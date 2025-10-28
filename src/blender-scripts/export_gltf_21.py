"""
GLTF Export with Terrain Texture Baking
- 지형: Texture Baking (Shader Nodes → PNG)
- 도로/물: 그대로 유지 (UV 보존)

& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" "C:\graphics\buildup\blender-terrain-mcp\output\test.blend" --background --python "C:\graphics\buildup\blender-terrain-mcp\src\blender-scripts\export_gltf_21.py" -- "C:\graphics\buildup\blender-terrain-mcp\output\test.glb"


Usage:
    blender <input.blend> --background --python test_gltf_export.py -- <output.glb>
"""

import bpy
import sys
import os

def log(msg):
    print(f"[GLTF Export] {msg}")
    sys.stdout.flush()

def bake_terrain_texture(terrain_obj, output_dir, terrain_id):
    """지형 텍스처 Baking (Shader Nodes → PNG)"""
    log("Starting terrain texture baking...")

    # CRITICAL: 모든 객체 deselect + 지형만 active
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    # 1. UV Unwrap
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')

    # 2. Bake 이미지 생성
    bake_image = bpy.data.images.new(name="TerrainBake", width=2048, height=2048, alpha=False)

    # 3. Material에 Image Texture 노드 추가
    if not terrain_obj.data.materials:
        log("⚠️ No material on terrain, skipping baking")
        return None

    material = terrain_obj.data.materials[0]
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    bake_node = nodes.new('ShaderNodeTexImage')
    bake_node.image = bake_image
    bake_node.select = True
    nodes.active = bake_node

    # 4. Baking
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.bake_type = 'DIFFUSE'
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False

    log("Baking diffuse texture (this may take a while)...")
    try:
        bpy.ops.object.bake(type='DIFFUSE')
        log("✅ Baking completed")
    except Exception as e:
        log(f"❌ Baking failed: {e}")
        return None

    # 5. 이미지 저장
    os.makedirs(output_dir, exist_ok=True)
    texture_path = os.path.join(output_dir, f'{terrain_id}_diffuse.png')
    bake_image.filepath_raw = texture_path
    bake_image.file_format = 'PNG'
    bake_image.save()
    log(f"✅ Texture saved: {texture_path}")

    # 6. Material 단순화 (지형 Material ONLY)
    # IMPORTANT: material 변수를 재확인해서 정확히 지형 Material만 수정
    terrain_material = terrain_obj.data.materials[0]
    terrain_nodes = terrain_material.node_tree.nodes
    terrain_links = terrain_material.node_tree.links

    output_node = None
    for node in list(terrain_nodes):  # list() 복사본으로 순회
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
        elif node != bake_node:
            terrain_nodes.remove(node)

    if not output_node:
        output_node = terrain_nodes.new('ShaderNodeOutputMaterial')
        output_node.location = (400, 0)

    bsdf = terrain_nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)
    bake_node.location = (0, 0)

    terrain_links.new(bake_node.outputs['Color'], bsdf.inputs['Base Color'])
    terrain_links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])

    log("✅ Terrain material simplified")

    # CRITICAL: 지형 작업 완료 후 deselect
    bpy.ops.object.select_all(action='DESELECT')

    return texture_path

def main():
    # 커맨드라인 인자 파싱
    argv = sys.argv
    if "--" not in argv:
        log("❌ Usage: blender <input.blend> --background --python test_gltf_export.py -- <output.glb>")
        sys.exit(1)

    argv = argv[argv.index("--") + 1:]
    if len(argv) < 1:
        log("❌ Output GLB path not provided")
        sys.exit(1)

    output_glb_path = argv[0]
    output_dir = os.path.dirname(output_glb_path) or os.getcwd()
    terrain_id = os.path.splitext(os.path.basename(output_glb_path))[0]

    log(f"Input: {bpy.data.filepath}")
    log(f"Output: {output_glb_path}")

    # 지형 객체 찾기
    terrain_obj = bpy.data.objects.get("BiomeTerrain")
    if terrain_obj:
        log(f"✅ Terrain found: {terrain_obj.name}")
        bake_terrain_texture(terrain_obj, output_dir, terrain_id)
    else:
        log("⚠️ Terrain object 'BiomeTerrain' not found, skipping baking")

    # 도로/물은 그대로 유지 (아무것도 안 함)
    road_obj = bpy.data.objects.get("Road")
    water_obj = bpy.data.objects.get("Water")

    if road_obj:
        log(f"✅ Road found: {road_obj.name} (using as-is)")
    if water_obj:
        log(f"✅ Water found: {water_obj.name} (using as-is)")

    # GLTF Export (기본 설정)
    log("Exporting to GLTF...")
    bpy.ops.export_scene.gltf(
        filepath=output_glb_path,
        export_format='GLB'
    )

    log(f"✅ Export complete: {output_glb_path}")

if __name__ == "__main__":
    main()
