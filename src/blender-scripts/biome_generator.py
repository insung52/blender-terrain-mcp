"""
바이옴 기반 지형 생성 시스템
terrain_upgrade.md 기반 구현
"""

import json
import math
import sys
from typing import List, Dict, Tuple, Any
import numpy as np
from PIL import Image
import os

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# =============================================================================
# 1. 바이옴 포인트 블렌딩 알고리즘 (Smooth Step + Coverage + Noise Distortion)
# =============================================================================

def perlin_noise_2d(x: float, y: float, seed: int = 0) -> float:
    """
    간단한 2D Perlin-like Noise (해시 기반)

    Args:
        x, y: 좌표
        seed: 시드 값

    Returns:
        -1.0 ~ 1.0 범위의 노이즈 값
    """
    # 간단한 해시 함수로 의사 난수 생성
    def hash_coord(ix: int, iy: int, s: int) -> float:
        h = (ix * 374761393 + iy * 668265263 + s * 1274126177) & 0x7FFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0x7FFFFFFF
        return (h & 0xFFFF) / 0xFFFF * 2.0 - 1.0

    # 정수 좌표
    ix, iy = int(math.floor(x)), int(math.floor(y))

    # 소수 부분
    fx, fy = x - ix, y - iy

    # Smoothstep 보간
    u = fx * fx * (3.0 - 2.0 * fx)
    v = fy * fy * (3.0 - 2.0 * fy)

    # 4개 코너 값
    a = hash_coord(ix, iy, seed)
    b = hash_coord(ix + 1, iy, seed)
    c = hash_coord(ix, iy + 1, seed)
    d = hash_coord(ix + 1, iy + 1, seed)

    # 이중선형 보간
    return a * (1 - u) * (1 - v) + b * u * (1 - v) + c * (1 - u) * v + d * u * v


def multi_octave_noise(x: float, y: float, seed: int = 0, scale_factor: float = 1.0) -> float:
    """
    Multi-octave Perlin Noise (3단계)

    Args:
        x, y: 좌표
        seed: 시드 값
        scale_factor: 노이즈 강도 조절 (0.0~1.0, 바이옴이 가까우면 약하게)

    Returns:
        왜곡 거리 (m)
    """
    # Large-scale: 큰 만곡 (150m)
    noise_large = perlin_noise_2d(x * 0.01, y * 0.01, seed) * (150.0 * scale_factor)

    # Medium-scale: 중간 굴곡 (50m)
    noise_medium = perlin_noise_2d(x * 0.05, y * 0.05, seed + 1) * (50.0 * scale_factor)

    # Small-scale: 미세 들쑥날쑥 (10m)
    noise_small = perlin_noise_2d(x * 0.2, y * 0.2, seed + 2) * (10.0 * scale_factor)

    return noise_large + noise_medium + noise_small


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """
    Smoothstep 함수 (S-curve 보간)

    Args:
        edge0: 시작 경계
        edge1: 끝 경계
        x: 입력 값

    Returns:
        0.0 ~ 1.0 보간된 값
    """
    # Clamp
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0) if edge1 != edge0 else 0.0))

    # S-curve
    return t * t * (3.0 - 2.0 * t)


