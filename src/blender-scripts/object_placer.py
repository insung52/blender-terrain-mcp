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
import json

# 🐛 DEBUG MODE: True이면 모든 시도마다 상세 로그 출력
DEBUG_MODE = True

# 🔧 Pillow가 user site-packages에 설치되어 있는 경우 경로 추가
user_site_packages = os.path.expanduser(
    "~\\AppData\\Roaming\\Python\\Python311\\site-packages"
)
if os.path.exists(user_site_packages) and user_site_packages not in sys.path:
    sys.path.append(user_site_packages)

from PIL import Image

# =============================================================================
# 로그 함수
# =============================================================================

# 로그 파일 핸들러 (전역)
log_file = None


def init_log_file(output_blend_path):
    """로그 파일 초기화"""
    global log_file
    # output_blend 파일 이름에서 로그 파일명 생성
    log_path = output_blend_path.replace('.blend', '_log.txt')
    log_file = open(log_path, 'w', encoding='utf-8')
    log(f"Log file created: {log_path}")


def close_log_file():
    """로그 파일 닫기"""
    global log_file
    if log_file:
        log_file.close()
        log_file = None


def log(msg):
    """콘솔 및 파일 출력 (실시간)"""
    log_msg = f"[Object Placer] {msg}"

    # 콘솔 출력
    print(log_msg)
    sys.stdout.flush()

    # 파일 출력 (실시간)
    if log_file:
        log_file.write(log_msg + "\n")
        log_file.flush()  # 즉시 디스크에 기록


# =============================================================================
# 1. 커맨드라인 인자 파싱
# =============================================================================

argv = sys.argv
if "--" not in argv:
    log(
        "❌ Usage: blender <road.blend> --background --python object_placer.py -- <biome_maps_dir> <assets_dir> <object_count> <output_blend> <preview_png>"
    )
    sys.exit(1)

argv = argv[argv.index("--") + 1 :]
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
log(f"🐛 DEBUG MODE: {DEBUG_MODE}")


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
        "temperature",
        "humidity",
        "erosion",
        "continentalness",
        "weirdness",
        "vegetation_color_r",
        "vegetation_color_g",
        "vegetation_color_b",
        "ground_color_r",
        "ground_color_g",
        "ground_color_b",
        "rock_color_r",
        "rock_color_g",
        "rock_color_b",
        "snow_start_height",
        "rock_exposure",
    ]

    biome_maps = {}
    for param_name in param_names:
        img_path = os.path.join(biome_maps_dir, f"biome_{param_name}.png")
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
    # Y축 반전: 월드 +y(위) → 이미지 0(위), 월드 -y(아래) → 이미지 999(아래)
    img_y = height - 1 - int((biome_y / terrain_size) * height)

    # 경계 체크
    img_x = max(0, min(width - 1, img_x))
    img_y = max(0, min(height - 1, img_y))

    # 16bit PNG 픽셀 값 읽기 (0~65535)
    pixel_value = img.getpixel((img_x, img_y))

    # 역정규화
    if param_name in ["temperature", "continentalness"]:
        # -1.0 ~ 1.0
        normalized_value = (pixel_value / 65535.0) * 2.0 - 1.0
    elif param_name == "snow_start_height":
        # 0 ~ 5000
        normalized_value = (pixel_value / 65535.0) * 5000.0
    else:
        # 0.0 ~ 1.0
        normalized_value = pixel_value / 65535.0

    # 🐛 DEBUG: 픽셀 읽기 상세 정보
    if DEBUG_MODE and param_name in ["temperature", "humidity"]:
        log(f"    🔍 read_biome_pixel({param_name}): world({x:.1f}, {y:.1f}) → img({img_x}, {img_y}) → raw={pixel_value} → value={normalized_value:.3f}")

    return normalized_value


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

    tree_dir = os.path.join(assets_dir, "objects", "tree")
    categories = ["general", "big", "tropical", "desert"]

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
        if filename.endswith((".gltf", ".glb")):
            return os.path.join(folder_path, filename)
    return None


# =============================================================================
# 4. 나무 선택 로직 (확률 가중치 기반)
# =============================================================================


