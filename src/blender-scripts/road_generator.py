import bpy
import sys
import json
import math
import os

# 커맨드 라인 인자 파싱
# blender --background --python road_generator.py -- params.json terrain.blend output.blend preview.png
args = sys.argv[sys.argv.index("--") + 1:]
params_file = os.path.abspath(args[0])
terrain_blend_path = os.path.abspath(args[1])
output_path = os.path.abspath(args[2])
preview_path = os.path.abspath(args[3])

# 파라미터 파일 읽기
with open(params_file, 'r') as f:
    params = json.load(f)

control_points = params.get('controlPoints', [])
road_width = params.get('width', 1.6)  # 기본 1.6m (1차선)

print(f"[Road] Parameters: {params}")
print(f"[Road] Control points: {len(control_points)}")
print(f"[Road] Terrain file: {terrain_blend_path}")
print(f"[Road] Output: {output_path}")

# 1. Terrain 파일 로드
print(f"[Road] Loading terrain file...")
bpy.ops.wm.open_mainfile(filepath=terrain_blend_path)

# Terrain 오브젝트 찾기
terrain_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and 'Terrain' in obj.name:
        terrain_obj = obj
        break

if not terrain_obj:
    print(f"[Road] ERROR: Terrain object not found!")
    sys.exit(1)

print(f"[Road] Found terrain: {terrain_obj.name}")

# 2. Bezier Curve 생성
print(f"[Road] Creating road curve...")
curve_data = bpy.data.curves.new('RoadCurve', type='CURVE')
curve_data.dimensions = '3D'

# Spline 생성
spline = curve_data.splines.new('BEZIER')
spline.bezier_points.add(len(control_points) - 1)  # 첫 포인트는 이미 있음

# Control points 설정 및 도로 길이 계산
total_length = 0.0
converted_points = []

for i, point in enumerate(control_points):
    # 좌표 변환: 웹 좌표 -> Blender 좌표 (중앙 기준)
    # Terrain 크기: 1000m (1km) → 좌표 범위: 0-100 → -500~500
    if isinstance(point, dict):
        x = (point['x'] - 50) * 10  # 0-100 -> -500~500 (10배 스케일)
        y = (point['y'] - 50) * 10
    else:  # list 또는 tuple
        x = (point[0] - 50) * 10
        y = (point[1] - 50) * 10

    converted_points.append((x, y))

    # 이전 포인트와의 거리 계산
    if i > 0:
        prev_x, prev_y = converted_points[i-1]
        segment_length = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        total_length += segment_length

print(f"[Road] Total road length: {total_length:.1f}m")

# Control points를 Bezier curve에 설정
# Z 좌표를 높게 설정 (투영을 위해)
start_z = 10000  # 10km 높이에서 시작 (어떤 지형보다 높음)
for i, (x, y) in enumerate(converted_points):
    bp = spline.bezier_points[i]
    bp.co = (x, y, start_z)  # 높은 곳에서 시작
    bp.handle_left_type = 'AUTO'
    bp.handle_right_type = 'AUTO'

# Curve Object 생성
curve_obj = bpy.data.objects.new('Road', curve_data)
bpy.context.collection.objects.link(curve_obj)

# 3. 동적 Curve 해상도 계산 (도로 길이 기반)
# 목표: 2m당 1개 샘플 (1km 도로 = 500 샘플)
target_resolution = int(total_length / 2.0)
resolution_u = max(32, min(target_resolution, 512))  # 32~512 범위
bevel_resolution = max(4, min(int(resolution_u / 64), 8))  # 4~8 범위

print(f"[Road] Dynamic resolution: {resolution_u} (length-based)")
curve_data.resolution_u = resolution_u
curve_data.bevel_resolution = bevel_resolution

# 4. Curve 두께 설정 (Bevel)
print(f"[Road] Setting road width: {road_width}m")
curve_data.bevel_depth = road_width / 2  # 반지름

# 5. Shrinkwrap Modifier (하늘에서 지형으로 투영)
print(f"[Road] Adding shrinkwrap modifier...")
modifier = curve_obj.modifiers.new('Shrinkwrap', 'SHRINKWRAP')
modifier.target = terrain_obj
modifier.wrap_method = 'PROJECT'  # PROJECT 방식
modifier.use_project_z = True
modifier.use_negative_direction = True  # 아래로만 투영 (Z=10000 → 지형)
modifier.use_positive_direction = False  # 위로는 투영 안함
modifier.offset = 0.2  # 지형 위 20cm