def calculate_influence(
    point: Dict[str, Any],
    x: int,
    y: int,
    all_biome_points: List[Dict[str, Any]],
    point_id: int = 0,
    core_ratio: float = 0.4,
    fade_ratio: float = 0.3
) -> float:
    """
    바이옴 포인트가 특정 셀에 미치는 영향력 계산
    (Dynamic Zone Size + Smooth Step + Coverage + Noise Distortion)

    Args:
        point: 바이옴 포인트 {"position": [x, y], "coverage": float, ...}
        x, y: 셀 좌표
        all_biome_points: 모든 바이옴 포인트 (동적 zone 계산용)
        point_id: 바이옴 포인트 ID (noise seed용)
        core_ratio: Core zone 비율 (0.4 = 40%)
        fade_ratio: Transition zone 비율 (0.3 = 30%)

    Returns:
        영향력 (0.0 ~ 1.0)
    """
    px, py = point["position"]

    # Step 1: 실제 거리 계산
    real_distance = math.sqrt((x - px)**2 + (y - py)**2)

    # Step 2: 가장 가까운 다른 바이옴까지의 거리 계산 (동적 Zone Size)
    min_neighbor_distance = float('inf')
    for i, other_point in enumerate(all_biome_points):
        if i == point_id:
            continue  # 자기 자신 제외

        ox, oy = other_point["position"]
        neighbor_distance = math.sqrt((px - ox)**2 + (py - oy)**2)
        min_neighbor_distance = min(min_neighbor_distance, neighbor_distance)

    # 다른 바이옴이 없으면 기본값 사용
    if min_neighbor_distance == float('inf'):
        min_neighbor_distance = 500.0

    # Step 3: Multi-octave Noise로 거리 왜곡
    # 🔥 중요: seed를 좌표 기반으로만 사용 (point_id 사용 안 함!)
    # 모든 바이옴이 같은 distortion을 공유해야 윤곽선 아티팩트 방지
    noise_scale_factor = min(1.0, min_neighbor_distance / 1000.0)
    distortion = multi_octave_noise(x, y, seed=0, scale_factor=noise_scale_factor)

    # Step 4: Coverage 가중치 적용
    # Coverage 클수록 → 영향력 범위 넓어짐
    coverage = point.get("coverage", 0.5)
    if coverage <= 0.0:
        coverage = 0.01  # Division by zero 방지

    # 🔥 동적 Zone Size: 가장 가까운 바이옴까지 거리의 일정 비율
    # Coverage가 크면 더 넓게 확장
    base_zone_size = min_neighbor_distance * coverage * 0.6  # 거리의 60%까지 확장

    core_threshold = base_zone_size * core_ratio
    fade_threshold = core_threshold + base_zone_size * fade_ratio

    # 🔥 Noise Clamping: Noise 왜곡이 Core threshold의 30%를 넘지 않도록 제한
    # 이렇게 하면 경계 픽셀이 극단적으로 뒤집히는 것을 방지 (윤곽선 아티팩트 제거)
    max_distortion = core_threshold * 0.3
    distortion = max(-max_distortion, min(max_distortion, distortion))

    # 왜곡된 거리 재계산 (클램핑된 distortion 사용)
    distorted_distance = max(0.0, real_distance + distortion)

    # Step 5: Smoothstep Influence 계산
    if distorted_distance < core_threshold:
        # Core Zone: 100% 원본 바이옴 유지
        return 1.0
    elif distorted_distance < fade_threshold:
        # Transition Zone: Smoothstep (1.0 → 0.0)
        return 1.0 - smoothstep(core_threshold, fade_threshold, distorted_distance)
    else:
        # Far Zone: 거리 기반 fallback (완전히 0 방지)
        # 작은 영향력 유지 (모든 영역이 블렌딩에 참여하도록)
        fallback_influence = 1.0 / (distorted_distance - fade_threshold + 10.0)
        return max(0.001, fallback_influence * 0.5)  # 최소 0.001 (기존 0.0001에서 10배 증가)


def blend_parameters(influences: List[Tuple[float, Dict[str, float]]]) -> Dict[str, float]:
    """
    여러 바이옴의 영향력에 따라 파라미터 블렌딩

    Args:
        influences: [(영향력, 파라미터 딕셔너리), ...]

    Returns:
        블렌딩된 파라미터 딕셔너리
    """
    if not influences:
        raise ValueError("influences가 비어있습니다")

    # 영향력 정규화
    total_influence = sum(inf for inf, _ in influences)

    # 🔥 Threshold 제거! 모든 영역이 정상 블렌딩에 참여
    # fallback influence 덕분에 total_influence는 거의 항상 > 0
    if total_influence == 0:
        # 극히 드문 경우: 진짜 0 (이론적으로만 가능)
        # 가장 큰 fallback influence 2개 블렌딩
        sorted_influences = sorted(influences, key=lambda x: x[0], reverse=True)

        if len(sorted_influences) >= 2:
            # 상위 2개 블렌딩 (균등 가중)
            first = sorted_influences[0][1]
            second = sorted_influences[1][1]

            blended = {}
            for param_name in first.keys():
                blended[param_name] = (first[param_name] + second[param_name]) / 2.0
            return blended
        else:
            # 바이옴이 1개뿐
            return sorted_influences[0][1].copy()

    # 정상 블렌딩: 영향력에 비례한 가중 평균
    weights = [(inf / total_influence, params) for inf, params in influences]

    # 가중 평균으로 파라미터 블렌딩
    blended = {}
    param_names = weights[0][1].keys()

    for param_name in param_names:
        blended[param_name] = sum(
            weight * params[param_name]
            for weight, params in weights
        )

    return blended


