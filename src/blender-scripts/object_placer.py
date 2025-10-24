"""
지형 오브젝트 배치 스크립트 (나무 배치)

Usage:
    blender <road.blend> --background --python object_placer.py -- \
        <biome_maps_dir> <assets_dir> <object_count> <output_blend> <preview_png>

Example:
    blender output/road_123.blend --background --python object_placer.py -- \
        output/biome_terrain_123/biome_maps \
        assets \
        1000 \
        output/road_123.blend \
        output/road_123_preview.png
"""

import bpy
import sys
import os
import math
import random
import mathutils
from PIL import Image

# =============================================================================
# 로그 함수
# =============================================================================

def log(msg):
    """콘솔 출력"""
    print(f"[Object Placer] {msg}")
    sys.stdout.flush()


# =============================================================================
# 1. 커맨드라인 인자 파싱
# =============================================================================

argv = sys.argv
if "--" not in argv:
    log("❌ Usage: blender <road.blend> --background --python object_placer.py -- <biome_maps_dir> <assets_dir> <object_count> <output_blend> <preview_png>")
    sys.exit(1)

argv = argv[argv.index("--") + 1:]
if len(argv) < 5:
    log("❌ Missing arguments")
    sys.exit(1)

BIOME_MAPS_DIR = argv[0]
ASSETS_DIR = argv[1]
OBJECT_COUNT = int(argv[2])
OUTPUT_BLEND = argv[3]
PREVIEW_PATH = argv[4]

log(f"Biome maps: {BIOME_MAPS_DIR}")
log(f"Assets: {ASSETS_DIR}")
log(f"Object count: {OBJECT_COUNT}")
log(f"Output: {OUTPUT_BLEND}")
log(f"Preview: {PREVIEW_PATH}")


# =============================================================================
# 2. Biome Map 이미지 로드
# =============================================================================

def load_biome_maps(biome_maps_dir):
    """
    16bit PNG 바이옴 맵 로드

    Returns:
        {
            'temperature': Image,
            'humidity': Image,
            ...
        }
    """
    log("Loading biome maps...")

    param_names = [
        'temperature', 'humidity', 'erosion', 'continentalness', 'weirdness',
        'vegetation_color_r', 'vegetation_color_g', 'vegetation_color_b',
        'ground_color_r', 'ground_color_g', 'ground_color_b',
        'rock_color_r', 'rock_color_g', 'rock_color_b',
        'snow_start_height', 'rock_exposure'
    ]

    biome_maps = {}
    for param_name in param_names:
        img_path = os.path.join(biome_maps_dir, f'biome_{param_name}.png')
        if not os.path.exists(img_path):
            log(f"⚠️ Missing biome map: {param_name}")
            continue

        img = Image.open(img_path)
        biome_maps[param_name] = img

    log(f"✅ Loaded {len(biome_maps)} biome maps")
    return biome_maps


def read_biome_pixel(biome_maps, param_name, x, y, terrain_size=1000):
    """
    특정 월드 좌표 (x, y)에서 바이옴 파라미터 값 읽기

    Args:
        biome_maps: load_biome_maps() 결과
        param_name: 파라미터 이름 (예: 'temperature')
        x, y: 월드 좌표 (-500~500)
        terrain_size: 지형 크기 (기본 1000m, 바이옴 맵 해상도)

    Returns:
        float: 역정규화된 값 (temperature: -1~1, humidity: 0~1 등)
    """
    if param_name not in biome_maps:
        return 0.0

    img = biome_maps[param_name]
    width, height = img.size

    # 월드 좌표 (-500~500) → 바이옴 맵 좌표 (0~1000) → 이미지 픽셀 좌표
    biome_x = x + 500  # -500~500 → 0~1000
    biome_y = y + 500
    img_x = int((biome_x / terrain_size) * width)
    img_y = int((biome_y / terrain_size) * height)

    # 경계 체크
    img_x = max(0, min(width - 1, img_x))
    img_y = max(0, min(height - 1, img_y))

    # 16bit PNG 픽셀 값 읽기 (0~65535)
    pixel_value = img.getpixel((img_x, img_y))

    # 역정규화
    if param_name in ['temperature', 'continentalness']:
        # -1.0 ~ 1.0
        return (pixel_value / 65535.0) * 2.0 - 1.0
    elif param_name == 'snow_start_height':
        # 0 ~ 5000
        return (pixel_value / 65535.0) * 5000.0
    else:
        # 0.0 ~ 1.0
        return pixel_value / 65535.0


