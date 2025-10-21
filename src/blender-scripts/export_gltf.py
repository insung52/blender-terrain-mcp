"""
GLTF Export 전용 스크립트
기존 .blend 파일을 읽어서 .glb로 변환 (도로 생성 전/후 모두 사용 가능)

Usage:
    blender <terrain.blend> --background --python export_gltf.py -- <output.glb>

처리 순서:
    1. .blend 파일 로드 (자동, Blender가 처리)
    2. Terrain 객체 찾기
    3. Texture Baking (Shader Nodes → PNG)
    4. Water Material 단순화 (Fresnel, Volume 제거)
    5. Road 메시 찾기 (있으면 포함)
    6. GLTF Export (Terrain + Water + Road(optional))
"""

import bpy
import sys
import os
import math

# =============================================================================
# 로깅 함수
# =============================================================================

def log(msg):
    """로그 출력"""
    print(f"[GLTF Export] {msg}")
    sys.stdout.flush()


# =============================================================================
# 1. Texture Baking
# =============================================================================

def bake_terrain_textures(terrain_obj, output_dir, terrain_id):
    """
    지형 메시의 Material을 이미지 텍스처로 Baking

    Args:
        terrain_obj: 지형 메시 객체
        output_dir: 텍스처 출력 디렉토리
        terrain_id: 지형 고유 ID (파일명 충돌 방지)

    Returns:
        baked_texture_path: Baking된 텍스처 파일 경로
    """
    log("Starting texture baking...")

    # 1. UV Unwrap (Smart UV Project)
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')

    log("UV unwrap completed")

    # 2. Bake용 이미지 생성 (2048x2048)
    bake_image = bpy.data.images.new(
        name="TerrainBake",
        width=2048,
        height=2048,
        alpha=False
    )

    # 3. Material에 Image Texture 노드 추가
    if not terrain_obj.data.materials:
        log("⚠️ No material found on terrain, skipping baking")
        return None

    material = terrain_obj.data.materials[0]
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Image Texture 노드 생성 (Baking 타겟)
    bake_node = nodes.new('ShaderNodeTexImage')
    bake_node.image = bake_image
    bake_node.select = True
    nodes.active = bake_node

    log("Bake image node created")

    # 4. Bake 실행
    # 모든 객체 선택 해제 후 지형만 선택
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.bake_type = 'DIFFUSE'
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False

    log("Baking diffuse texture... (this may take a while)")

    try:
        bpy.ops.object.bake(type='DIFFUSE')
        log("✅ Baking completed")
    except Exception as e:
        log(f"❌ Baking failed: {e}")
        return None

    # 5. 이미지 저장 (지형별 고유 파일명으로 충돌 방지)
    os.makedirs(output_dir, exist_ok=True)
    texture_path = os.path.join(output_dir, f'{terrain_id}_diffuse.png')
    bake_image.filepath_raw = texture_path
    bake_image.file_format = 'PNG'
    bake_image.save()

    log(f"✅ Texture saved: {texture_path}")

    # 6. Baked 텍스처를 실제 Material에 연결
    # Material의 Shader Nodes를 단순화 (Geometry는 이미 Apply됨)
    # 기존: ColorRamp, Noise Texture, Math Nodes 등 복잡한 Shader Graph
    # → GLTF는 복잡한 노드 지원 안함
    # 변환: Image Texture → Principled BSDF (단순)

    # 기존 노드 삭제 (Output과 Bake Node 제외)
    output_node = None
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
        elif node != bake_node:
            nodes.remove(node)

    if not output_node:
        output_node = nodes.new('ShaderNodeOutputMaterial')
        output_node.location = (400, 0)

    # Principled BSDF 추가
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)

    # Image Texture 위치 조정
    bake_node.location = (0, 0)

    # 연결
    links.new(bake_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])

    log("✅ Material simplified (Image Texture → Principled BSDF)")

    return texture_path


# =============================================================================
# 2. 도로 Material 단순화 (Baking 없이 기존 UV 유지)
# =============================================================================