# 5. Procedural 도로 Material 생성 (아스팔트 + 차선 + 균열)
print(f"[Road] Creating procedural road material...")
mat = bpy.data.materials.new(name="RoadMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# 기존 노드 제거
nodes.clear()

# === Output 노드 ===
mat_output = nodes.new('ShaderNodeOutputMaterial')
mat_output.location = (1200, 0)

# === Principled BSDF ===
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (1000, 0)
links.new(bsdf.outputs['BSDF'], mat_output.inputs['Surface'])

# === Texture Coordinate (도로 방향 따라 UV) ===
tex_coord = nodes.new('ShaderNodeTexCoord')
tex_coord.location = (-800, 0)

# === 1. 아스팔트 베이스 (Noise Texture) ===
noise_asphalt = nodes.new('ShaderNodeTexNoise')
noise_asphalt.location = (-600, 300)
noise_asphalt.inputs['Scale'].default_value = 50  # 미세한 질감
noise_asphalt.inputs['Detail'].default_value = 10
noise_asphalt.inputs['Roughness'].default_value = 0.7
links.new(tex_coord.outputs['Generated'], noise_asphalt.inputs['Vector'])

# ColorRamp (어두운 회색 범위)
ramp_asphalt = nodes.new('ShaderNodeValToRGB')
ramp_asphalt.location = (-400, 300)
ramp_asphalt.color_ramp.elements[0].position = 0.4
ramp_asphalt.color_ramp.elements[0].color = (0.08, 0.08, 0.08, 1.0)  # 진한 회색
ramp_asphalt.color_ramp.elements[1].position = 0.6
ramp_asphalt.color_ramp.elements[1].color = (0.12, 0.12, 0.12, 1.0)  # 밝은 회색
links.new(noise_asphalt.outputs['Fac'], ramp_asphalt.inputs['Fac'])

# === 2. 차선 (Generated Y축 기반) ===
separate_xyz = nodes.new('ShaderNodeSeparateXYZ')
separate_xyz.location = (-600, 0)
links.new(tex_coord.outputs['Generated'], separate_xyz.inputs['Vector'])

# Y좌표를 이용한 반복 패턴 (차선)
math_multiply = nodes.new('ShaderNodeMath')
math_multiply.operation = 'MULTIPLY'
math_multiply.location = (-400, 0)
math_multiply.inputs[1].default_value = 40  # 차선 반복 빈도
links.new(separate_xyz.outputs['Y'], math_multiply.inputs[0])

# Modulo로 반복
math_modulo = nodes.new('ShaderNodeMath')
math_modulo.operation = 'MODULO'
math_modulo.location = (-200, 0)
math_modulo.inputs[1].default_value = 1.0
links.new(math_multiply.outputs['Value'], math_modulo.inputs[0])

# ColorRamp (차선 폭 조절)
ramp_lane = nodes.new('ShaderNodeValToRGB')
ramp_lane.location = (0, 0)
ramp_lane.color_ramp.elements[0].position = 0.45
ramp_lane.color_ramp.elements[0].color = (0, 0, 0, 1)  # 아스팔트
ramp_lane.color_ramp.elements[1].position = 0.50
ramp_lane.color_ramp.elements[1].color = (0.9, 0.9, 0.0, 1)  # 노란 차선
links.new(math_modulo.outputs['Value'], ramp_lane.inputs['Fac'])

# === 3. 균열 (Voronoi Crack) ===
voronoi = nodes.new('ShaderNodeTexVoronoi')
voronoi.location = (-600, -300)
voronoi.voronoi_dimensions = '3D'
voronoi.feature = 'DISTANCE_TO_EDGE'
voronoi.inputs['Scale'].default_value = 5  # 균열 밀도
links.new(tex_coord.outputs['Generated'], voronoi.inputs['Vector'])

# ColorRamp (균열을 검은 선으로)
ramp_crack = nodes.new('ShaderNodeValToRGB')
ramp_crack.location = (-400, -300)
ramp_crack.color_ramp.elements[0].position = 0.05
ramp_crack.color_ramp.elements[0].color = (0.05, 0.05, 0.05, 1.0)  # 검은 균열
ramp_crack.color_ramp.elements[1].position = 0.1
ramp_crack.color_ramp.elements[1].color = (1, 1, 1, 1)  # 투명
links.new(voronoi.outputs['Distance'], ramp_crack.inputs['Fac'])

# === 4. 모든 요소 Mix ===
# Mix 1: 아스팔트 + 차선
mix_lane = nodes.new('ShaderNodeMix')
mix_lane.data_type = 'RGBA'
mix_lane.location = (200, 150)
links.new(ramp_asphalt.outputs['Color'], mix_lane.inputs['A'])
links.new(ramp_lane.outputs['Color'], mix_lane.inputs['B'])
links.new(ramp_lane.outputs['Alpha'], mix_lane.inputs['Factor'])

# Mix 2: (아스팔트+차선) + 균열
mix_final = nodes.new('ShaderNodeMix')
mix_final.data_type = 'RGBA'
mix_final.location = (400, 150)
mix_final.inputs['Factor'].default_value = 0.3  # 균열 강도
links.new(mix_lane.outputs['Result'], mix_final.inputs['A'])
links.new(ramp_crack.outputs['Color'], mix_final.inputs['B'])

# === 5. Principled BSDF 연결 ===
links.new(mix_final.outputs['Result'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.85  # 거친 아스팔트
bsdf.inputs['Specular IOR Level'].default_value = 0.3  # 약간의 반사

print(f"[Road] Procedural material created: asphalt + lanes + cracks")

# Material 할당
if curve_obj.data.materials:
    curve_obj.data.materials[0] = mat
else:
    curve_obj.data.materials.append(mat)

# 6. Top View 렌더링
print(f"[Road] Rendering top view...")
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = preview_path

# 카메라가 이미 있는지 확인 (terrain 파일에서 로드된 경우 이미 존재)
camera = bpy.context.scene.camera
if not camera:
    # Terrain 크기: 1000m → 카메라 높이: 1800m
    bpy.ops.object.camera_add(location=(0, 0, 1800))
    camera = bpy.context.active_object
    camera.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = camera

# Far clip plane 설정 (기존 카메라든 새 카메라든 모두 적용)
camera.data.clip_end = 5000  # 충분히 멀리

bpy.ops.render.render(write_still=True)

# 7. .blend 파일 저장
print(f"[Road] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath=output_path)

print(f"[Road] SUCCESS: Road created at {output_path}")
print(f"[Road] Preview saved to {preview_path}")