def generate_biome_parameter_map(
    biome_points: List[Dict[str, Any]],
    grid_size: int = 100
) -> Dict[str, np.ndarray]:
    """
    바이옴 포인트들로부터 파라미터 맵 생성
    (Smooth Step + Coverage + Noise Distortion)

    Args:
        biome_points: Claude AI가 생성한 바이옴 포인트 리스트
        grid_size: 그리드 크기 (기본 100, terrain_scale에 따라 스케일링)

    Returns:
        파라미터 이름: (grid_size, grid_size) numpy 배열 딕셔너리
    """
    # 파라미터 이름 리스트
    param_names = [
        'temperature', 'humidity', 'erosion', 'continentalness', 'weirdness',
        'vegetation_color_r', 'vegetation_color_g', 'vegetation_color_b',
        'ground_color_r', 'ground_color_g', 'ground_color_b',
        'snow_start_height', 'rock_exposure'
    ]

    # 초기화
    biome_maps = {name: np.zeros((grid_size, grid_size)) for name in param_names}

    print(f"🔥 New Biome Blending Algorithm V2:")
    print(f"  - Dynamic Zone Size (based on nearest neighbor distance)")
    print(f"  - Smooth Step (3-Zone System)")
    print(f"  - Coverage-based Expansion (larger coverage = wider zone)")
    print(f"  - Multi-octave Noise Distortion (Minecraft-style irregular boundaries)")
    print(f"  - Adaptive Noise Strength (closer biomes = weaker distortion)")
    print(f"  - Fallback Blending (prevents sink holes)")
    print(f"  - Core ratio: 40%, Fade ratio: 30%")
    print()

    # 각 셀에 대해 파라미터 계산
    for y in range(grid_size):
        if y % 100 == 0:
            print(f"  Progress: {y}/{grid_size} rows...")

        for x in range(grid_size):
            # 각 바이옴 포인트의 영향력 계산
            influences = []
            for point_id, point in enumerate(biome_points):
                # 🔥 새로운 알고리즘: all_biome_points 전달 (동적 zone 계산)
                influence = calculate_influence(
                    point, x, y,
                    all_biome_points=biome_points,
                    point_id=point_id,
                    core_ratio=0.4,
                    fade_ratio=0.3
                )
                influences.append((influence, point["biome_params"]))

            # 영향력 기반 블렌딩
            blended_params = blend_parameters(influences)

            # 각 파라미터 맵에 저장
            for param_name in param_names:
                biome_maps[param_name][y, x] = blended_params[param_name]

    print(f"  Progress: {grid_size}/{grid_size} rows... Done!")
    return biome_maps


# =============================================================================
# 2. 바이옴 맵을 이미지로 변환
# =============================================================================

def normalize_parameter_to_image(param_map: np.ndarray, param_name: str) -> np.ndarray:
    """
    파라미터 맵을 0~255 이미지 데이터로 정규화

    Args:
        param_map: (grid_size, grid_size) numpy 배열
        param_name: 파라미터 이름

    Returns:
        (grid_size, grid_size) uint8 배열 (0~255)
    """
    if param_name in ['temperature', 'continentalness']:
        # -1.0 ~ 1.0 → 0 ~ 255
        normalized = ((param_map + 1.0) / 2.0 * 255).astype(np.uint8)
    elif param_name == 'snow_start_height':
        # 0 ~ 5000 → 0 ~ 255
        normalized = (np.clip(param_map, 0, 5000) / 5000.0 * 255).astype(np.uint8)
    else:
        # 0.0 ~ 1.0 → 0 ~ 255
        normalized = (np.clip(param_map, 0.0, 1.0) * 255).astype(np.uint8)

    return normalized


