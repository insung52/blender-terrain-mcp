"""
Blender에서 실행되는 바이옴 지형 생성 스크립트
Geometry Nodes를 사용하여 이미지 기반 지형 생성

Usage:
    blender --background --python biome_terrain_blender.py -- <image_dir> <output_blend>
"""

import bpy
import sys
import os
import math

# =============================================================================
# 커맨드라인 인자 파싱
# =============================================================================

argv = sys.argv
argv = argv[argv.index("--") + 1:]  # -- 이후의 인자들만

if len(argv) < 2:
    print("Usage: blender --background --python biome_terrain_blender.py -- <image_dir> <output_blend>")
    sys.exit(1)

IMAGE_DIR = argv[0]
OUTPUT_BLEND = argv[1]

print(f"📂 Image Directory: {IMAGE_DIR}")
print(f"💾 Output Blend: {OUTPUT_BLEND}")

# =============================================================================
# 1. 기존 객체 삭제
# =============================================================================

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# =============================================================================
# 2. 100x100 그리드 메시 생성
# =============================================================================

bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=100,
    y_subdivisions=100,
    size=100,
    location=(0, 0, 0)
)

terrain_obj = bpy.context.active_object
terrain_obj.name = "BiomeTerrain"
mesh = terrain_obj.data

print(f"✅ Created 100x100 grid mesh ({len(mesh.vertices)} vertices)")

# =============================================================================
# 3. 바이옴 이미지 로드
# =============================================================================

param_names = [
    'temperature', 'humidity', 'erosion', 'continentalness', 'weirdness',
    'vegetation_color_r', 'vegetation_color_g', 'vegetation_color_b',
    'ground_color_r', 'ground_color_g', 'ground_color_b',
    'snow_start_height', 'rock_exposure'
]

loaded_images = {}

for param_name in param_names:
    img_path = os.path.join(IMAGE_DIR, f'biome_{param_name}.png')
    if os.path.exists(img_path):
        # 이미 로드된 이미지가 있으면 제거
        if f'biome_{param_name}' in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[f'biome_{param_name}'])

        img = bpy.data.images.load(img_path)
        img.name = f'biome_{param_name}'
        loaded_images[param_name] = img
        print(f'✅ Loaded: {param_name} ({img.size[0]}x{img.size[1]})')
    else:
        print(f'❌ Not found: {img_path}')

# =============================================================================
# 4. Geometry Nodes 모디파이어 추가
# =============================================================================

# Geometry Nodes 모디파이어 생성
modifier = terrain_obj.modifiers.new(name="BiomeTerrainGenerator", type='NODES')

# Node Group 생성
node_group = bpy.data.node_groups.new(name="BiomeTerrain", type='GeometryNodeTree')
modifier.node_group = node_group

# Input/Output 노드
nodes = node_group.nodes
links = node_group.links

group_input = nodes.new('NodeGroupInput')
group_output = nodes.new('NodeGroupOutput')

group_input.location = (-1000, 0)
group_output.location = (1000, 0)

# Input/Output 소켓 정의
node_group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
node_group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

# =============================================================================
# 5. Geometry Nodes 그래프 생성
# =============================================================================

# Position 노드
position_node = nodes.new('GeometryNodeInputPosition')
position_node.location = (-800, 0)

# Separate XYZ
separate_xyz = nodes.new('ShaderNodeSeparateXYZ')
separate_xyz.location = (-600, 0)
links.new(position_node.outputs['Position'], separate_xyz.inputs['Vector'])

# Normalize X, Y to 0~1 (그리드는 -50~50이므로 +50하고 /100)
add_x_node = nodes.new('ShaderNodeMath')
add_x_node.operation = 'ADD'
add_x_node.inputs[1].default_value = 50.0
add_x_node.location = (-400, 200)
links.new(separate_xyz.outputs['X'], add_x_node.inputs[0])

divide_x_node = nodes.new('ShaderNodeMath')
divide_x_node.operation = 'DIVIDE'
divide_x_node.inputs[1].default_value = 100.0
divide_x_node.location = (-200, 200)
links.new(add_x_node.outputs['Value'], divide_x_node.inputs[0])

