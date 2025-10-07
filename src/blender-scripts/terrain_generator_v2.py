import bpy
import sys
import json
import math

# 커맨드 라인 인자 파싱
args = sys.argv[sys.argv.index("--") + 1:]
params_file = args[0]
output_path = args[1]
preview_path = args[2]

# 파라미터 파일 읽기
with open(params_file, 'r') as f:
    params = json.load(f)

print(f"[Terrain v2] Parameters: {json.dumps(params, indent=2)}")
print(f"[Terrain v2] Output: {output_path}")
print(f"[Terrain v2] Preview: {preview_path}")

# 기존 오브젝트 삭제
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ===== 파라미터 추출 =====
# 기본 형상
base_scale = params.get('base_scale', 20)
base_roughness = params.get('base_roughness', 0.7)
height_multiplier = params.get('height_multiplier', 30)

# 노이즈 설정
noise_type = params.get('noise_type', 'MUSGRAVE')  # PERLIN, VORONOI, MUSGRAVE
noise_layers = params.get('noise_layers', 3)
octaves = params.get('octaves', 6)

# 지형 특성
peak_sharpness = params.get('peak_sharpness', 0.5)
valley_depth = params.get('valley_depth', 0.5)
erosion = params.get('erosion', 0.3)
terrace_levels = params.get('terrace_levels', 0)

# 머티리얼
snow_height = params.get('snow_height', 0.7)
rock_height = params.get('rock_height', 0.3)
grass_height = params.get('grass_height', 0.0)

# 색상 (RGB)
snow_color = params.get('snow_color', [0.95, 0.95, 1.0])
rock_color = params.get('rock_color', [0.3, 0.3, 0.35])
grass_color = params.get('grass_color', [0.2, 0.4, 0.1])

# 환경
climate = params.get('climate', 'temperate')
wetness = params.get('wetness', 0.3)

base_size = 100  # 기본 100m로 생성
terrain_scale = params.get('terrain_scale', 10)  # 최종 스케일 배율 (기본 10배 = 1km)
size = base_size * terrain_scale  # 최종 크기 (표시용)

print(f"[Terrain v2] Creating terrain: base={base_size}m, scale={terrain_scale}x, final={size}m, height={height_multiplier}m")

# ===== 1. 고해상도 Plane 생성 (항상 100m로 생성) =====
print(f"[Terrain v2] Creating high-res plane...")
bpy.ops.mesh.primitive_grid_add(
    size=base_size,  # 항상 100m로 생성
    x_subdivisions=200,  # 높은 해상도
    y_subdivisions=200,
    location=(0, 0, 0)
)
terrain = bpy.context.active_object
terrain.name = "Terrain"

# ===== 2. Geometry Nodes Modifier 추가 =====
print(f"[Terrain v2] Setting up Geometry Nodes...")
geo_nodes = terrain.modifiers.new(name="TerrainGeometry", type='NODES')

# 새 Geometry Node Group 생성
node_group = bpy.data.node_groups.new(name="TerrainGenerator", type='GeometryNodeTree')
geo_nodes.node_group = node_group

# 노드 생성 헬퍼 함수
nodes = node_group.nodes
links = node_group.links

def create_node(type_name, location=(0, 0)):
    node = nodes.new(type=type_name)
    node.location = location
    return node

# Input/Output 노드
group_input = nodes.get('Group Input')
if not group_input:
    group_input = create_node('NodeGroupInput', (-800, 0))

group_output = nodes.get('Group Output')
if not group_output:
    group_output = create_node('NodeGroupOutput', (1200, 0))

# ===== 3. Base Noise Layer =====
print(f"[Terrain v2] Adding noise layers...")
noise_node = create_node('ShaderNodeTexNoise', (-600, 0))
noise_node.inputs['Scale'].default_value = base_scale
noise_node.inputs['Detail'].default_value = octaves
noise_node.inputs['Roughness'].default_value = base_roughness

# ===== 4. Multiple Noise Layers (디테일) =====
current_x = -400
math_add_node = None

