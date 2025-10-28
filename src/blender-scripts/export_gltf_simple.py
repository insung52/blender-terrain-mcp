"""
Simple GLTF exporter with texture baking for terrain
Minimal implementation - only bakes diffuse textures
"""

import bpy
import sys
import os

def log(message):
    print(f"[GLTF Export] {message}", flush=True)

def bake_diffuse_texture(obj, texture_size=2048):
    """
    Bake diffuse color to texture for an object
    """
    log(f"Baking diffuse texture for: {obj.name}")

    # 오브젝트 선택
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Material 확인
    if not obj.data.materials:
        log(f"  No materials found on {obj.name}, skipping")
        return

    mat = obj.data.materials[0]
    if not mat.use_nodes:
        log(f"  Material {mat.name} doesn't use nodes, skipping")
        return

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Image Texture 노드 생성
    bake_image = bpy.data.images.new(
        name=f"{obj.name}_Diffuse",
        width=texture_size,
        height=texture_size,
        alpha=False
    )

    # Image Texture 노드 추가
    img_node = nodes.new(type='ShaderNodeTexImage')
    img_node.image = bake_image
    img_node.select = True
    nodes.active = img_node

    # UV 확인
    if not obj.data.uv_layers:
        log(f"  No UV map found, creating one...")
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')

    # Bake settings
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.cycles.samples = 16  # 빠른 베이킹
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False
    bpy.context.scene.render.bake.use_pass_color = True

    # Bake
    log(f"  Baking... (resolution: {texture_size}x{texture_size})")
    try:
        bpy.ops.object.bake(type='DIFFUSE')
        log(f"  ✅ Bake complete")
    except Exception as e:
        log(f"  ❌ Bake failed: {e}")
        # 실패해도 계속 진행
        nodes.remove(img_node)
        bpy.data.images.remove(bake_image)
        return

    # 기존 노드들 제거하고 간단한 setup으로 교체
    output_node = None
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
            break

    if output_node:
        # 기존 연결 제거
        for link in list(links):
            links.remove(link)

        # 간단한 setup: Image Texture -> Principled BSDF -> Output
        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = (0, 0)

        img_node.location = (-300, 0)
        output_node.location = (300, 0)

        # 연결
        links.new(img_node.outputs['Color'], principled.inputs['Base Color'])
        links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])

        log(f"  Material simplified with baked texture")

def main():
    if len(sys.argv) < 7:
        log("Usage: blender file.blend --background --python export_gltf_simple.py -- output.glb")
        sys.exit(1)

    # Arguments after --
    argv = sys.argv[sys.argv.index("--") + 1:]
    output_path = argv[0]

    log(f"Starting GLTF export")
    log(f"Output: {output_path}")

    # Terrain 오브젝트 찾기 및 베이킹
    terrain_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and 'terrain' in obj.name.lower()]

    if terrain_objects:
        log(f"Found {len(terrain_objects)} terrain object(s)")
        for obj in terrain_objects:
            bake_diffuse_texture(obj, texture_size=2048)
    else:
        log("No terrain objects found, skipping baking")

    # GLTF Export
    log("Exporting to GLTF...")
    try:
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            export_texcoords=True,
            export_normals=True,
            export_materials='EXPORT',
            export_cameras=False,
            export_lights=False,
            export_apply=True
        )
        log(f"✅ Export complete: {output_path}")

        # 파일 크기 확인
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            log(f"File size: {size_mb:.2f} MB")

    except Exception as e:
        log(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
