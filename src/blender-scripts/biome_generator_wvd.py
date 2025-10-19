"""
바이옴 기반 지형 생성 시스템 (Weighted Voronoi Diagram + Gaussian Blur)
next.md 기반 새로운 구현
"""

import json
import math
import sys
from typing import List, Dict, Tuple, Any
import numpy as np
from PIL import Image, ImageFilter
import os

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# =============================================================================
# 1. Noise 함수 (Perlin only - 성능 최적화)
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


def multi_octave_noise(
    x: float, y: float, seed: int = 0, scale_factor: float = 1.0
) -> float:
    """
    Multi-octave Perlin Noise - 땅따먹기용 (Voronoi 제거, 성능 향상)

    Args:
        x, y: 픽셀 좌표
        seed: 시드 값
        scale_factor: 노이즈 강도 조절

    Returns:
        왜곡 거리 (픽셀 단위)
    """
    # 🔥 Perlin Noise만 사용 (Voronoi 제거로 10배 이상 빠름)
    # Extra-large: 매우 큰 만곡 (500픽셀 주기) - 강도 증가
    noise_xlarge = perlin_noise_2d(x * 0.001, y * 0.001, seed) * (300.0 * scale_factor)

    # Large-scale: 큰 만곡 (200픽셀 주기) - 강도 증가
    noise_large = perlin_noise_2d(x * 0.003, y * 0.003, seed + 1) * (
        180.0 * scale_factor
    )

    # Medium-scale: 중간 굴곡 (50픽셀 주기) - 강도 증가
    noise_medium = perlin_noise_2d(x * 0.015, y * 0.015, seed + 2) * (
        100.0 * scale_factor
    )

    # Small-scale: 미세 디테일 (10픽셀 주기) - 새로 추가
    noise_small = perlin_noise_2d(x * 0.08, y * 0.08, seed + 3) * (50.0 * scale_factor)

    # 총 강도: ±630 픽셀 (기존 Voronoi 포함 버전과 비슷)
    return noise_xlarge + noise_large + noise_medium + noise_small


# =============================================================================
# 2. Weighted Voronoi Diagram 기반 바이옴 영역 할당
# =============================================================================


def assign_biome_regions_wvd(
    biome_points: List[Dict[str, Any]], grid_size: int = 100
) -> np.ndarray:
    """
    Weighted Voronoi Diagram으로 바이옴 영역 할당

    각 픽셀을 정확히 하나의 바이옴에 할당 (100% or 0%, 블렌딩 없음)
    Coverage가 클수록 더 넓은 영역 차지

    Args:
        biome_points: 바이옴 포인트 리스트 (position은 0~100 범위)
        grid_size: 그리드 크기 (예: 1000)

    Returns:
        (grid_size, grid_size) 바이옴 ID 배열
    """
    biome_id_map = np.zeros((grid_size, grid_size), dtype=int)

    print(f"🔥 Weighted Voronoi Diagram Algorithm:")
    print(f"  - Coverage-based distance weighting")
    print(f"  - Multi-octave noise for irregular boundaries")
    print(f"  - Each pixel assigned to exactly one biome")
    print()

    # 바이옴 포인트 위치 스케일링 (0~100 → 0~grid_size)
    scale_factor = grid_size / 100.0

    for y in range(grid_size):
        if y % 100 == 0:
            print(f"  Assigning regions: {y}/{grid_size} rows...")

        for x in range(grid_size):
            best_biome_id = -1
            best_weighted_distance = float("inf")

            for i, biome in enumerate(biome_points):
                # 바이옴 포인트 위치 스케일링
                px, py = biome["position"]
                px_scaled = px * scale_factor
                # 🔥 Y축 반전: 이미지 좌표계는 위가 0, 아래가 grid_size
                # 바이옴 좌표계는 아래가 0, 위가 100 → 반전 필요
                py_scaled = (100 - py) * scale_factor
                coverage = biome.get("coverage", 0.5)

                # 실제 거리 계산
                dx = x - px_scaled
                dy = y - py_scaled
                real_distance = math.sqrt(dx**2 + dy**2)

                # 🔥 각 바이옴마다 다른 noise 적용 (바이옴 중심 기준 좌표계)
                # 현재 픽셀의 바이옴 중심 기준 상대 좌표에서 noise 샘플링
                biome_local_noise = multi_octave_noise(
                    px_scaled + dx,
                    py_scaled + dy,
                    seed=i * 1000,  # 바이옴마다 다른 seed
                    scale_factor=1.0,
                )

                # 🔥 Coverage 가중치 적용: Coverage 클수록 거리 짧아짐 (영역 넓어짐)
                weighted_distance = (real_distance + biome_local_noise) / max(
                    0.01, coverage
                )

                if weighted_distance < best_weighted_distance:
                    best_weighted_distance = weighted_distance
                    best_biome_id = i

            biome_id_map[y, x] = best_biome_id

    print(f"  Assigning regions: {grid_size}/{grid_size} rows... Done!")
    return biome_id_map