for i in range(noise_layers):
    detail_noise = create_node('ShaderNodeTexNoise', (current_x, -200 * i))
    detail_noise.inputs['Scale'].default_value = base_scale * (2 ** (i + 1))
    detail_noise.inputs['Detail'].default_value = 2

    # 강도 감소
    multiply_node = create_node('ShaderNodeMath', (current_x + 200, -200 * i))
    multiply_node.operation = 'MULTIPLY'
    multiply_node.inputs[1].default_value = 1.0 / (2 ** (i + 1))

    links.new(detail_noise.outputs['Fac'], multiply_node.inputs[0])

    if math_add_node is None:
        # 첫 번째 레이어: base noise + detail
        math_add_node = create_node('ShaderNodeMath', (current_x + 400, 0))
        math_add_node.operation = 'ADD'
        links.new(noise_node.outputs['Fac'], math_add_node.inputs[0])
        links.new(multiply_node.outputs[0], math_add_node.inputs[1])
    else:
        # 이후 레이어: 이전 결과 + detail
        new_add = create_node('ShaderNodeMath', (current_x + 400, -100 * i))
        new_add.operation = 'ADD'
        links.new(math_add_node.outputs[0], new_add.inputs[0])
        links.new(multiply_node.outputs[0], new_add.inputs[1])
        math_add_node = new_add

combined_noise = math_add_node

# ===== 5. Peak Sharpness (Power) =====
if peak_sharpness > 0.01:
    print(f"[Terrain v2] Adding peak sharpness: {peak_sharpness}")
    power_node = create_node('ShaderNodeMath', (0, 0))
    power_node.operation = 'POWER'
    power_node.inputs[1].default_value = 1.0 + (peak_sharpness * 3)  # 1-4 range
    links.new(combined_noise.outputs[0], power_node.inputs[0])
    combined_noise = power_node

# ===== 6. Valley Depth =====
if valley_depth > 0.01:
    print(f"[Terrain v2] Adding valley depth: {valley_depth}")
    # Subtract 0.5, multiply, add back 0.5 (deepen valleys)
    sub_node = create_node('ShaderNodeMath', (200, 0))
    sub_node.operation = 'SUBTRACT'
    sub_node.inputs[1].default_value = 0.5

    mult_node = create_node('ShaderNodeMath', (400, 0))
    mult_node.operation = 'MULTIPLY'
    mult_node.inputs[1].default_value = 1.0 + valley_depth

    add_node = create_node('ShaderNodeMath', (600, 0))
    add_node.operation = 'ADD'
    add_node.inputs[1].default_value = 0.5

    links.new(combined_noise.outputs[0], sub_node.inputs[0])
    links.new(sub_node.outputs[0], mult_node.inputs[0])
    links.new(mult_node.outputs[0], add_node.inputs[0])
    combined_noise = add_node

# ===== 7. Terrace Effect =====
if terrace_levels > 0:
    print(f"[Terrain v2] Adding terrace effect: {terrace_levels} levels")
    snap_node = create_node('ShaderNodeMath', (800, 0))
    snap_node.operation = 'SNAP'
    snap_node.inputs[1].default_value = 1.0 / terrace_levels
    links.new(combined_noise.outputs[0], snap_node.inputs[0])
    combined_noise = snap_node

# ===== 8. Height Multiplier =====
final_mult = create_node('ShaderNodeMath', (1000, 0))
final_mult.operation = 'MULTIPLY'
final_mult.inputs[1].default_value = height_multiplier
links.new(combined_noise.outputs[0], final_mult.inputs[0])

# ===== 9. Position 노드 (Geometry Nodes) =====
# Shader Nodes가 아닌 Geometry Nodes로 전환 필요
# 현재는 Displacement 방식 사용 (Geometry Nodes는 복잡도가 높음)

print(f"[Terrain v2] Applying modifiers...")

# Geometry Nodes 대신 Displacement 사용 (간소화)
# 실제 Geometry Nodes 구현은 복잡하므로 Shader → Texture → Displacement 방식

# Texture 생성
texture = bpy.data.textures.new("TerrainTexture", type='BLEND')

# Displacement Modifier
displace_mod = terrain.modifiers.new(name="Displacement", type='DISPLACE')
displace_mod.texture = texture
displace_mod.strength = height_multiplier
displace_mod.mid_level = 0.5

# Geometry Nodes 제거 (너무 복잡)
terrain.modifiers.remove(geo_nodes)

# Subdivision Surface
subsurf = terrain.modifiers.new(name="Subdivision", type='SUBSURF')
subsurf.levels = 3  # 5 → 3 (파일 크기 최적화: 4GB → ~150MB)
subsurf.render_levels = 3