add_y_node = nodes.new('ShaderNodeMath')
add_y_node.operation = 'ADD'
add_y_node.inputs[1].default_value = 50.0
add_y_node.location = (-400, 0)
links.new(separate_xyz.outputs['Y'], add_y_node.inputs[0])

divide_y_node = nodes.new('ShaderNodeMath')
divide_y_node.operation = 'DIVIDE'
divide_y_node.inputs[1].default_value = 100.0
divide_y_node.location = (-200, 0)
links.new(add_y_node.outputs['Value'], divide_y_node.inputs[0])

# Combine XY for UV
combine_xy = nodes.new('ShaderNodeCombineXYZ')
combine_xy.location = (0, 100)
links.new(divide_x_node.outputs['Value'], combine_xy.inputs['X'])
links.new(divide_y_node.outputs['Value'], combine_xy.inputs['Y'])

# =============================================================================
# 6. Image Texture 샘플링 및 Attribute 저장
# =============================================================================

# 각 파라미터에 대해 Image Texture + Map Range + Store Named Attribute
current_y = 500

# 지형 높이에 사용할 파라미터만 로드 (temperature, erosion, continentalness, weirdness)
height_params = ['temperature', 'erosion', 'continentalness', 'weirdness']

stored_attributes = {}

for param_name in height_params:
    if param_name not in loaded_images:
        continue

    # Image Texture 노드
    img_tex_node = nodes.new('GeometryNodeImageTexture')
    img_tex_node.location = (200, current_y)
    # Blender 4.5+에서는 inputs['Image']로 이미지 설정
    img_tex_node.inputs['Image'].default_value = loaded_images[param_name]
    # interpolation은 extension_type으로 변경됨
    img_tex_node.extension = 'EXTEND'
    links.new(combine_xy.outputs['Vector'], img_tex_node.inputs['Vector'])

    # Map Range (0~1 이미지 값을 파라미터 범위로 변환)
    map_range = nodes.new('ShaderNodeMapRange')
    map_range.location = (400, current_y)

    if param_name in ['temperature', 'continentalness']:
        # 0~1 → -1~1
        map_range.inputs['From Min'].default_value = 0.0
        map_range.inputs['From Max'].default_value = 1.0
        map_range.inputs['To Min'].default_value = -1.0
        map_range.inputs['To Max'].default_value = 1.0
    else:
        # 0~1 → 0~1 (그대로)
        map_range.inputs['From Min'].default_value = 0.0
        map_range.inputs['From Max'].default_value = 1.0
        map_range.inputs['To Min'].default_value = 0.0
        map_range.inputs['To Max'].default_value = 1.0

    links.new(img_tex_node.outputs['Color'], map_range.inputs['Value'])

    # Store Named Attribute
    store_attr = nodes.new('GeometryNodeStoreNamedAttribute')
    store_attr.location = (600, current_y)
    store_attr.data_type = 'FLOAT'
    store_attr.domain = 'POINT'
    store_attr.inputs['Name'].default_value = param_name

    links.new(map_range.outputs['Result'], store_attr.inputs['Value'])

    # 체인 연결 (Input → Store Attr → Output)
    if not stored_attributes:
        # 첫 번째
        links.new(group_input.outputs['Geometry'], store_attr.inputs['Geometry'])
    else:
        # 이전 노드에서 연결
        prev_node = list(stored_attributes.values())[-1]
        links.new(prev_node.outputs['Geometry'], store_attr.inputs['Geometry'])

    stored_attributes[param_name] = store_attr

    current_y -= 300

# =============================================================================
# 7. Named Attribute 읽기 + Noise Texture + 지형 높이 계산
# =============================================================================

last_store_node = list(stored_attributes.values())[-1]

# Named Attributes
attr_temp = nodes.new('GeometryNodeInputNamedAttribute')
attr_temp.location = (800, 400)
attr_temp.data_type = 'FLOAT'
attr_temp.inputs['Name'].default_value = 'temperature'

attr_erosion = nodes.new('GeometryNodeInputNamedAttribute')
attr_erosion.location = (800, 200)
attr_erosion.data_type = 'FLOAT'
attr_erosion.inputs['Name'].default_value = 'erosion'

