"""
바이옴 기반 지형 생성 시스템 (Weighted Voronoi Diagram + Gaussian Blur)
next.md 기반 새로운 구현 - Voronoi Noise 포함 버전 (느림)
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
# 1. Noise 함수 (기존 코드와 동일)
# =============================================================================


def voronoi_noise_2d(x: float, y: float, seed: int = 0) -> float:
    """
    2D Voronoi/Cellular Noise (불규칙한 셀 패턴)

    Args:
        x, y: 좌표
        seed: 시드 값

    Returns:
        0.0 ~ 1.0 범위의 거리 값
    """

    # 해시 함수
    def hash_2d(ix: int, iy: int, s: int) -> tuple:
        h = (ix * 374761393 + iy * 668265263 + s * 1274126177) & 0x7FFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0x7FFFFFFF
        fx = (h & 0xFFFF) / 0xFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0x7FFFFFFF
        fy = (h & 0xFFFF) / 0xFFFF
        return fx, fy

    # 현재 셀
    xi = int(math.floor(x))
    yi = int(math.floor(y))

    min_dist = float("inf")

    # 주변 9개 셀 검사
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            cell_x = xi + dx
            cell_y = yi + dy

            # 셀 내부의 랜덤 포인트
            fx, fy = hash_2d(cell_x, cell_y, seed)
            point_x = cell_x + fx
            point_y = cell_y + fy

            # 현재 위치에서 포인트까지 거리
            dist = math.sqrt((x - point_x) ** 2 + (y - point_y) ** 2)
            min_dist = min(min_dist, dist)

    # 0~1 범위로 정규화 (대략 sqrt(2) = 1.414가 최대)
    return min(1.0, min_dist / 1.414)


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
    Multi-octave Noise (Perlin + Voronoi) - 땅따먹기용 강화 버전

    Args:
        x, y: 픽셀 좌표
        seed: 시드 값
        scale_factor: 노이즈 강도 조절

    Returns:
        왜곡 거리 (픽셀 단위)
    """
    # 🔥 Perlin Noise: 부드러운 만곡
    # Extra-large: 매우 큰 만곡 (500픽셀 주기)
    noise_xlarge = perlin_noise_2d(x * 0.001, y * 0.001, seed) * (200.0 * scale_factor)

    # Large-scale: 큰 만곡 (200픽셀 주기)
    noise_large = perlin_noise_2d(x * 0.003, y * 0.003, seed + 1) * (
        120.0 * scale_factor
    )

    # Medium-scale: 중간 굴곡 (50픽셀 주기)
    noise_medium = perlin_noise_2d(x * 0.015, y * 0.015, seed + 2) * (
        60.0 * scale_factor
    )

    # 🔥 Voronoi Noise: 불규칙한 셀 패턴 (경계를 더 들쑥날쑥하게)
    # Voronoi는 0~1 범위이므로 -1~1로 변환
    voronoi_large = (voronoi_noise_2d(x * 0.008, y * 0.008, seed + 3) * 2 - 1) * (
        100.0 * scale_factor
    )
    voronoi_small = (voronoi_noise_2d(x * 0.04, y * 0.04, seed + 4) * 2 - 1) * (
        50.0 * scale_factor
    )

    return noise_xlarge + noise_large + noise_medium + voronoi_large + voronoi_small


# ... 나머지 코드는 동일 (생략)
