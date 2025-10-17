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
# 1. 바이옴 포인트 블렌딩 알고리즘
# =============================================================================

def calculate_influence(point: Dict[str, Any], x: int, y: int) -> float:
    """
    바이옴 포인트가 특정 셀에 미치는 영향력 계산

    Args:
        point: 바이옴 포인트 {"position": [x, y], "coverage": float, ...}
        x, y: 셀 좌표

    Returns:
        영향력 (0.0 ~ 무한대, 가까울수록 큼)
    """
    px, py = point["position"]
    distance = math.sqrt((x - px)**2 + (y - py)**2)

    # 영향력 = coverage / (거리 + 1)
    # +1: 거리 0일 때 무한대 방지
    influence = point["coverage"] / (distance + 1.0)

    return influence


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

    if total_influence == 0:
        # 모든 영향력이 0일 경우 첫 번째 파라미터 반환
        return influences[0][1].copy()

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
    바이옴 포인트들로부터 100x100 파라미터 맵 생성

    Args:
        biome_points: Claude AI가 생성한 바이옴 포인트 리스트
        grid_size: 그리드 크기 (기본 100)

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

    # 각 셀에 대해 파라미터 계산
    for y in range(grid_size):
        for x in range(grid_size):
            # 각 바이옴 포인트의 영향력 계산
            influences = []
            for point in biome_points:
                influence = calculate_influence(point, x, y)
                influences.append((influence, point["biome_params"]))

            # 영향력 기반 블렌딩
            blended_params = blend_parameters(influences)

            # 각 파라미터 맵에 저장
            for param_name in param_names:
                biome_maps[param_name][y, x] = blended_params[param_name]

    return biome_maps


# =============================================================================
# 2. 바이옴 맵을 이미지로 변환
# =============================================================================

def normalize_parameter_to_image(param_map: np.ndarray, param_name: str) -> np.ndarray:
    """
    파라미터 맵을 0~255 이미지 데이터로 정규화

    Args:
        param_map: (100, 100) numpy 배열
        param_name: 파라미터 이름

    Returns:
        (100, 100) uint8 배열 (0~255)
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

    # 2. 100x100 바이옴 파라미터 맵 생성
    print("\n🔄 100x100 바이옴 파라미터 맵 생성 중...")
    biome_maps = generate_biome_parameter_map(biome_points)
    print(f"✅ {len(biome_maps)}개 파라미터 맵 생성 완료")

    # 3. 이미지로 저장
    image_dir = os.path.join(output_dir, 'biome_maps')
    print(f"\n💾 이미지 저장 중: {image_dir}")
    saved_files = save_biome_maps_as_images(biome_maps, image_dir)
    print(f"✅ {len(saved_files)}개 PNG 파일 저장 완료")

    # 4. Blender 스크립트 생성
    blend_file = os.path.join(output_dir, 'biome_terrain.blend')
    blender_script = generate_biome_terrain_script(biome_maps, blend_file, image_dir)

    script_path = os.path.join(output_dir, 'run_in_blender.py')
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(blender_script)

    print(f"\n✅ Blender 스크립트 생성: {script_path}")
    print(f"\n🎯 다음 명령으로 Blender에서 실행:")
    print(f"   blender --background --python {script_path}")

    # 5. 결과 요약
    print("\n" + "="*60)
    print("📊 생성 결과 요약")
    print("="*60)
    print(f"바이옴 포인트: {len(biome_points)}개")
    print(f"파라미터 맵: {len(biome_maps)}개 (100x100)")
    print(f"PNG 이미지: {len(saved_files)}개")
    print(f"출력 디렉토리: {output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()