attr_continentalness = nodes.new('GeometryNodeInputNamedAttribute')
attr_continentalness.location = (800, 0)
attr_continentalness.data_type = 'FLOAT'
attr_continentalness.inputs['Name'].default_value = 'continentalness'

attr_weirdness = nodes.new('GeometryNodeInputNamedAttribute')
attr_weirdness.location = (800, -200)
attr_weirdness.data_type = 'FLOAT'
attr_weirdness.inputs['Name'].default_value = 'weirdness'

# Noise Texture (기본)
noise_node = nodes.new('ShaderNodeTexNoise')
noise_node.location = (1000, -400)
noise_node.inputs['Scale'].default_value = 0.05
noise_node.inputs['Detail'].default_value = 5.0
links.new(position_node.outputs['Position'], noise_node.inputs['Vector'])

# Noise Texture (weirdness용)
noise_weird = nodes.new('ShaderNodeTexNoise')
noise_weird.location = (1000, -600)
noise_weird.inputs['Scale'].default_value = 0.2
noise_weird.inputs['Detail'].default_value = 3.0
links.new(position_node.outputs['Position'], noise_weird.inputs['Vector'])

# 지형 높이 계산: Height = Noise * erosion * 20.0
multiply_noise_erosion = nodes.new('ShaderNodeMath')
multiply_noise_erosion.operation = 'MULTIPLY'
multiply_noise_erosion.location = (1200, 200)
links.new(noise_node.outputs['Fac'], multiply_noise_erosion.inputs[0])
links.new(attr_erosion.outputs['Attribute'], multiply_noise_erosion.inputs[1])

multiply_by_20 = nodes.new('ShaderNodeMath')
multiply_by_20.operation = 'MULTIPLY'
multiply_by_20.inputs[1].default_value = 20.0
multiply_by_20.location = (1400, 200)
links.new(multiply_noise_erosion.outputs['Value'], multiply_by_20.inputs[0])

# continentalness * 10.0
multiply_cont_10 = nodes.new('ShaderNodeMath')
multiply_cont_10.operation = 'MULTIPLY'
multiply_cont_10.inputs[1].default_value = 10.0
multiply_cont_10.location = (1200, 0)
links.new(attr_continentalness.outputs['Attribute'], multiply_cont_10.inputs[0])

# weirdness * Noise * 5.0
multiply_weird_noise = nodes.new('ShaderNodeMath')
multiply_weird_noise.operation = 'MULTIPLY'
multiply_weird_noise.location = (1200, -200)
links.new(attr_weirdness.outputs['Attribute'], multiply_weird_noise.inputs[0])
links.new(noise_weird.outputs['Fac'], multiply_weird_noise.inputs[1])

multiply_by_5 = nodes.new('ShaderNodeMath')
multiply_by_5.operation = 'MULTIPLY'
multiply_by_5.inputs[1].default_value = 5.0
multiply_by_5.location = (1400, -200)
links.new(multiply_weird_noise.outputs['Value'], multiply_by_5.inputs[0])

# Height += continentalness * 10.0
add_cont = nodes.new('ShaderNodeMath')
add_cont.operation = 'ADD'
add_cont.location = (1600, 100)
links.new(multiply_by_20.outputs['Value'], add_cont.inputs[0])
links.new(multiply_cont_10.outputs['Value'], add_cont.inputs[1])

# Height += weirdness * Noise * 5.0
add_weird = nodes.new('ShaderNodeMath')
add_weird.operation = 'ADD'
add_weird.location = (1800, 100)
links.new(add_cont.outputs['Value'], add_weird.inputs[0])
links.new(multiply_by_5.outputs['Value'], add_weird.inputs[1])

# Height *= (1.0 - temperature * 0.2)
multiply_temp_02 = nodes.new('ShaderNodeMath')
multiply_temp_02.operation = 'MULTIPLY'
multiply_temp_02.inputs[1].default_value = 0.2
multiply_temp_02.location = (1600, 400)
links.new(attr_temp.outputs['Attribute'], multiply_temp_02.inputs[0])

subtract_from_1 = nodes.new('ShaderNodeMath')
subtract_from_1.operation = 'SUBTRACT'
subtract_from_1.inputs[0].default_value = 1.0
subtract_from_1.location = (1800, 400)
links.new(multiply_temp_02.outputs['Value'], subtract_from_1.inputs[1])