def simplify_road_material(road_obj):
    """
    도로 메시의 Material을 GLTF 호환 형태로 단순화 (UV 보존)

    도로는 이미 정교한 UV 매핑이 되어 있으므로 Baking하지 않고,
    기존 Image Texture 노드를 유지하면서 불필요한 노드만 제거

    Args:
        road_obj: 도로 메시 객체

    Returns:
        texture_path: 원본 텍스처 경로 (roadtexture.jpg)
    """
    log("Simplifying road material (preserving UV)...")

    # UV 정보 디버깅
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(road_obj.data)
    uv_layer = bm.loops.layers.uv.active
    if uv_layer:
        uv_samples = []
        for i, face in enumerate(bm.faces):
            if i < 3:  # 처음 3개 face만
                for loop in face.loops:
                    uv = loop[uv_layer].uv
                    uv_samples.append((uv.x, uv.y))
        log(f"   UV samples (before export): {uv_samples[:6]}")
    bm.free()

    if not road_obj.data.materials:
        log("⚠️ No material found on road")
        return None

    material = road_obj.data.materials[0]
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # 1. 기존 노드 찾기
    output_node = None
    bsdf_node = None
    image_node = None
    tex_coord_node = None

    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
        elif node.type == 'BSDF_PRINCIPLED':
            bsdf_node = node
        elif node.type == 'TEX_IMAGE':
            image_node = node
        elif node.type == 'TEX_COORD':
            tex_coord_node = node

    # 2. GLTF 호환 구조 확인: Tex Coord → Image Texture → BSDF → Output
    if not (output_node and bsdf_node and image_node):
        log("⚠️ Road material structure incomplete, cannot simplify")
        return None

    # 3. 불필요한 노드 제거 (Mapping, ColorRamp 등 GLTF 비호환 노드)
    nodes_to_keep = {output_node, bsdf_node, image_node}
    if tex_coord_node:
        nodes_to_keep.add(tex_coord_node)

    for node in list(nodes):
        if node not in nodes_to_keep:
            nodes.remove(node)

    # 4. 연결 재구성 (GLTF 호환)
    links.clear()

    # Tex Coord → Image (UV 유지)
    if tex_coord_node:
        links.new(tex_coord_node.outputs['UV'], image_node.inputs['Vector'])

    # Image → BSDF Base Color
    links.new(image_node.outputs['Color'], bsdf_node.inputs['Base Color'])

    # BSDF → Output
    links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])

    # 5. 텍스처 경로 확인
    texture_path = image_node.image.filepath if image_node.image else None

    log("✅ Road material simplified (UV preserved)")
    log(f"   Using texture: {texture_path if texture_path else 'embedded'}")

    return texture_path


# =============================================================================
# 3. 물 Material 단순화
# =============================================================================

def simplify_water_material(water_obj):
    """
    물 메시의 Material을 GLTF 호환 단순 Material로 교체

    Args:
        water_obj: 물 메시 객체

    Returns:
        water_obj: Material이 교체된 물 메시
    """
    log("Simplifying water material...")

    # 기존 Material 제거
    water_obj.data.materials.clear()

    # 새 Material 생성 (GLTF 호환)
    water_mat = bpy.data.materials.new(name="WaterMaterial_Simple")
    water_mat.use_nodes = True

    nodes = water_mat.node_tree.nodes
    links = water_mat.node_tree.links
    nodes.clear()

    # Principled BSDF (단순 설정만)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    bsdf.inputs['Base Color'].default_value = (0.1, 0.3, 0.6, 1.0)  # 파란색
    bsdf.inputs['Transmission Weight'].default_value = 0.8  # 80% 투명
    bsdf.inputs['Roughness'].default_value = 0.1  # 약간 반짝임
    bsdf.inputs['IOR'].default_value = 1.333  # 물의 굴절률 (기본값)

    # Output
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Blend Mode 설정
    water_mat.blend_method = 'BLEND'

    # Material 할당
    water_obj.data.materials.append(water_mat)

    log("✅ Water material simplified for GLTF")
    log("   Removed: Fresnel, Volume Absorption")
    log("   Kept: Basic transparency and color")

    return water_obj


# =============================================================================
# 3. GLTF Export
# =============================================================================

def export_to_gltf(objects_list, output_path):
    """
    지형 + 물 + (도로) 메시를 GLB 포맷으로 Export

    Args:
        objects_list: Export할 객체 리스트 [terrain, water, road(optional)]
        output_path: 출력 .glb 파일 경로
    """
    log(f"Exporting {len(objects_list)} objects to GLTF...")

    # 1. 모든 객체 선택 해제
    bpy.ops.object.select_all(action='DESELECT')

    # 2. Export할 객체들 선택
    for obj in objects_list:
        obj.select_set(True)
        log(f"   - {obj.name}")

    # 3. GLB Export
    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',  # Binary 포맷 (단일 파일)
            use_selection=True,   # 선택된 객체만

            # Geometry
            # False로 설정: 지형은 이미 Geometry Nodes가 Apply된 상태이고,
            # 도로는 UV 보존을 위해 Apply하지 않음
            export_apply=False,

            # Materials
            export_materials='EXPORT',

            # Optimization
            # Draco 압축 비활성화 (UV 좌표 보존 및 파일 크기보다 품질 우선)
            export_draco_mesh_compression_enable=False,

            # Extras
            export_extras=False,
            export_cameras=False,
            export_lights=False
        )
        log(f"✅ GLTF exported: {output_path}")
    except Exception as e:
        log(f"❌ GLTF export failed: {e}")
        raise