def save_biome_maps_as_images(
    biome_maps: Dict[str, np.ndarray],
    output_dir: str
) -> List[str]:
    """
    바이옴 파라미터 맵들을 PNG 이미지로 저장

    Args:
        biome_maps: 파라미터 이름: numpy 배열 딕셔너리
        output_dir: 출력 디렉토리 경로

    Returns:
        저장된 파일 경로 리스트
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_files = []

    for param_name, param_map in biome_maps.items():
        # 정규화
        normalized = normalize_parameter_to_image(param_map, param_name)

        # PNG 저장 (Grayscale)
        img = Image.fromarray(normalized, mode='L')
        file_path = os.path.join(output_dir, f'biome_{param_name}.png')
        img.save(file_path)
        saved_files.append(file_path)

    return saved_files


# =============================================================================
# 3. Blender 지형 생성 (추후 Geometry Nodes와 통합)
# =============================================================================

def generate_biome_terrain_script(
    biome_maps: Dict[str, np.ndarray],
    output_blend_file: str,
    image_dir: str
) -> str:
    """
    Blender에서 실행할 Python 스크립트 생성

    Args:
        biome_maps: 바이옴 파라미터 맵
        output_blend_file: 출력 .blend 파일 경로
        image_dir: 바이옴 이미지 디렉토리

    Returns:
        Blender Python 스크립트 문자열
    """
    script = f'''
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
image_dir = r"{image_dir}"
param_names = [
    'temperature', 'humidity', 'erosion', 'continentalness', 'weirdness',
    'vegetation_color_r', 'vegetation_color_g', 'vegetation_color_b',
    'ground_color_r', 'ground_color_g', 'ground_color_b',
    'snow_start_height', 'rock_exposure'
]

loaded_images = {{}}
for param_name in param_names:
    img_path = os.path.join(image_dir, f'biome_{{param_name}}.png')
    if os.path.exists(img_path):
        img = bpy.data.images.load(img_path)
        img.name = f'biome_{{param_name}}'
        loaded_images[param_name] = img
        print(f'✅ Loaded: {{img_path}}')
    else:
        print(f'❌ Not found: {{img_path}}')

# === 4. Geometry Nodes Modifier 추가 ===
# (추후 구현: Image Texture 샘플링 → Set Position)
modifier = terrain_obj.modifiers.new(name="BiomeTerrainGenerator", type='NODES')

# TODO: Geometry Nodes 그래프 프로그래밍 방식으로 생성
# 현재는 수동으로 Geometry Nodes 설정 필요

# === 5. .blend 파일 저장 ===
bpy.ops.wm.save_as_mainfile(filepath=r"{output_blend_file}")
print(f'✅ Saved: {output_blend_file}')
'''
    return script


# =============================================================================
# 4. 메인 실행 함수
# =============================================================================

def generate_default_terrain_params():
    """기본 지형 파라미터 생성"""
    return {
        "grid_subdivisions": 200,
        "terrain_scale": 10,  # 10배 = 1km
        "height_multiplier": 30,
        "z_scale": 3,
        "noise_scale": 0.05,
        "noise_detail": 5.0,
        "erosion_strength": 20.0,
        "continentalness_strength": 10.0,
        "weirdness_strength": 5.0,
        "temperature_influence": 0.2
    }


def main():
    """
    메인 실행 함수

    Usage:
        python biome_generator.py <biome_layout_json> <output_dir>

    Example:
        python biome_generator.py biome_layout.json ./output
    """
    if len(sys.argv) < 3:
        print("Usage: python biome_generator.py <biome_layout_json> <output_dir>")
        print("\nExample biome_layout.json:")
        print(json.dumps({
            "biome_points": [
                {
                    "position": [15, 50],
                    "biome_params": {
                        "temperature": -0.7,
                        "humidity": 0.4,
                        "erosion": 0.8,
                        "continentalness": 0.6,
                        "weirdness": 0.3,
                        "vegetation_color_r": 0.2,
                        "vegetation_color_g": 0.3,
                        "vegetation_color_b": 0.2,
                        "ground_color_r": 0.4,
                        "ground_color_g": 0.4,
                        "ground_color_b": 0.45,
                        "snow_start_height": 1500,
                        "rock_exposure": 0.7
                    },
                    "coverage": 0.25,
                    "description": "snowy_mountain"
                },
                {
                    "position": [85, 50],
                    "biome_params": {
                        "temperature": 0.9,
                        "humidity": 0.1,
                        "erosion": 0.3,
                        "continentalness": 0.5,
                        "weirdness": 0.1,
                        "vegetation_color_r": 0.4,
                        "vegetation_color_g": 0.4,
                        "vegetation_color_b": 0.2,
                        "ground_color_r": 0.9,
                        "ground_color_g": 0.8,
                        "ground_color_b": 0.6,
                        "snow_start_height": 9999,
                        "rock_exposure": 0.3
                    },
                    "coverage": 0.25,
                    "description": "desert"
                }
            ],
            "blend_distance": 15
        }, indent=2))
        sys.exit(1)

    biome_layout_file = sys.argv[1]
    output_dir = sys.argv[2]

    # 1. 바이옴 레이아웃 로드
    with open(biome_layout_file, 'r', encoding='utf-8') as f:
        biome_layout = json.load(f)

    biome_points = biome_layout["biome_points"]

    print(f"📍 바이옴 포인트 개수: {len(biome_points)}")
    for i, point in enumerate(biome_points):
        print(f"  {i+1}. {point['description']} at {point['position']}")

    # 2. terrain_scale 로드
    if 'terrain_params' in biome_layout:
        terrain_scale = biome_layout['terrain_params'].get('terrain_scale', 10)
    else:
        terrain_scale = 10  # 기본값

    # 바이옴 이미지 크기 = base_size(100) * terrain_scale
    grid_size = 100 * terrain_scale  # 1000 for terrain_scale=10

    # 바이옴 포인트 위치를 terrain_scale에 맞게 스케일링
    scaled_biome_points = []
    for point in biome_points:
        scaled_point = point.copy()
        scaled_point['position'] = [
            point['position'][0] * terrain_scale,
            point['position'][1] * terrain_scale
        ]
        scaled_biome_points.append(scaled_point)

    print(f"\n🔄 {grid_size}x{grid_size} 바이옴 파라미터 맵 생성 중 (terrain_scale={terrain_scale})...")
    biome_maps = generate_biome_parameter_map(scaled_biome_points, grid_size=grid_size)
    print(f"✅ {len(biome_maps)}개 파라미터 맵 생성 완료")

    # 3. 이미지로 저장
    image_dir = os.path.join(output_dir, 'biome_maps')
    print(f"\n💾 이미지 저장 중: {image_dir}")
    saved_files = save_biome_maps_as_images(biome_maps, image_dir)
    print(f"✅ {len(saved_files)}개 PNG 파일 저장 완료")

    # 4. 지형 파라미터 JSON 생성
    terrain_params = generate_default_terrain_params()
    if 'terrain_params' in biome_layout:
        terrain_params.update(biome_layout['terrain_params'])

    params_file = os.path.join(output_dir, 'terrain_params.json')
    with open(params_file, 'w', encoding='utf-8') as f:
        json.dump(terrain_params, f, indent=2)

    print(f"✅ 지형 파라미터 생성: {params_file}")

    # 5. Blender 실행 명령 출력
    blend_file = os.path.join(output_dir, 'biome_terrain.blend')
    preview_file = os.path.join(output_dir, 'preview.png')

    print(f"\n🎯 다음 명령으로 Blender에서 실행:")
    print(f'   blender --background --python src/blender-scripts/biome_terrain_blender.py -- "{image_dir}" "{params_file}" "{blend_file}" "{preview_file}"')

    # 6. 결과 요약
    print("\n" + "="*60)
    print("📊 생성 결과 요약")
    print("="*60)
    print(f"바이옴 포인트: {len(biome_points)}개")
    print(f"파라미터 맵: {len(biome_maps)}개 ({grid_size}x{grid_size})")
    print(f"PNG 이미지: {len(saved_files)}개")
    print(f"지형 파라미터: {params_file}")
    print(f"출력 디렉토리: {output_dir}")
    print(f"\n지형 설정:")
    print(f"  - 그리드: {terrain_params['grid_subdivisions']}×{terrain_params['grid_subdivisions']}")
    print(f"  - 크기: {terrain_params['terrain_scale'] * 100}m (= {terrain_params['terrain_scale'] * 100 / 1000}km)")
    print(f"  - 최대 높이: {terrain_params['height_multiplier'] * terrain_params['z_scale']}m")
    print("="*60)


if __name__ == "__main__":
    main()