multiply_final = nodes.new('ShaderNodeMath')
multiply_final.operation = 'MULTIPLY'
multiply_final.location = (2000, 250)
links.new(add_weird.outputs['Value'], multiply_final.inputs[0])
links.new(subtract_from_1.outputs['Value'], multiply_final.inputs[1])

# =============================================================================
# 8. Set Position (Z offset)
# =============================================================================

combine_offset = nodes.new('ShaderNodeCombineXYZ')
combine_offset.location = (2200, 250)
combine_offset.inputs['X'].default_value = 0.0
combine_offset.inputs['Y'].default_value = 0.0
links.new(multiply_final.outputs['Value'], combine_offset.inputs['Z'])

set_position = nodes.new('GeometryNodeSetPosition')
set_position.location = (2400, 0)
links.new(last_store_node.outputs['Geometry'], set_position.inputs['Geometry'])
links.new(combine_offset.outputs['Vector'], set_position.inputs['Offset'])

# =============================================================================
# 9. Set Shade Smooth
# =============================================================================

set_smooth = nodes.new('GeometryNodeSetShadeSmooth')
set_smooth.location = (2600, 0)
set_smooth.inputs['Shade Smooth'].default_value = True
links.new(set_position.outputs['Geometry'], set_smooth.inputs['Geometry'])

# Output 연결
links.new(set_smooth.outputs['Geometry'], group_output.inputs['Geometry'])

print("✅ Geometry Nodes graph created")

# =============================================================================
# 10. Material 추가 (간단한 높이 기반 색상)
# =============================================================================

material = bpy.data.materials.new(name="BiomeTerrainMaterial")
material.use_nodes = True
material_nodes = material.node_tree.nodes
material_links = material.node_tree.links

# 기존 노드 삭제
material_nodes.clear()

# Output
mat_output = material_nodes.new('ShaderNodeOutputMaterial')
mat_output.location = (400, 0)

# Principled BSDF
bsdf = material_nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (200, 0)

# ColorRamp (높이 기반 색상)
color_ramp = material_nodes.new('ShaderNodeValToRGB')
color_ramp.location = (0, 0)
color_ramp.color_ramp.elements[0].color = (0.2, 0.15, 0.1, 1.0)  # 낮은 곳: 갈색
color_ramp.color_ramp.elements[1].color = (0.9, 0.9, 0.9, 1.0)  # 높은 곳: 흰색

# Position Z
position_mat = material_nodes.new('ShaderNodeNewGeometry')
position_mat.location = (-400, 0)

separate_xyz_mat = material_nodes.new('ShaderNodeSeparateXYZ')
separate_xyz_mat.location = (-200, 0)

material_links.new(position_mat.outputs['Position'], separate_xyz_mat.inputs['Vector'])
material_links.new(separate_xyz_mat.outputs['Z'], color_ramp.inputs['Fac'])
material_links.new(color_ramp.outputs['Color'], bsdf.inputs['Base Color'])
material_links.new(bsdf.outputs['BSDF'], mat_output.inputs['Surface'])

# Material 할당
if terrain_obj.data.materials:
    terrain_obj.data.materials[0] = material
else:
    terrain_obj.data.materials.append(material)

print("✅ Material created and assigned")

# =============================================================================
# 11. 카메라 및 조명 추가
# =============================================================================

# 카메라
bpy.ops.object.camera_add(location=(150, -150, 100))
camera = bpy.context.active_object
camera.rotation_euler = (math.radians(60), 0, math.radians(45))
bpy.context.scene.camera = camera

# 조명
bpy.ops.object.light_add(type='SUN', location=(50, 50, 100))
light = bpy.context.active_object
light.data.energy = 2.0

print("✅ Camera and light added")

# =============================================================================
# 12. 저장
# =============================================================================

bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)
print(f"✅ Saved: {OUTPUT_BLEND}")

print("\n" + "="*60)
print("🎉 Biome Terrain Generation Complete!")
print("="*60)
print(f"Vertices: {len(mesh.vertices)}")
print(f"Biome Parameters: {len(loaded_images)}")
print(f"Output: {OUTPUT_BLEND}")
print("="*60)