# =============================================================================
# 3. Assets 폴더 스캔
# =============================================================================

def scan_tree_assets(assets_dir):
    """
    assets/objects/tree/ 폴더 스캔

    Returns:
        {
            'general': ['/path/to/tree1/', '/path/to/tree2/', ...],
            'big': [...],
            'tropical': [...],
            'desert': [...]
        }
    """
    log("Scanning tree assets...")

    tree_dir = os.path.join(assets_dir, 'objects', 'tree')
    categories = ['general', 'big', 'tropical', 'desert']

    result = {}
    for category in categories:
        category_path = os.path.join(tree_dir, category)
        if not os.path.exists(category_path):
            result[category] = []
            log(f"⚠️ Category not found: {category}")
            continue

        # 카테고리 폴더 내부의 모든 하위 폴더 수집
        subfolders = [
            os.path.join(category_path, d)
            for d in os.listdir(category_path)
            if os.path.isdir(os.path.join(category_path, d))
        ]
        result[category] = subfolders
        log(f"✅ {category}: {len(subfolders)} folders")

    return result


def find_gltf_in_folder(folder_path):
    """폴더 내부의 첫 번째 .gltf 또는 .glb 파일 찾기"""
    for filename in os.listdir(folder_path):
        if filename.endswith(('.gltf', '.glb')):
            return os.path.join(folder_path, filename)
    return None


# =============================================================================
# 4. 카테고리 결정 로직
# =============================================================================

def determine_tree_category(temperature, humidity, continentalness, erosion, slope_angle):
    """
    바이옴 파라미터 → tree 카테고리 매핑

    Returns:
        'general' | 'big' | 'tropical' | 'desert' | None
    """
    # ❌ 배치 불가 조건
    if continentalness < -0.2:
        return None  # 물 아래

    if slope_angle > 45:
        return None  # 너무 급경사

    # 🌴 tropical (열대: 온도 높음 + 습도 높음)
    if temperature > 0.5 and humidity > 0.6:
        return 'tropical'

    # 🌵 desert (사막: 온도 높음 + 습도 낮음)
    if temperature > 0.5 and humidity < 0.3:
        # 30% 확률로 배치
        return 'desert' if random.random() < 0.3 else None

    # 🌲 big (큰 나무: 평지 + 습함, 낮은 확률)
    if humidity > 0.5 and erosion < 0.3 and slope_angle < 15:
        # 5% 확률로 배치
        if random.random() < 0.05:
            return 'big'

    # 🌳 general (기본 나무: 온대 기후)
    if humidity > 0.4:
        # 70% 확률로 배치
        return 'general' if random.random() < 0.7 else None

    # 기본: 배치 안함
    return None


# =============================================================================
# 5. 도로 충돌 체크
# =============================================================================

def is_too_close_to_road(x, y, road_mesh, min_distance=2.0):
    """
    해당 XY 좌표가 도로와 너무 가까운지 체크

    Args:
        x, y: 월드 좌표
        road_mesh: 도로 메시 오브젝트
        min_distance: 최소 거리 (미터)

    Returns:
        bool: True = 너무 가까움 (배치 불가)
    """
    if road_mesh is None:
        return False

    # 도로 메시의 버텍스와의 최소 거리 계산
    for vert in road_mesh.data.vertices:
        world_pos = road_mesh.matrix_world @ vert.co
        dist_2d = math.sqrt((world_pos.x - x)**2 + (world_pos.y - y)**2)

        if dist_2d < min_distance:
            return True

    return False


# =============================================================================
# 6. GLTF 임포트 및 배치 (캐싱)
# =============================================================================

# GLTF 캐시: {gltf_path: [원본_오브젝트들]}
# 같은 GLTF를 여러 번 임포트하면 용량 폭발 → 한 번만 임포트하고 복사 사용
gltf_cache = {}