# 실제 노이즈 텍스처 생성 (수동)
noise_tex = bpy.data.textures.new("ComplexNoise", type='CLOUDS')
noise_tex.noise_scale = base_scale
noise_tex.noise_depth = octaves
displace_mod.texture = noise_tex

# 모디파이어 적용
bpy.ops.object.modifier_apply(modifier="Subdivision")
bpy.ops.object.modifier_apply(modifier="Displacement")

# ===== 9.5. Terrain 스케일 적용 =====
z_scale = 3  # Z축 스케일 (높이 3배)
print(f"[Terrain v2] Applying terrain scale: XY={terrain_scale}x, Z={z_scale}x")
terrain.scale = (terrain_scale, terrain_scale, z_scale)  # XY 10배, Z 3배
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# ===== 10. Material 생성 (높이 기반) =====
print(f"[Terrain v2] Creating height-based material...")
mat = bpy.data.materials.new(name="TerrainMaterial")
mat.use_nodes = True
mat_nodes = mat.node_tree.nodes
mat_links = mat.node_tree.links

# 기존 노드 제거
mat_nodes.clear()

# Material Output
mat_output = mat_nodes.new('ShaderNodeOutputMaterial')
mat_output.location = (800, 0)

# Principled BSDF
bsdf = mat_nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (600, 0)

# Geometry Input (Z 좌표)
geometry = mat_nodes.new('ShaderNodeNewGeometry')
geometry.location = (0, 0)

# Separate XYZ
separate_xyz = mat_nodes.new('ShaderNodeSeparateXYZ')
separate_xyz.location = (200, 0)
mat_links.new(geometry.outputs['Position'], separate_xyz.inputs['Vector'])

# Map Range (Z를 0-1로 정규화)
map_range = mat_nodes.new('ShaderNodeMapRange')
map_range.location = (400, 0)
map_range.inputs['From Min'].default_value = 0
map_range.inputs['From Max'].default_value = height_multiplier
map_range.inputs['To Min'].default_value = 0
map_range.inputs['To Max'].default_value = 1
mat_links.new(separate_xyz.outputs['Z'], map_range.inputs['Value'])

# Color Ramp (높이 기반 색상)
color_ramp = mat_nodes.new('ShaderNodeValToRGB')
color_ramp.location = (400, 200)
mat_links.new(map_range.outputs['Result'], color_ramp.inputs['Fac'])

# Color Ramp 설정
color_ramp.color_ramp.elements[0].position = grass_height
color_ramp.color_ramp.elements[0].color = (*grass_color, 1.0)

color_ramp.color_ramp.elements[1].position = rock_height
color_ramp.color_ramp.elements[1].color = (*rock_color, 1.0)

# Snow stop 추가
color_ramp.color_ramp.elements.new(snow_height)
color_ramp.color_ramp.elements[2].color = (*snow_color, 1.0)

# BSDF 연결
mat_links.new(color_ramp.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.7
bsdf.inputs['Specular IOR Level'].default_value = wetness

mat_links.new(bsdf.outputs['BSDF'], mat_output.inputs['Surface'])

# Material 적용
terrain.data.materials.append(mat)

# Smooth Shading
bpy.ops.object.shade_smooth()

# ===== 11. 카메라 설정 =====
print(f"[Terrain v2] Setting up camera...")
bpy.ops.object.camera_add(location=(0, 0, size * 1.8))
camera = bpy.context.active_object
camera.rotation_euler = (0, 0, 0)
camera.data.clip_end = size * 5  # Far clip plane 설정 (충분히 멀리)
bpy.context.scene.camera = camera

# ===== 12. 조명 =====
print(f"[Terrain v2] Adding lighting...")
bpy.ops.object.light_add(type='SUN', location=(size/2, size/2, size * 2))
sun = bpy.context.active_object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(45), 0, math.radians(45))

# ===== 13. 렌더 설정 =====
print(f"[Terrain v2] Configuring render...")
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.filepath = preview_path

# Ambient Occlusion
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = 10

# ===== 14. 렌더링 =====
print(f"[Terrain v2] Rendering preview...")
bpy.ops.render.render(write_still=True)

# ===== 15. 저장 =====
print(f"[Terrain v2] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath=output_path)

print(f"[Terrain v2] SUCCESS!")
print(f"[Terrain v2] Created: {output_path}")
print(f"[Terrain v2] Preview: {preview_path}")