# =============================================================================
# 3. 바이옴 맵 생성 (영역 할당 + 가우시안 블러)
# =============================================================================


def generate_biome_parameter_map_wvd(
    biome_points: List[Dict[str, Any]], grid_size: int = 100, blur_radius: int = 50
) -> Dict[str, np.ndarray]:
    """
    WVD + Gaussian Blur 방식으로 바이옴 파라미터 맵 생성

    Args:
        biome_points: 바이옴 포인트 리스트
        grid_size: 그리드 크기
        blur_radius: 가우시안 블러 반경 (픽셀)

    Returns:
        파라미터 이름: (grid_size, grid_size) numpy 배열 딕셔너리
    """
    # Step 1: 바이옴 영역 할당 (Weighted Voronoi)
    biome_id_map = assign_biome_regions_wvd(biome_points, grid_size)

    # 파라미터 이름 리스트
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
        "rock_color_r",  # 🪨 바위 색상 (경사진 곳에 노출)
        "rock_color_g",
        "rock_color_b",
        "snow_start_height",
        "rock_exposure",
    ]

    # Step 2: 각 파라미터 맵 생성 (영역별로 값 할당)
    biome_maps = {}

    print(f"\n🎨 Generating parameter maps...")
    for param_name in param_names:
        param_map = np.zeros((grid_size, grid_size), dtype=np.float32)

        # 각 바이옴 영역에 해당 파라미터 값 할당
        for i, biome in enumerate(biome_points):
            param_value = biome["biome_params"][param_name]
            mask = biome_id_map == i
            param_map[mask] = param_value

        biome_maps[param_name] = param_map
        print(
            f"  ✅ {param_name}: range [{param_map.min():.2f}, {param_map.max():.2f}]"
        )

    # Step 3: 가우시안 블러로 경계 블렌딩
    # ⚠️ PIL GaussianBlur는 "L" 모드만 지원하므로, float32로 직접 처리
    print(
        f"\n🌫️  Applying Gaussian Blur (radius={blur_radius}) with float32 precision..."
    )
    for param_name in param_names:
        # NumPy 배열을 PIL Image로 변환
        param_map = biome_maps[param_name]

        # 정규화 (0~1 범위)
        min_val = param_map.min()
        max_val = param_map.max()
        if max_val > min_val:
            normalized = (param_map - min_val) / (max_val - min_val)
        else:
            normalized = param_map.copy()

        # Float32 이미지로 변환 후 블러 (정밀도 유지)
        # PIL은 float를 지원하지 않으므로, 32bit int로 변환
        img_32bit = Image.fromarray(
            (normalized * 4294967295).astype(np.uint32), mode="I"
        )

        # "I" 모드는 GaussianBlur 지원, 하지만 느림
        # 대신 scipy.ndimage로 직접 블러 (더 빠르고 정밀)
        from scipy.ndimage import gaussian_filter

        # 🔧 mode='nearest': 경계에서 가장 가까운 값 복제 (외삽 방지)
        # 기본값 'reflect'는 경계를 반사시켜 예상치 못한 값 생성
        blurred_array = gaussian_filter(normalized, sigma=blur_radius, mode="nearest")

        # 역정규화
        if max_val > min_val:
            blurred_array = blurred_array * (max_val - min_val) + min_val

        biome_maps[param_name] = blurred_array
        print(f"  ✅ Blurred {param_name} (float32)")

    return biome_maps


# =============================================================================
# 4. 바이옴 맵을 이미지로 변환 (기존 코드와 동일)
# =============================================================================


def normalize_parameter_to_image(param_map: np.ndarray, param_name: str) -> np.ndarray:
    """
    파라미터 맵을 0~65535 이미지 데이터로 정규화 (16bit PNG)

    🔧 next.md 5번: 계단식 층 문제 해결
    - 8bit (0~255): 500m 지형 → 2m마다 계단
    - 16bit (0~65535): 500m 지형 → 0.76cm 정밀도

    Args:
        param_map: (grid_size, grid_size) numpy 배열
        param_name: 파라미터 이름

    Returns:
        (grid_size, grid_size) uint16 배열 (0~65535)
    """
    if param_name in ["temperature", "continentalness"]:
        # -1.0 ~ 1.0 → 0 ~ 65535
        normalized = ((param_map + 1.0) / 2.0 * 65535).astype(np.uint16)
    elif param_name == "snow_start_height":
        # 0 ~ 5000 → 0 ~ 65535
        normalized = (np.clip(param_map, 0, 5000) / 5000.0 * 65535).astype(np.uint16)
    else:
        # 0.0 ~ 1.0 → 0 ~ 65535
        normalized = (np.clip(param_map, 0.0, 1.0) * 65535).astype(np.uint16)

    return normalized


