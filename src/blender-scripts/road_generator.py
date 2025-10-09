import bpy  # type: ignore
import bmesh  # type: ignore
import mathutils  # type: ignore
import sys
import json
import math
import os

# 커맨드 라인 인자 파싱
# blender --background --python road_generator.py -- params.json terrain.blend output.blend preview.png
args = sys.argv[sys.argv.index("--") + 1 :]
params_file = os.path.abspath(args[0])
terrain_blend_path = os.path.abspath(args[1])
output_path = os.path.abspath(args[2])
preview_path = os.path.abspath(args[3])

# 파라미터 파일 읽기
with open(params_file, "r") as f:
    params = json.load(f)

control_points = params.get("controlPoints", [])
road_width = params.get("width", 1.6)  # 기본 1.6m (1차선)

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
    if obj.type == "MESH" and "Terrain" in obj.name:
        terrain_obj = obj
        break

if not terrain_obj:
    print(f"[Road] ERROR: Terrain object not found!")
    sys.exit(1)

print(f"[Road] Found terrain: {terrain_obj.name}")

# 2. Bezier Curve 생성
print(f"[Road] Creating road curve...")
curve_data = bpy.data.curves.new("RoadCurve", type="CURVE")
curve_data.dimensions = "3D"

# Spline 생성
spline = curve_data.splines.new("BEZIER")
spline.bezier_points.add(len(control_points) - 1)  # 첫 포인트는 이미 있음

# Control points 설정 및 도로 길이 계산
total_length = 0.0
converted_points = []

for i, point in enumerate(control_points):
    # 좌표 변환: 웹 좌표 -> Blender 좌표 (중앙 기준)
    # Terrain 크기: 1000m (1km) → 좌표 범위: 0-100 → -500~500
    if isinstance(point, dict):
        x = (point["x"] - 50) * 10  # 0-100 -> -500~500 (10배 스케일)
        y = (point["y"] - 50) * 10
    else:  # list 또는 tuple
        x = (point[0] - 50) * 10
        y = (point[1] - 50) * 10

    converted_points.append((x, y))

    # 이전 포인트와의 거리 계산
    if i > 0:
        prev_x, prev_y = converted_points[i - 1]
        segment_length = math.sqrt((x - prev_x) ** 2 + (y - prev_y) ** 2)
        total_length += segment_length

print(f"[Road] Total road length: {total_length:.1f}m")

# Control points를 Bezier curve에 설정
# Z 좌표를 높게 설정 (투영을 위해)
start_z = 10000  # 10km 높이에서 시작 (어떤 지형보다 높음)
for i, (x, y) in enumerate(converted_points):
    bp = spline.bezier_points[i]
    bp.co = (x, y, start_z)  # 높은 곳에서 시작
    bp.handle_left_type = "AUTO"
    bp.handle_right_type = "AUTO"

# Curve Object 생성
curve_obj = bpy.data.objects.new("Road", curve_data)
bpy.context.collection.objects.link(curve_obj)

# 3. 동적 Curve 해상도 계산 (도로 길이 기반)
# 목표: 2m당 1개 샘플 (1km 도로 = 500 샘플)
target_resolution = int(total_length / 2.0)
resolution_u = max(32, min(target_resolution, 512))  # 32~512 범위
bevel_resolution = max(4, min(int(resolution_u / 64), 8))  # 4~8 범위

print(f"[Road] Dynamic resolution: {resolution_u} (length-based)")
curve_data.resolution_u = resolution_u
curve_data.bevel_resolution = bevel_resolution

# 4. Curve 두께 설정 (Bevel) - 평면 도로용 커스텀 프로필
print(f"[Road] Setting road width: {road_width}m")

# Bevel Object: 평면 선 프로필 생성 (11점 → 10 segments)
bevel_curve_data = bpy.data.curves.new("RoadProfile", type="CURVE")
bevel_curve_data.dimensions = "2D"
bevel_spline = bevel_curve_data.splines.new("POLY")
num_segments = 10  # 도로 폭 방향 세그먼트 수
bevel_spline.points.add(num_segments)  # 11개 점 (10 segments)

# 선 프로필 좌표 (X축 방향 평면, 균등 분할)
half_width = road_width / 2
for i in range(num_segments + 1):
    x = -half_width + (i * road_width / num_segments)
    bevel_spline.points[i].co = (x, 0, 0, 1)
bevel_spline.use_cyclic_u = False  # 열린 선

bevel_obj = bpy.data.objects.new("RoadProfile", bevel_curve_data)
bpy.context.collection.objects.link(bevel_obj)

# Curve에 bevel object 할당
curve_data.bevel_mode = "OBJECT"
curve_data.bevel_object = bevel_obj
curve_data.use_fill_caps = False  # 평면이므로 cap 불필요

