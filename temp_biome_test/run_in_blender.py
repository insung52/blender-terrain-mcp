
import bpy
import os

# === 1. 기존 객체 삭제 ===
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# === 2. 100x100 그리드 메시 생성 ===
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=100,
    y_subdivisions=100,
    size=100,
    location=(0, 0, 0)
)

terrain_obj = bpy.context.active_object
terrain_obj.name = "BiomeTerrain"

# === 3. 바이옴 이미지 로드 ===
image_dir = r"C:\graphics\buildup\blender-terrain-mcp\temp_biome_test\biome_maps"
param_names = [
    'temperature', 'humidity', 'erosion', 'continentalness', 'weirdness',
    'vegetation_color_r', 'vegetation_color_g', 'vegetation_color_b',
    'ground_color_r', 'ground_color_g', 'ground_color_b',
    'snow_start_height', 'rock_exposure'
]

loaded_images = {}
for param_name in param_names:
    img_path = os.path.join(image_dir, f'biome_{param_name}.png')
    if os.path.exists(img_path):
        img = bpy.data.images.load(img_path)
        img.name = f'biome_{param_name}'
        loaded_images[param_name] = img
        print(f'✅ Loaded: {img_path}')
    else:
        print(f'❌ Not found: {img_path}')

# === 4. Geometry Nodes Modifier 추가 ===
# (추후 구현: Image Texture 샘플링 → Set Position)
modifier = terrain_obj.modifiers.new(name="BiomeTerrainGenerator", type='NODES')

# TODO: Geometry Nodes 그래프 프로그래밍 방식으로 생성
# 현재는 수동으로 Geometry Nodes 설정 필요

# === 5. .blend 파일 저장 ===
bpy.ops.wm.save_as_mainfile(filepath=r"C:\graphics\buildup\blender-terrain-mcp\temp_biome_test\biome_terrain.blend")
print(f'✅ Saved: C:\graphics\buildup\blender-terrain-mcp\temp_biome_test\biome_terrain.blend')