def save_biome_maps_as_images(biome_maps: Dict[str, np.ndarray], output_dir: str):
    """
    바이옴 맵을 16bit PNG 이미지로 저장

    🔧 next.md 5번: 16bit PNG 사용 (0~65535)
    - 계단식 층 문제 해결
    - 정밀도: 500m 지형 기준 약 0.76cm

    Args:
        biome_maps: 파라미터 이름: numpy 배열 딕셔너리
        output_dir: 출력 디렉토리
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n💾 Saving biome maps as 16bit PNG images...")
    for param_name, param_map in biome_maps.items():
        # 정규화 (0~65535, uint16)
        img_data = normalize_parameter_to_image(param_map, param_name)

        # 16bit 이미지 저장 (mode="I;16")
        img = Image.fromarray(img_data, mode="I;16")
        img_path = os.path.join(output_dir, f"biome_{param_name}.png")
        img.save(img_path)
        print(f"  ✅ Saved (16bit): {img_path}")


# =============================================================================
# 5. 지형 파라미터 생성
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
        "temperature_influence": 0.2,
    }


# =============================================================================
# 6. 메인 실행 함수
# =============================================================================


def main():
    """
    메인 실행 함수

    Usage:
        python biome_generator_wvd.py <biome_layout_json> <output_dir>

    Example:
        python biome_generator_wvd.py biome_layout.json ./output
    """
    if len(sys.argv) < 3:
        print("Usage: python biome_generator_wvd.py <biome_layout_json> <output_dir>")
        print("\nExample biome_layout.json:")
        print(
            json.dumps(
                {
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
                                "rock_color_r": 0.5,
                                "rock_color_g": 0.48,
                                "rock_color_b": 0.45,
                                "snow_start_height": 1500,
                                "rock_exposure": 0.7,
                            },
                            "coverage": 0.25,
                            "description": "snowy_mountain",
                        }
                    ],
                    "terrain_params": {"terrain_scale": 10},
                },
                indent=2,
            )
        )
        sys.exit(1)

    biome_layout_file = sys.argv[1]
    output_dir = sys.argv[2]

    # 1. 바이옴 레이아웃 로드
    with open(biome_layout_file, "r", encoding="utf-8") as f:
        biome_layout = json.load(f)

    biome_points = biome_layout["biome_points"]

    print(f"📍 바이옴 포인트 개수: {len(biome_points)}")
    for i, point in enumerate(biome_points):
        print(
            f"  {i+1}. {point['description']} at {point['position']}, coverage={point.get('coverage', 0.5)}"
        )

    # 2. terrain_scale 로드
    if "terrain_params" in biome_layout:
        terrain_scale = biome_layout["terrain_params"].get("terrain_scale", 10)
    else:
        terrain_scale = 10  # 기본값

    # 바이옴 이미지 크기 = base_size(100) * terrain_scale
    grid_size = 100 * terrain_scale

    print(f"\n⚙️  Settings:")
    print(f"  - Terrain scale: {terrain_scale}x")
    print(f"  - Grid size: {grid_size}x{grid_size}")
    print(f"  - Blur radius: 50 pixels")

    # 3. 바이옴 맵 생성 (WVD + Gaussian Blur)
    biome_maps = generate_biome_parameter_map_wvd(
        biome_points, grid_size=grid_size, blur_radius=100
    )

    # 4. 이미지로 저장
    biome_maps_dir = os.path.join(output_dir, "biome_maps")
    save_biome_maps_as_images(biome_maps, biome_maps_dir)

    # 5. 지형 파라미터 JSON 생성
    terrain_params = generate_default_terrain_params()
    if "terrain_params" in biome_layout:
        terrain_params.update(biome_layout["terrain_params"])

    params_file = os.path.join(output_dir, "terrain_params.json")
    with open(params_file, "w", encoding="utf-8") as f:
        json.dump(terrain_params, f, indent=2)

    print(f"\n✅ Terrain parameters saved: {params_file}")
    print(f"✅ All biome maps generated successfully!")
    print(f"📂 Output directory: {biome_maps_dir}")


if __name__ == "__main__":
    main()