print(f"[Road] Using flat bevel profile (2 points)")

# 5. Shrinkwrap Modifier (하늘에서 지형으로 투영)
print(f"[Road] Adding shrinkwrap modifier...")
modifier = curve_obj.modifiers.new("Shrinkwrap", "SHRINKWRAP")
modifier.target = terrain_obj
modifier.wrap_method = "PROJECT"  # PROJECT 방식
modifier.use_project_z = True
modifier.use_negative_direction = True  # 아래로만 투영 (Z=10000 → 지형)
modifier.use_positive_direction = False  # 위로는 투영 안함
modifier.offset = 0.05  # 지형 위 20cm

# 6. Curve를 Mesh로 변환 (UV 좌표 자동 생성됨)
print(f"[Road] Converting curve to mesh...")
bpy.context.view_layer.objects.active = curve_obj
curve_obj.select_set(True)
bpy.ops.object.convert(target="MESH")
print(f"[Road] Curve converted to mesh with auto-generated UV")

# 변환 후 active object 재설정
bpy.context.view_layer.objects.active = curve_obj
mesh = curve_obj.data

# 7. UV 좌표 조정: 90도 회전 + Y축 동적 스케일
# 동적 스케일 계산: 도로 길이 기반
# 기준: 1966.8m → 200x 스케일 (텍스처 반복)
# 공식: scale = (total_length / 10.0) → 도로 10m당 텍스처 1회 반복
y_scale_factor = total_length / 10.0 * 3.0

print(
    f"[Road] Adjusting UV coordinates (rotate 90° + scale Y {y_scale_factor:.1f}x)..."
)
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(mesh)
uv_layer = bm.loops.layers.uv.active

if uv_layer:
    # 모든 UV 좌표에 대해 변환 적용
    for face in bm.faces:
        for loop in face.loops:
            uv = loop[uv_layer].uv
            u, v = uv.x, uv.y

            # 90도 회전: (u, v) -> (-v, u)
            # 그리고 Y축 동적 스케일 (도로 길이 기반)
            uv.x = -v
            uv.y = u * y_scale_factor

    bmesh.update_edit_mesh(mesh)
    print(f"[Road] UV rotated 90° and scaled Y by {y_scale_factor:.1f}x (dynamic)")

bm.free()
bpy.ops.object.mode_set(mode="OBJECT")

# 8. 이미지 텍스처 기반 도로 Material 생성
print(f"[Road] Creating texture-based road material...")
mat = bpy.data.materials.new(name="RoadMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# 기존 노드 제거
nodes.clear()

# === Output 노드 ===
mat_output = nodes.new("ShaderNodeOutputMaterial")
mat_output.location = (600, 0)

# === Principled BSDF ===
bsdf = nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (400, 0)
links.new(bsdf.outputs["BSDF"], mat_output.inputs["Surface"])

# === Texture Coordinate (UV 사용) ===
tex_coord = nodes.new("ShaderNodeTexCoord")
tex_coord.location = (-400, 0)

# === Image Texture (도로 텍스처) ===
texture_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "assets",
    "roadtexture.jpg",
)
texture_path = os.path.abspath(texture_path)
print(f"[Road] Loading texture: {texture_path}")

if os.path.exists(texture_path):
    # 이미지 로드
    img = bpy.data.images.load(texture_path)
    img_texture = nodes.new("ShaderNodeTexImage")
    img_texture.image = img
    img_texture.location = (-200, 0)

    # UV Coordinate → Image Texture (Mapping 노드 없이 직접 연결)
    links.new(tex_coord.outputs["UV"], img_texture.inputs["Vector"])

    # BSDF에 연결
    links.new(img_texture.outputs["Color"], bsdf.inputs["Base Color"])
    print(f"[Road] Texture loaded successfully (no mapping node)")
else:
    print(f"[Road] WARNING: Texture not found at {texture_path}")
    # 기본 회색으로 설정
    bsdf.inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1.0)

# 도로 재질 속성
bsdf.inputs["Roughness"].default_value = 0.85  # 거친 아스팔트
bsdf.inputs["Specular IOR Level"].default_value = 0.3  # 약간의 반사

print(f"[Road] Material created")

# Material 할당
if curve_obj.data.materials:
    curve_obj.data.materials[0] = mat
else:
    curve_obj.data.materials.append(mat)

# 9. Top View 렌더링
print(f"[Road] Rendering top view...")
bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
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
camera.data.clip_end = 10000  # 충분히 멀리

bpy.ops.render.render(write_still=True)

# 10. .blend 파일 저장
print(f"[Road] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath=output_path)

print(f"[Road] SUCCESS: Road created at {output_path}")
print(f"[Road] Preview saved to {preview_path}")