def import_and_place_gltf(gltf_path, x, y, z, normal):
    """
    GLTF 파일 임포트 후 지형에 배치 (캐싱 사용으로 용량 최적화)

    Args:
        gltf_path: GLTF 파일 경로
        x, y, z: 월드 좌표
        normal: 법선 벡터 (지형 경사)
    """
    global gltf_cache

    # 캐시 확인: 이미 임포트한 적이 있는가?
    if gltf_path not in gltf_cache:
        # 최초 임포트
        bpy.ops.import_scene.gltf(filepath=gltf_path)

        # 방금 임포트된 오브젝트들 수집
        if len(bpy.context.selected_objects) == 0:
            log(f"⚠️ No objects imported from {gltf_path}")
            return

        imported_objs = list(bpy.context.selected_objects)

        # 캐시에 저장 (원본으로 사용)
        gltf_cache[gltf_path] = imported_objs

        # 원본은 화면 밖으로 숨김
        for obj in imported_objs:
            obj.location = (0, 0, -1000)
            obj.hide_viewport = True
            obj.hide_render = True

    # 캐시된 원본 오브젝트들 중에서 랜덤으로 하나만 선택
    original_objs = gltf_cache[gltf_path]

    # MESH 타입 오브젝트만 필터링 (카메라, 라이트 등 제외)
    mesh_objs = [obj for obj in original_objs if obj.type == 'MESH']

    if len(mesh_objs) == 0:
        log(f"⚠️ No mesh objects in {gltf_path}")
        return

    # 여러 메시 중 랜덤으로 하나 선택
    selected_original = random.choice(mesh_objs)

    # 선택된 오브젝트만 복사 (진짜 인스턴싱)
    imported_obj = selected_original.copy()
    imported_obj.data = selected_original.data  # 메시 데이터 완전 공유 (인스턴싱)
    bpy.context.collection.objects.link(imported_obj)

    # 복사본 보이기
    imported_obj.hide_viewport = False
    imported_obj.hide_render = False

    # 위치 설정
    imported_obj.location = (x, y, z)

    # 법선 벡터에 맞춰 회전 (지형 경사에 정렬)
    z_axis = normal
    x_axis = mathutils.Vector((1, 0, 0))

    # Z축이 수직에 가까우면 기본 회전 사용
    if abs(z_axis.z) > 0.99:
        imported_obj.rotation_euler = (0, 0, 0)
    else:
        y_axis = z_axis.cross(x_axis).normalized()
        x_axis = y_axis.cross(z_axis).normalized()

        rotation_matrix = mathutils.Matrix([
            [x_axis.x, y_axis.x, z_axis.x],
            [x_axis.y, y_axis.y, z_axis.y],
            [x_axis.z, y_axis.z, z_axis.z]
        ]).transposed()

        imported_obj.rotation_euler = rotation_matrix.to_euler()

    # 랜덤 Z축 회전 (나무 방향 다양성)
    imported_obj.rotation_euler.z += random.uniform(0, 2 * math.pi)

    # 랜덤 스케일 (0.8 ~ 1.2배)
    scale_factor = random.uniform(0.8, 1.2)
    imported_obj.scale = (scale_factor, scale_factor, scale_factor)


# =============================================================================
# 7. 메인 실행
# =============================================================================