# =============================================================================
# 4. 메인 실행
# =============================================================================

def main():
    """메인 실행 함수"""

    # 커맨드라인 인자
    argv = sys.argv
    if "--" not in argv:
        log("❌ No arguments provided")
        log("Usage: blender <terrain.blend> --background --python export_gltf.py -- <output.glb>")
        sys.exit(1)

    argv = argv[argv.index("--") + 1:]

    if len(argv) < 1:
        log("❌ Output path not provided")
        sys.exit(1)

    output_glb_path = argv[0]
    log(f"Output GLB: {output_glb_path}")

    # 현재 Scene의 지형 객체 찾기
    terrain_obj = bpy.data.objects.get("BiomeTerrain")
    if not terrain_obj:
        log("❌ Terrain object 'BiomeTerrain' not found")
        log("Available objects:")
        for obj in bpy.data.objects:
            log(f"   - {obj.name}")
        sys.exit(1)

    log(f"✅ Terrain object found: {terrain_obj.name}")

    # 1. Texture Baking
    output_dir = os.path.dirname(output_glb_path)
    if not output_dir:
        output_dir = os.getcwd()

    # .glb 파일명에서 terrain ID 추출 (예: f4f04317-26b7-472d-8f58-7308a20631d8.glb → f4f04317-26b7-472d-8f58-7308a20631d8)
    terrain_id = os.path.splitext(os.path.basename(output_glb_path))[0]

    baked_terrain_texture = bake_terrain_textures(terrain_obj, output_dir, terrain_id)

    # 2. 물 메시 Material 단순화
    water_obj = bpy.data.objects.get("Water")
    if not water_obj:
        log("⚠️ Water mesh not found (will export without water)")
    else:
        log("✅ Water mesh found")
        simplify_water_material(water_obj)

    # 3. 도로 메시 찾기 및 Material 단순화
    road_obj = bpy.data.objects.get("Road")
    road_texture = None

    objects_to_export = [terrain_obj]
    if water_obj:
        objects_to_export.append(water_obj)
    if road_obj:
        log("✅ Road mesh found, will be included")

        # UV 확인 (파일에서 로드된 UV 상태 체크)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(road_obj.data)
        uv_layer = bm.loops.layers.uv.active
        if uv_layer:
            uv_samples = []
            for i, face in enumerate(bm.faces):
                if i < 2:  # 처음 2개 face만
                    for loop in face.loops:
                        uv = loop[uv_layer].uv
                        uv_samples.append((round(uv.x, 3), round(uv.y, 3)))
            log(f"   Road UV samples from file: {uv_samples[:4]}")
        bm.free()

        # 도로 Material 확인
        if road_obj.data.materials:
            mat = road_obj.data.materials[0]
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    log(f"   Road texture path: {node.image.filepath}")
                    log(f"   Road texture packed: {node.image.packed_file is not None}")
                    # 이미지가 packed되지 않았다면 pack
                    if not node.image.packed_file:
                        log("   Packing road texture into blend file...")
                        node.image.pack()

        # CRITICAL: .blend 파일을 다시 저장해서 UV 변경사항 확정
        temp_blend_path = output_glb_path.replace('.glb', '_temp.blend')
        log(f"   Saving temporary blend file to preserve UV: {temp_blend_path}")
        bpy.ops.wm.save_as_mainfile(filepath=temp_blend_path, copy=True)

        objects_to_export.append(road_obj)

    # 4. GLTF Export
    export_to_gltf(objects_to_export, output_glb_path)

    # 5. 완료
    log("=" * 60)
    log("🎉 GLTF Export Complete!")
    log("=" * 60)
    log(f"Objects: {len(objects_to_export)}")
    for obj in objects_to_export:
        log(f"   - {obj.name} ({len(obj.data.vertices)} vertices)")
    log(f"Output: {output_glb_path}")
    if baked_terrain_texture:
        log(f"Terrain Texture: {baked_terrain_texture}")
    log("=" * 60)


if __name__ == "__main__":
    main()
