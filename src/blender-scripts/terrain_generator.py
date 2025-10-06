import bpy
import sys
import json
import math

# 커맨드 라인 인자 파싱
# blender --background --python terrain_generator.py -- params.json output.blend preview.png
args = sys.argv[sys.argv.index("--") + 1:]
params_file = args[0]
output_path = args[1]
preview_path = args[2]

# 파라미터 파일 읽기
with open(params_file, 'r') as f:
    params = json.load(f)

print(f"[Terrain] Parameters: {params}")
print(f"[Terrain] Output: {output_path}")
print(f"[Terrain] Preview: {preview_path}")

# 기존 오브젝트 삭제
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 기본 파라미터
scale = params.get('scale', 15)
roughness = params.get('roughness', 0.7)
size = params.get('size', 100)  # 100m x 100m

print(f"[Terrain] Creating plane: {size}m x {size}m")

# 1. Plane 생성
bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
plane = bpy.context.active_object
plane.name = "Terrain"

# 2. Subdivision Surface Modifier (더 많은 버텍스)
print(f"[Terrain] Adding subdivision...")
subsurf = plane.modifiers.new(name="Subdivision", type='SUBSURF')
subsurf.levels = 6  # 뷰포트 레벨
subsurf.render_levels = 6

# 3. Displace Modifier (Noise Texture로 지형 생성)
print(f"[Terrain] Adding displacement with scale={scale}, roughness={roughness}")
displace = plane.modifiers.new(name="Displace", type='DISPLACE')

# Noise Texture 생성
texture = bpy.data.textures.new("TerrainNoise", type='CLOUDS')
texture.noise_scale = scale
texture.noise_depth = 8
texture.cloud_type = 'GRAYSCALE'

displace.texture = texture
displace.strength = roughness * 10  # 높이 조절
displace.mid_level = 0.5

# 4. Smooth Shading
print(f"[Terrain] Applying smooth shading...")
bpy.ops.object.shade_smooth()

# 5. 카메라 설정 (Top View)
print(f"[Terrain] Setting up camera...")
bpy.ops.object.camera_add(location=(0, 0, size * 1.5))
camera = bpy.context.active_object
camera.rotation_euler = (0, 0, 0)
bpy.context.scene.camera = camera

# 6. 조명 추가
print(f"[Terrain] Adding light...")
bpy.ops.object.light_add(type='SUN', location=(size/2, size/2, size))
light = bpy.context.active_object
light.data.energy = 2.0

# 7. 렌더 설정
print(f"[Terrain] Configuring render settings...")
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = preview_path

# 8. Top View 렌더링
print(f"[Terrain] Rendering top view...")
bpy.ops.render.render(write_still=True)

# 9. .blend 파일 저장
print(f"[Terrain] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath=output_path)

print(f"[Terrain] SUCCESS: Created terrain at {output_path}")
print(f"[Terrain] Preview saved to {preview_path}")