def main():
    log("========================================")
    log("Starting object placement...")
    log("========================================")

    # 1. Biome maps 로드
    biome_maps = load_biome_maps(BIOME_MAPS_DIR)
    if len(biome_maps) == 0:
        log("❌ No biome maps found")
        sys.exit(1)

    # 2. Assets 스캔
    tree_assets = scan_tree_assets(ASSETS_DIR)
    total_assets = sum(len(folders) for folders in tree_assets.values())
    if total_assets == 0:
        log("❌ No tree assets found")
        sys.exit(1)

    # 3. 지형 및 도로 메시 찾기
    terrain_obj = bpy.data.objects.get("BiomeTerrain")
    if terrain_obj is None:
        log("❌ Terrain object 'BiomeTerrain' not found")
        sys.exit(1)

    road_obj = bpy.data.objects.get("Road")
    if road_obj:
        log(f"✅ Road found: {road_obj.name}")
    else:
        log("⚠️ Road not found, skipping road collision check")

    # 4. Scene, View Layer 및 Depsgraph 가져오기
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # 🔍 디버깅: 지형 경계 정보 출력
    terrain_bounds = terrain_obj.bound_box
    min_x = min([v[0] for v in terrain_bounds])
    max_x = max([v[0] for v in terrain_bounds])
    min_y = min([v[1] for v in terrain_bounds])
    max_y = max([v[1] for v in terrain_bounds])
    min_z = min([v[2] for v in terrain_bounds])
    max_z = max([v[2] for v in terrain_bounds])

    log(f"\n🔍 Terrain bounds (local):")
    log(f"  X: {min_x:.1f} to {max_x:.1f}")
    log(f"  Y: {min_y:.1f} to {max_y:.1f}")
    log(f"  Z: {min_z:.1f} to {max_z:.1f}")
    log(f"  Location: {terrain_obj.location}")
    log(f"  Dimensions: {terrain_obj.dimensions}")

    # 🔍 디버깅: 지형 중심에서 테스트 raycast
    center_x = (min_x + max_x) / 2 + terrain_obj.location.x
    center_y = (min_y + max_y) / 2 + terrain_obj.location.y
    test_origin = mathutils.Vector((center_x, center_y, 2000))
    test_direction = mathutils.Vector((0, 0, -1))

    test_hit, test_loc, test_normal, _, test_obj, _ = scene.ray_cast(
        depsgraph,
        test_origin,
        test_direction
    )

    log(f"\n🔍 Test raycast at terrain center ({center_x:.1f}, {center_y:.1f}, 2000):")
    log(f"  Hit: {test_hit}")
    if test_hit:
        log(f"  Location: {test_loc}")
        log(f"  Object: {test_obj.name if test_obj else 'None'}")

    log(f"\nStarting placement of {OBJECT_COUNT} objects...")

    # 5. 랜덤 좌표 생성 및 오브젝트 배치
    placed_count = 0
    terrain_size = 1000  # 1km (biome map 해상도)

    # 지형의 실제 월드 좌표 범위 (지형은 -500~500 범위에 위치)
    terrain_min = -500
    terrain_max = 500

    # 디버깅 카운터
    debug_stats = {
        'total_attempts': 0,
        'no_hit': 0,
        'too_close_to_road': 0,
        'no_category': 0,
        'no_assets': 0,
        'no_gltf': 0,
        'import_failed': 0,
        'success': 0
    }

    # 목표 개수에 도달할 때까지 계속 시도 (최대 시도 횟수 제한)
    max_attempts = OBJECT_COUNT * 10  # 최대 10배까지 시도
    attempt = 0

    while placed_count < OBJECT_COUNT and attempt < max_attempts:
        attempt += 1

        if attempt % 100 == 0:
            log(f"  Progress: {placed_count}/{OBJECT_COUNT} placed ({attempt} attempts)")

        debug_stats['total_attempts'] += 1

        # 랜덤 XY 좌표 (지형 범위: -500 ~ 500)
        x = random.uniform(terrain_min, terrain_max)
        y = random.uniform(terrain_min, terrain_max)

        # Raycast로 지형 정보 찾기
        origin = mathutils.Vector((x, y, 1000))
        direction = mathutils.Vector((0, 0, -1))

        hit, location, normal, _, obj, _ = scene.ray_cast(
            depsgraph,
            origin,
            direction
        )

        if not hit:
            debug_stats['no_hit'] += 1
            if debug_stats['total_attempts'] <= 10:
                log(f"  Debug [attempt {attempt}]: No raycast hit at ({x:.1f}, {y:.1f})")
            continue  # 지형 없음

        z = location.z

        # 물 위 배치 방지 (z < 0.1)
        if z < 0.1:
            debug_stats['no_hit'] += 1  # 물로 간주
            if debug_stats['total_attempts'] <= 10:
                log(f"  Debug [attempt {attempt}]: Water area at ({x:.1f}, {y:.1f}, z={z:.2f})")
            continue

        slope_angle = math.degrees(math.acos(max(-1, min(1, normal.z))))

        # 도로 충돌 체크
        if is_too_close_to_road(x, y, road_obj, min_distance=2.0):
            debug_stats['too_close_to_road'] += 1
            if debug_stats['total_attempts'] <= 10:
                log(f"  Debug [attempt {attempt}]: Too close to road at ({x:.1f}, {y:.1f})")
            continue

        # Biome 파라미터 읽기
        temperature = read_biome_pixel(biome_maps, 'temperature', x, y, terrain_size)
        humidity = read_biome_pixel(biome_maps, 'humidity', x, y, terrain_size)
        continentalness = read_biome_pixel(biome_maps, 'continentalness', x, y, terrain_size)
        erosion = read_biome_pixel(biome_maps, 'erosion', x, y, terrain_size)

        # 카테고리 결정
        category = determine_tree_category(
            temperature, humidity, continentalness, erosion, slope_angle
        )

        if category is None:
            debug_stats['no_category'] += 1
            if debug_stats['total_attempts'] <= 10:
                log(f"  Debug [attempt {attempt}]: No category (temp={temperature:.2f}, hum={humidity:.2f}, cont={continentalness:.2f}, slope={slope_angle:.1f}°)")
            continue  # 배치 안함

        # 해당 카테고리의 랜덤 폴더 선택
        if category not in tree_assets or len(tree_assets[category]) == 0:
            debug_stats['no_assets'] += 1
            log(f"  Debug [attempt {attempt}]: No assets for category '{category}'")
            continue

        tree_folder = random.choice(tree_assets[category])

        # 폴더 내부의 GLTF 파일 찾기
        gltf_file = find_gltf_in_folder(tree_folder)
        if gltf_file is None:
            debug_stats['no_gltf'] += 1
            log(f"  Debug [attempt {attempt}]: No GLTF in folder {tree_folder}")
            continue

        # GLTF 임포트 및 배치
        try:
            import_and_place_gltf(gltf_file, x, y, z, normal)
            debug_stats['success'] += 1
            placed_count += 1
            if placed_count <= 5:
                log(f"  ✅ Placed {category} at ({x:.1f}, {y:.1f}, {z:.1f}) [#{placed_count}]")
        except Exception as e:
            debug_stats['import_failed'] += 1
            log(f"  ⚠️ Failed to place object: {e}")
            continue

    # 디버깅 통계 출력
    log(f"\n📊 Debug Statistics:")
    log(f"  Total attempts: {debug_stats['total_attempts']}")
    log(f"  No raycast hit: {debug_stats['no_hit']}")
    log(f"  Too close to road: {debug_stats['too_close_to_road']}")
    log(f"  No category (biome rules): {debug_stats['no_category']}")
    log(f"  No assets for category: {debug_stats['no_assets']}")
    log(f"  No GLTF file found: {debug_stats['no_gltf']}")
    log(f"  Import failed: {debug_stats['import_failed']}")
    log(f"  Success: {debug_stats['success']}")

    # 목표 달성 여부 확인
    if placed_count >= OBJECT_COUNT:
        log(f"\n✅ Placement complete: {placed_count}/{OBJECT_COUNT} objects placed ({attempt} attempts)")
    else:
        log(f"\n⚠️ Placement incomplete: {placed_count}/{OBJECT_COUNT} objects placed (reached max attempts: {attempt})")
        log(f"   Consider adjusting biome rules or increasing max_attempts multiplier")

    # 6. Blend 파일 저장 (압축 활성화)
    log(f"Saving blend file: {OUTPUT_BLEND}")
    bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND, compress=True)
    log("✅ Blend file saved (compressed)")

    # 7. .blend1 백업 파일 삭제
    blend1_path = OUTPUT_BLEND + "1"
    if os.path.exists(blend1_path):
        try:
            os.remove(blend1_path)
            log(f"🗑️ Removed backup file: {blend1_path}")
        except Exception as e:
            log(f"⚠️ Failed to remove backup file: {e}")

    # 8. 미리보기 렌더링
    log(f"Rendering preview: {PREVIEW_PATH}")
    scene.render.filepath = PREVIEW_PATH
    scene.camera.location = (500, 500, 800)
    scene.camera.rotation_euler = (0, 0, 0)
    bpy.ops.render.render(write_still=True)
    log("✅ Preview rendered")

    log("========================================")
    log(f"Object placement finished: {placed_count} objects")
    log("========================================")


if __name__ == "__main__":
    main()