def load_object_spawn_config(script_dir):
    """오브젝트 spawn 설정 파일 로드 (나무, 꽃, 바위 등)"""
    config_path = os.path.join(script_dir, "object_spawn_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_object_type(spawn_config):
    """
    타입별 가중치로 오브젝트 타입 선택 (trees, flowers, rocks 등)

    Returns:
        str: 선택된 타입 키 (예: 'trees', 'flowers')
    """
    types = []
    weights = []

    for obj_type, config in spawn_config.items():
        if "type_weight" in config:
            types.append(obj_type)
            weights.append(config["type_weight"])

    if not types:
        return None

    total_weight = sum(weights)
    if total_weight <= 0:
        return None

    rand_value = random.random() * total_weight
    cumulative = 0

    for obj_type, weight in zip(types, weights):
        cumulative += weight
        if rand_value <= cumulative:
            return obj_type

    return types[0]  # fallback


def is_in_range(value, range_tuple):
    """값이 범위 내에 있는지 확인"""
    min_val, max_val = range_tuple
    return min_val <= value <= max_val


def calculate_vegetation_density(
    temperature, humidity, continentalness, erosion, slope_angle
):
    """
    바이옴 파라미터를 기반으로 식생 밀도를 계산 (0.0 ~ 1.0)

    이 함수는 나무 배치 확률을 결정합니다.
    나중에 공식을 쉽게 조정할 수 있도록 별도 함수로 분리되었습니다.

    Args:
        temperature: -1 ~ 1 (낮음 = 추움, 높음 = 더움)
        humidity: 0 ~ 1 (낮음 = 건조, 높음 = 습함)
        continentalness: 0 ~ 1 (낮음 = 바다, 높음 = 내륙)
        erosion: 0 ~ 1 (낮음 = 평탄, 높음 = 침식됨)
        slope_angle: 0 ~ 90 (각도, 경사도)

    Returns:
        float: 0.0 ~ 1.0 (0 = 나무 없음, 1 = 최대 밀도)
    """

    # 물 지역 제외 (continentalness가 매우 낮으면 바다/호수)
    # 참고: z < 0.1 체크로 이미 물은 필터링되므로 이 체크는 불필요
    # if continentalness < 0.2:
    #     return 0.0

    # 경사가 너무 가파르면 밀도 감소 (절벽에는 나무 적음)
    if slope_angle > 50:
        slope_factor = max(0.0, 1.0 - (slope_angle - 50) / 40.0)  # 50~90도: 1.0 -> 0.0
    else:
        slope_factor = 1.0

    # 습도 영향 (나무는 물이 필요함) - 가장 큰 영향
    humidity_factor = humidity + 0.1  # 0~1

    # 온도 영향 (너무 춥거나 덥지 않은 중간 범위가 최적)
    # temperature는 -1~1이므로, 0.2~0.5 범위가 최적이라고 가정
    optimal_temp_center = 0.3
    optimal_temp_range = 0.6
    temp_distance = abs(temperature - optimal_temp_center) / optimal_temp_range
    temp_factor = max(0.0, 1.0 - temp_distance)

    # 침식 영향 (침식이 심하면 토양이 얇아서 나무 적음)
    erosion_factor = max(0.1, 1.0 - erosion * 0.7)  # 침식이 심해도 최소 10%는 유지

    # 대륙성 영향 (내륙일수록 밀도 증가, 하지만 너무 극단적이지 않게)
    continental_factor = min(1.0, continentalness * 1.2)

    # 최종 밀도 계산 (가중 평균)
    density = (
        humidity_factor * 0.45  # 25% 영향
        + temp_factor * 0.25  # 25% 영향
        + erosion_factor * 0.15  # 15% 영향
        + slope_factor * 0.15  # 15% 영향
        + continental_factor * 0.05  # 5% 영향
    )

    # 0~1 범위로 클램핑
    density = max(0.01, min(1.0, density))

    return density


def select_object_by_probability(
    temperature,
    humidity,
    continentalness,
    erosion,
    slope_angle,
    objects_list,
    object_type,
    assets_dir,
):
    """
    현재 바이옴 파라미터에 따라 확률 가중치 기반으로 오브젝트 선택

    Args:
        objects_list: 오브젝트 리스트 (spawn_config['trees']['items'] 등)
        object_type: 오브젝트 타입 ('trees', 'flowers' 등)

    Returns:
        (gltf_file_path, object_config) | (None, None)
    """
    current_params = {
        "temperature": temperature,
        "humidity": humidity,
        "continentalness": continentalness,
        "erosion": erosion,
        "slope_angle": slope_angle,
    }

    # 1단계: 범위 필터링 (Hard Constraint)
    valid_objects = []
    for obj in objects_list:
        is_valid = True
        failed_param = None
        failed_value = None
        failed_range = None

        for param_name, value in current_params.items():
            if param_name in obj["param_ranges"]:
                if not is_in_range(value, obj["param_ranges"][param_name]):
                    is_valid = False
                    failed_param = param_name
                    failed_value = value
                    failed_range = obj["param_ranges"][param_name]
                    break

        if is_valid:
            valid_objects.append(obj)
            if DEBUG_MODE:
                log(f"      ✅ {obj['name']}: PASSED all range checks")
        else:
            if DEBUG_MODE:
                log(f"      ❌ {obj['name']}: FILTERED by {failed_param}={failed_value:.3f} not in {failed_range}")

    if not valid_objects:
        if DEBUG_MODE:
            log(f"    ❌ No valid objects after range filtering")
        return None, None  # 배치 불가

    # 2단계: 중앙값과의 거리로 가중치 계산 (온도/습도만, 선형)
    if DEBUG_MODE:
        log(f"    🎲 Calculating weights for {len(valid_objects)} valid objects...")

    weights = []
    for obj in valid_objects:
        # 선형 거리 가중치: 중앙 = 100%, 최소/최대 = 50%
        distance_penalty = 0.0

        # 온도/습도만 거리 가중치 적용 (다른 파라미터는 Hard Constraint만)
        for param_name in ["temperature", "humidity"]:
            if param_name in obj["param_ranges"]:
                value = current_params[param_name]
                min_val, max_val = obj["param_ranges"][param_name]
                center = (min_val + max_val) / 2.0  # 중앙값
                range_size = max_val - min_val

                if range_size > 0:
                    # 중앙에서의 정규화된 거리 (0~1)
                    # center에서 0, min/max에서 1
                    normalized_dist = abs(value - center) / (range_size / 2.0)
                    # 선형 페널티: 0 → 0%, 1 → 50% 감소
                    penalty = normalized_dist * 0.5
                    distance_penalty += penalty

                    if DEBUG_MODE:
                        log(f"      📐 {obj['name']}: {param_name}={value:.3f}, range=[{min_val:.2f},{max_val:.2f}], center={center:.2f}, dist={normalized_dist:.3f}, penalty={penalty:.3f}")

        # 평균 페널티 (온도와 습도 두 개면 평균)
        if distance_penalty > 0:
            distance_penalty /= 2.0  # 두 파라미터 평균

        # 선형 가중치: 1.0 (중앙) → 0.5 (최소/최대)
        distance_weight = 1.0 - distance_penalty

        # 최종 가중치 = 거리 가중치 * spawn_weight
        weight = distance_weight * obj["spawn_weight"]
        weights.append((obj, weight))

        if DEBUG_MODE:
            log(f"      🎯 {obj['name']}: distance_weight={distance_weight:.3f}, spawn_weight={obj['spawn_weight']}, final_weight={weight:.3f}")

    # 3단계: 가중치 기반 랜덤 선택
    total_weight = sum(w for _, w in weights)
    if total_weight <= 0:
        if DEBUG_MODE:
            log(f"    ❌ Total weight is 0, cannot select")
        return None, None

    if DEBUG_MODE:
        log(f"    🎲 Total weight: {total_weight:.3f}")
        for obj, weight in weights:
            probability = (weight / total_weight) * 100
            log(f"      - {obj['name']}: probability={probability:.1f}%")

    rand_value = random.random() * total_weight
    cumulative = 0

    if DEBUG_MODE:
        log(f"    🎲 Random roll: {rand_value:.3f}")

    for obj, weight in weights:
        cumulative += weight
        if rand_value <= cumulative:
            # GLTF 파일 경로 생성
            category = obj["category"]
            gltf_relative = obj["gltf_path"]

            # object_type에 따라 폴더 이름 결정 (trees → tree, flowers → flower)
            folder_name = object_type.rstrip('s')  # 's' 제거 (trees→tree, flowers→flower)
            gltf_full_path = os.path.join(
                assets_dir, "objects", folder_name, category, gltf_relative
            )

            if DEBUG_MODE:
                log(f"    ✅ SELECTED: {obj['name']} (cumulative={cumulative:.3f})")

            if os.path.exists(gltf_full_path):
                return gltf_full_path, obj  # GLTF 경로와 object 설정 반환
            else:
                log(f"⚠️ GLTF not found: {gltf_full_path}")
                return None, None

    return None, None


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
        dist_2d = math.sqrt((world_pos.x - x) ** 2 + (world_pos.y - y) ** 2)

        if dist_2d < min_distance:
            return True

    return False


# =============================================================================
# 6. GLTF 임포트 및 배치 (캐싱)
# =============================================================================

# GLTF 캐시: {gltf_path: [원본_오브젝트들]}
# 같은 GLTF를 여러 번 임포트하면 용량 폭발 → 한 번만 임포트하고 복사 사용
gltf_cache = {}

# skeletal 로 여러개 나무를 파라미터로 변형 및 여러 종류로
# geometry 를 하나로 공유?

def import_and_place_gltf(gltf_path, x, y, z, normal, obj_config):
    """
    GLTF 파일 임포트 후 지형에 배치 (캐싱 사용으로 용량 최적화)

    Args:
        gltf_path: GLTF 파일 경로
        x, y, z: 월드 좌표
        normal: 법선 벡터 (지형 경사)
        obj_config: 오브젝트 설정 (scale_range, full_rotation 등)
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

        # 원본은 화면 밖으로 숨기고 익스포트에서 제외
        for obj in imported_objs:
            obj.location = (0, 0, -1000)
            obj.hide_viewport = True  # 뷰포트에서 숨김
            obj.hide_render = True  # 렌더링에서 제외
            obj.hide_select = True  # 선택 불가
            obj.hide_set(True)  # 완전히 숨김 (GLTF 익스포트에서도 제외)

    # 캐시된 원본 오브젝트들 중에서 랜덤으로 하나만 선택
    original_objs = gltf_cache[gltf_path]

    # MESH 타입 오브젝트만 필터링 (카메라, 라이트 등 제외)
    mesh_objs = [obj for obj in original_objs if obj.type == "MESH"]

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
    imported_obj.hide_set(False)  # 완전히 보이게 (GLTF 익스포트에 포함)

    # 위치 설정
    imported_obj.location = (x, y, z)

    # 회전 설정 (오브젝트 타입에 따라 다름)
    # CRITICAL: rotation_mode를 Euler로 변경 (Quaternion이면 rotation_euler이 무시됨)
    imported_obj.rotation_mode = 'XYZ'

    # full_rotation 속성이 있으면 전방향 랜덤 회전 (바위용)
    if obj_config.get("full_rotation", False):
        # X, Y, Z 모두 랜덤 회전
        random_x = random.uniform(0, 2 * math.pi)
        random_y = random.uniform(0, 2 * math.pi)
        random_z = random.uniform(0, 2 * math.pi)
        imported_obj.rotation_euler = (random_x, random_y, random_z)
    else:
        # Z축만 랜덤 회전 (나무, 꽃용 - 수직 유지)
        random_z_rotation = random.uniform(0, 2 * math.pi)
        imported_obj.rotation_euler = (0, 0, random_z_rotation)

    # 랜덤 스케일 (obj_config의 scale_range 사용)
    # 평균값 중심의 정규 분포로 스케일링 (가우시안 분포)
    if "scale_range" in obj_config:
        min_scale, max_scale = obj_config["scale_range"]
        mean_scale = (min_scale + max_scale) / 2.0
        std_dev = (max_scale - min_scale) / 4.0  # 99.7%가 범위 내에 들어오도록

        # 정규 분포로 스케일 생성 (평균 근처에 더 많이 분포)
        scale_factor = random.gauss(mean_scale, std_dev)
        scale_factor = max(min_scale, min(max_scale, scale_factor))  # 범위 클램핑
    else:
        # scale_range가 없으면 기본값 사용
        scale_factor = random.uniform(0.8, 1.2)

    imported_obj.scale = (scale_factor, scale_factor, scale_factor)


# =============================================================================
# 7. 메인 실행
# =============================================================================


def main():
    # 로그 파일 초기화
    init_log_file(OUTPUT_BLEND)

    log("========================================")
    log("Starting object placement...")
    log("========================================")

    # 1. Biome maps 로드
    biome_maps = load_biome_maps(BIOME_MAPS_DIR)
    if len(biome_maps) == 0:
        log("❌ No biome maps found")
        close_log_file()
        sys.exit(1)

    # 2. Object spawn config 로드
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        spawn_config = load_object_spawn_config(script_dir)
        total_configs = sum(len(config.get('items', [])) for config in spawn_config.values())
        log(f"✅ Loaded {total_configs} object configurations:")
        for obj_type, config in spawn_config.items():
            if 'items' in config and 'type_weight' in config:
                log(f"  - {obj_type}: {len(config['items'])} items, type_weight={config['type_weight']}")
    except Exception as e:
        log(f"❌ Failed to load object spawn config: {e}")
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
        depsgraph, test_origin, test_direction
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
        "total_attempts": 0,
        "no_hit": 0,
        "too_close_to_road": 0,
        "low_density": 0,  # 밀도가 낮아서 스킵
        "no_category": 0,
        "no_assets": 0,
        "no_gltf": 0,
        "import_failed": 0,
        "success": 0,
    }

    # 목표 개수에 도달할 때까지 계속 시도 (최대 시도 횟수 제한)
    max_attempts = OBJECT_COUNT * 30  # 최대 10배까지 시도
    attempt = 0

    while placed_count < OBJECT_COUNT and attempt < max_attempts:
        attempt += 1

        if attempt % 100 == 0:
            log(
                f"  Progress: {placed_count}/{OBJECT_COUNT} placed ({attempt} attempts)"
            )

        debug_stats["total_attempts"] += 1

        # 랜덤 XY 좌표 (지형 범위: -500 ~ 500)
        x = random.uniform(terrain_min, terrain_max)
        y = random.uniform(terrain_min, terrain_max)

        # 🐛 DEBUG: 시도 시작
        if DEBUG_MODE:
            log(f"")
            log(f"🔍 [Attempt {attempt}] Starting at world position ({x:.2f}, {y:.2f})")

        # Raycast로 지형 정보 찾기
        origin = mathutils.Vector((x, y, 1000))
        direction = mathutils.Vector((0, 0, -1))

        hit, location, normal, _, obj, _ = scene.ray_cast(depsgraph, origin, direction)

        if not hit:
            debug_stats["no_hit"] += 1
            if DEBUG_MODE:
                log(f"  ❌ SKIP: No raycast hit")
            continue  # 지형 없음

        z = location.z

        # 물 위 배치 방지 (z < 0.1)
        if z < 0.1:
            debug_stats["no_hit"] += 1  # 물로 간주
            if DEBUG_MODE:
                log(f"  ❌ SKIP: Water area (z={z:.3f})")
            continue

        slope_angle = math.degrees(math.acos(max(-1, min(1, normal.z))))

        if DEBUG_MODE:
            log(f"  ✅ Hit terrain at z={z:.2f}, slope={slope_angle:.1f}°, normal=({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f})")

        # 도로 충돌 체크
        if is_too_close_to_road(x, y, road_obj, min_distance=2.0):
            debug_stats["too_close_to_road"] += 1
            if DEBUG_MODE:
                log(f"  ❌ SKIP: Too close to road")
            continue

        # Biome 파라미터 읽기
        if DEBUG_MODE:
            log(f"  📊 Reading biome parameters...")

        temperature = read_biome_pixel(biome_maps, "temperature", x, y, terrain_size)
        humidity = read_biome_pixel(biome_maps, "humidity", x, y, terrain_size)
        continentalness = read_biome_pixel(
            biome_maps, "continentalness", x, y, terrain_size
        )
        erosion = read_biome_pixel(biome_maps, "erosion", x, y, terrain_size)

        if DEBUG_MODE:
            log(f"  📊 Biome params: temp={temperature:.3f}, humidity={humidity:.3f}, continentalness={continentalness:.3f}, erosion={erosion:.3f}")

        # 식생 밀도 계산 및 확률적 배치 결정
        vegetation_density = calculate_vegetation_density(
            temperature, humidity, continentalness, erosion, slope_angle
        )

        if DEBUG_MODE:
            log(f"  🌱 Vegetation density: {vegetation_density:.3f}")

        # 밀도 기반 확률 체크 (random.random()은 0~1 사이 값 반환)
        # 예: density=0.7이면 70% 확률로 배치 시도
        density_roll = random.random()
        if density_roll > vegetation_density:
            # 이 위치는 밀도가 낮아서 스킵
            debug_stats["low_density"] += 1
            if DEBUG_MODE:
                log(f"  ❌ SKIP: Low density (roll={density_roll:.3f} > {vegetation_density:.3f})")
            continue

        if DEBUG_MODE:
            log(f"  ✅ Passed density check (roll={density_roll:.3f} <= {vegetation_density:.3f})")

        # 1단계: 오브젝트 타입 선택 (trees, flowers 등)
        selected_type = select_object_type(spawn_config)
        if selected_type is None:
            debug_stats["no_category"] += 1
            if DEBUG_MODE:
                log(f"  ❌ SKIP: No object type selected")
            continue

        if DEBUG_MODE:
            log(f"  🎲 Selected object type: {selected_type}")

        # 2단계: 선택된 타입 내에서 구체적인 오브젝트 선택
        objects_list = spawn_config[selected_type].get("items", [])

        if DEBUG_MODE:
            log(f"  🔍 Selecting from {len(objects_list)} {selected_type} items...")

        gltf_file, obj_config = select_object_by_probability(
            temperature,
            humidity,
            continentalness,
            erosion,
            slope_angle,
            objects_list,
            selected_type,
            ASSETS_DIR,
        )

        if gltf_file is None:
            debug_stats["no_category"] += 1
            if DEBUG_MODE:
                log(f"  ❌ SKIP: No suitable {selected_type} found (all filtered out)")
            continue  # 배치 안함

        # GLTF 임포트 및 배치
        try:
            if DEBUG_MODE:
                log(f"  🚀 Importing and placing: {obj_config['name']}")

            import_and_place_gltf(gltf_file, x, y, z, normal, obj_config)
            debug_stats["success"] += 1
            placed_count += 1

            obj_name = obj_config.get(
                "name", os.path.basename(os.path.dirname(gltf_file))
            )
            scale_range = obj_config.get("scale_range", [0.8, 1.2])

            if DEBUG_MODE or placed_count <= 10:
                log(
                    f"  ✅ SUCCESS: Placed {obj_name} ({selected_type}) at ({x:.1f}, {y:.1f}, {z:.1f}) [scale: {scale_range[0]}-{scale_range[1]}] [#{placed_count}]"
                )

        except Exception as e:
            debug_stats["import_failed"] += 1
            log(f"  ⚠️ Failed to place object: {e}")
            if DEBUG_MODE:
                import traceback
                log(f"  ⚠️ Exception traceback:\n{traceback.format_exc()}")
            continue

    # 디버깅 통계 출력
    log(f"\n📊 Debug Statistics:")
    log(f"  Total attempts: {debug_stats['total_attempts']}")
    log(f"  No raycast hit: {debug_stats['no_hit']}")
    log(f"  Too close to road: {debug_stats['too_close_to_road']}")
    log(f"  Low vegetation density: {debug_stats['low_density']}")
    log(f"  No suitable tree (out of range): {debug_stats['no_category']}")
    log(f"  Import failed: {debug_stats['import_failed']}")
    log(f"  Success: {debug_stats['success']}")

    # 목표 달성 여부 확인
    if placed_count >= OBJECT_COUNT:
        log(
            f"\n✅ Placement complete: {placed_count}/{OBJECT_COUNT} objects placed ({attempt} attempts)"
        )
    else:
        log(
            f"\n⚠️ Placement incomplete: {placed_count}/{OBJECT_COUNT} objects placed (reached max attempts: {attempt})"
        )
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

    # 8. 미리보기 렌더링 (선택적)
    if PREVIEW_PATH and PREVIEW_PATH.strip():
        log(f"Rendering preview: {PREVIEW_PATH}")
        scene.render.filepath = PREVIEW_PATH
        scene.camera.location = (500, 500, 800)
        scene.camera.rotation_euler = (0, 0, 0)
        bpy.ops.render.render(write_still=True)
        log("✅ Preview rendered")
    else:
        log("⏭️ Skipping preview rendering (no preview path provided)")

    log("========================================")
    log(f"Object placement finished: {placed_count} objects")
    log("========================================")

    # 로그 파일 닫기
    close_log_file()


if __name__ == "__main__":
    main()
