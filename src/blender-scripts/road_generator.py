import bpy
import sys
import json
import math

# 커맨드 라인 인자 파싱
# blender --background --python road_generator.py -- params.json terrain.blend output.blend preview.png
args = sys.argv[sys.argv.index("--") + 1:]
params_file = args[0]
terrain_blend_path = args[1]
output_path = args[2]
preview_path = args[3]

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

# Control points 설정 (x, y 좌표, z는 0으로 시작)
for i, point in enumerate(control_points):
    bp = spline.bezier_points[i]
    # 좌표 변환: 웹 좌표 -> Blender 좌표 (중앙 기준)
    x = point['x'] - 50  # 0-100 -> -50~50
    y = point['y'] - 50
    bp.co = (x, y, 0)
    bp.handle_left_type = 'AUTO'
    bp.handle_right_type = 'AUTO'

# Curve Object 생성
curve_obj = bpy.data.objects.new('Road', curve_data)
bpy.context.collection.objects.link(curve_obj)

# 3. Curve 두께 설정 (Bevel)
print(f"[Road] Setting road width: {road_width}m")
curve_data.bevel_depth = road_width / 2  # 반지름

# 4. Shrinkwrap Modifier (지형에 맞춤)
print(f"[Road] Adding shrinkwrap modifier...")
modifier = curve_obj.modifiers.new('Shrinkwrap', 'SHRINKWRAP')
modifier.target = terrain_obj
modifier.wrap_method = 'PROJECT'
modifier.use_project_z = True
modifier.use_negative_direction = True
modifier.offset = 0.1  # 지형 위 10cm

# 5. Material 추가 (간단한 회색 아스팔트)
print(f"[Road] Adding material...")
mat = bpy.data.materials.new(name="RoadMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.2, 0.2, 0.2, 1.0)  # 회색
    bsdf.inputs['Roughness'].default_value = 0.8

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

# 카메라가 이미 있는지 확인
if not bpy.context.scene.camera:
    bpy.ops.object.camera_add(location=(0, 0, 100))
    camera = bpy.context.active_object
    camera.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = camera

bpy.ops.render.render(write_still=True)

# 7. .blend 파일 저장
print(f"[Road] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath=output_path)

print(f"[Road] SUCCESS: Road created at {output_path}")
print(f"[Road] Preview saved to {preview_path}")
