# 지형 생성 시스템 업그레이드 기획

## 목표
마인크래프트의 바이옴 시스템을 모티브로 한 **다중 바이옴 지형 생성** 기능 구현

---

## 1. 바이옴 시스템 설계

### 1.1 바이옴 파라미터 정의 (V1 - 필수 파라미터만)

**설계 원칙:**
- ✅ **모든 파라미터는 수치형** (블렌딩 가능하도록)
- ✅ **필수 파라미터만 13개** (추후 확장 가능)
- ✅ 범주형 변수 제거 (예: vegetation_type → 수치형으로 대체)

```typescript
interface BiomeParametersV1 {
  // === 핵심 지형 파라미터 (5개) ===
  temperature: number;      // -1.0 ~ 1.0 (극한 추위 ~ 작열)
  humidity: number;         // 0.0 ~ 1.0 (건조 ~ 열대)
  erosion: number;          // 0.0 ~ 1.0 (평평 ~ 험준)
  continentalness: number;  // -1.0 ~ 1.0 (바다 ~ 고원)
  weirdness: number;        // 0.0 ~ 1.0 (일반 ~ 특이)

  // === 시각 파라미터 (6개) ===
  vegetation_color_r: number;   // 0.0 ~ 1.0 (식생 R)
  vegetation_color_g: number;   // 0.0 ~ 1.0 (식생 G)
  vegetation_color_b: number;   // 0.0 ~ 1.0 (식생 B)

  ground_color_r: number;       // 0.0 ~ 1.0 (지표 R)
  ground_color_g: number;       // 0.0 ~ 1.0 (지표 G)
  ground_color_b: number;       // 0.0 ~ 1.0 (지표 B)

  // === 추가 파라미터 (2개) ===
  snow_start_height: number;    // 0 ~ 5000 (눈 시작 높이, 미터)
  rock_exposure: number;        // 0.0 ~ 1.0 (바위 노출도)
}

// 총 13개 파라미터 - 모두 수치형!
```

**범주형 → 수치형 변환 예시:**
```typescript
// ❌ 이전 방식 (범주형, 블렌딩 불가)
vegetation_type: 'grass' | 'moss' | 'coral'

// ✅ 새 방식 (수치형, 블렌딩 가능)
// vegetation_color로 대체 + 추후 필요시 추가 파라미터
// - 잔디: [0.3, 0.6, 0.2]
// - 이끼: [0.2, 0.4, 0.2]
// - 산호: [1.0, 0.4, 0.6]
// 블렌딩 결과: [0.65, 0.5, 0.4] (자연스러운 중간 색상)
```

### 1.2 사전 정의 바이옴 프리셋 (V1)

```typescript
const PRESET_BIOMES_V1 = {
  snowy_mountain: {
    // 핵심 지형
    temperature: -0.7,
    humidity: 0.4,
    erosion: 0.8,
    continentalness: 0.6,
    weirdness: 0.3,
    // 시각
    vegetation_color_r: 0.2,
    vegetation_color_g: 0.3,
    vegetation_color_b: 0.2,
    ground_color_r: 0.4,
    ground_color_g: 0.4,
    ground_color_b: 0.45,
    // 추가
    snow_start_height: 1500,
    rock_exposure: 0.7
  },

  desert: {
    temperature: 0.9,
    humidity: 0.1,
    erosion: 0.3,
    continentalness: 0.5,
    weirdness: 0.1,
    vegetation_color_r: 0.4,
    vegetation_color_g: 0.4,
    vegetation_color_b: 0.2,
    ground_color_r: 0.9,
    ground_color_g: 0.8,
    ground_color_b: 0.6,
    snow_start_height: 9999,  // 눈 없음
    rock_exposure: 0.3
  },

  plains: {
    temperature: 0.5,
    humidity: 0.6,
    erosion: 0.2,
    continentalness: 0.3,
    weirdness: 0.0,
    vegetation_color_r: 0.3,
    vegetation_color_g: 0.6,
    vegetation_color_b: 0.2,
    ground_color_r: 0.3,
    ground_color_g: 0.25,
    ground_color_b: 0.2,
    snow_start_height: 9999,
    rock_exposure: 0.1
  },

  lake: {
    temperature: 0.3,
    humidity: 1.0,
    erosion: 0.0,
    continentalness: -0.8,
    weirdness: 0.0,
    vegetation_color_r: 0.2,
    vegetation_color_g: 0.4,
    vegetation_color_b: 0.3,
    ground_color_r: 0.2,
    ground_color_g: 0.3,
    ground_color_b: 0.5,
    snow_start_height: 9999,
    rock_exposure: 0.0
  }
};
```

**블렌딩 예시:**
```
평지 + 호수 경계 (50% : 50%):
  temperature: (0.5 + 0.3) / 2 = 0.4
  humidity: (0.6 + 1.0) / 2 = 0.8
  ground_color_r: (0.3 + 0.2) / 2 = 0.25
  ground_color_g: (0.25 + 0.3) / 2 = 0.275
  ground_color_b: (0.2 + 0.5) / 2 = 0.35
  → 결과: 습한 갈색-회색 흙 (해변 색상!)
```

---

## 2. 바이옴 배치 시스템

### 2.1 좌표 시스템 설계

**그리드 기반 (채택)**
- 지형 크기: 100m x 100m
- 그리드 해상도: 1m x 1m (100 x 100 셀)
- 각 셀마다 바이옴 할당

### 2.2 바이옴 맵 생성 방식

**포인트 기반 영역 분배 + 파라미터 블렌딩**

```python
# Blender Python
import bpy
import numpy as np

# 1. 빈 바이옴 맵 생성 (100x100)
# 각 셀은 바이옴 파라미터 딕셔너리를 저장
biome_param_map = np.empty((100, 100), dtype=object)

# 2. Claude가 생성한 바이옴 포인트들
biome_points = [
    {"position": [15, 50], "params": {...}, "coverage": 0.25},
    {"position": [50, 50], "params": {...}, "coverage": 0.4},
    {"position": [85, 50], "params": {...}, "coverage": 0.25},
    {"position": [50, 85], "params": {...}, "coverage": 0.1}
]

# 3. 각 셀에 대해 영향력 기반 파라미터 계산
for x in range(100):
    for y in range(100):
        # 3-1. 각 바이옴 포인트의 영향력 계산 (거리 기반)
        influences = []
        for point in biome_points:
            distance = np.sqrt((x - point["position"][0])**2 +
                             (y - point["position"][1])**2)
            # 거리와 coverage를 고려한 영향력
            influence = point["coverage"] / (distance + 1.0)
            influences.append((influence, point["params"]))

        # 3-2. 영향력에 비례하여 파라미터 블렌딩
        blended_params = blend_parameters(influences)

        # 3-3. Perlin Noise 추가 (자연스러운 변화)
        noise_offset = perlin_noise(x * 0.1, y * 0.1)
        blended_params = apply_noise_variation(blended_params, noise_offset)

        biome_param_map[x, y] = blended_params

# 4. 결과: 100x100 맵 완성
# - 바이옴 포인트 근처: 해당 바이옴 파라미터
# - 경계 영역: 자동 블렌딩된 전환 바이옴 파라미터
# - Perlin Noise로 자연스러운 변화 추가
```

**파라미터 블렌딩 함수:**
```python
def blend_parameters(influences):
    """
    여러 바이옴의 영향력에 따라 파라미터 블렌딩

    예: 평지(70%) + 호수(30%) → 습한 평지 또는 해변 파라미터
    """
    # 영향력 정규화
    total_influence = sum(inf for inf, _ in influences)
    weights = [(inf / total_influence, params)
               for inf, params in influences]

    # 가중 평균으로 파라미터 블렌딩
    blended = {}
    for param_name in weights[0][1].keys():
        blended[param_name] = sum(
            weight * params[param_name]
            for weight, params in weights
        )

    return blended
```

---

## 3. Claude AI 통합

### 3.1 바이옴 포인트 기반 시스템

**핵심 개념:**
- Claude가 1~N개의 **바이옴 포인트**(중심점) 생성
- 각 포인트는 100x100 좌표계 상의 위치 + 바이옴 파라미터 + 영향력(coverage)
- 알고리즘이 전체 100x100 그리드를 자동으로 채움
- 경계 영역에서 파라미터가 자연스럽게 블렌딩되어 **새로운 바이옴 생성**
  - 예: 평지 + 바다 블렌딩 → 해변 바이옴 (Claude가 명시 안해도 자동 생성)

### 3.2 사용자 입력 분석

**입력 예시:**
```
"왼쪽은 눈 덮인 산맥, 중앙은 초원, 오른쪽은 사막, 그리고 아래쪽에 작은 호수"
```

**Claude 출력 (V1 파라미터):**
```json
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
        "snow_start_height": 1500,
        "rock_exposure": 0.7
      },
      "coverage": 0.25,
      "description": "snowy_mountain"
    },
    {
      "position": [50, 50],
      "biome_params": {
        "temperature": 0.5,
        "humidity": 0.6,
        "erosion": 0.2,
        "continentalness": 0.3,
        "weirdness": 0.0,
        "vegetation_color_r": 0.3,
        "vegetation_color_g": 0.6,
        "vegetation_color_b": 0.2,
        "ground_color_r": 0.3,
        "ground_color_g": 0.25,
        "ground_color_b": 0.2,
        "snow_start_height": 9999,
        "rock_exposure": 0.1
      },
      "coverage": 0.4,
      "description": "plains"
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
    },
    {
      "position": [50, 85],
      "biome_params": {
        "temperature": 0.3,
        "humidity": 1.0,
        "erosion": 0.0,
        "continentalness": -0.8,
        "weirdness": 0.0,
        "vegetation_color_r": 0.2,
        "vegetation_color_g": 0.4,
        "vegetation_color_b": 0.3,
        "ground_color_r": 0.2,
        "ground_color_g": 0.3,
        "ground_color_b": 0.5,
        "snow_start_height": 9999,
        "rock_exposure": 0.0
      },
      "coverage": 0.1,
      "description": "lake"
    }
  ],
  "blend_distance": 15
}
```

### 3.3 자동 바이옴 블렌딩

**경계 영역에서 자동 생성되는 바이옴 예시:**

```
평지(plains) + 바다(lake) 블렌딩 영역:
  → 해변(beach) 파라미터 자동 생성
  temperature: (0.5 + 0.3) / 2 = 0.4
  humidity: (0.6 + 1.0) / 2 = 0.8
  ground_color: 모래색으로 블렌딩

산악(mountain) + 평지(plains) 블렌딩 영역:
  → 산기슭(foothill) 파라미터 자동 생성
  erosion: (0.8 + 0.2) / 2 = 0.5
  snow_start_height: 점진적 증가

사막(desert) + 호수(lake) 블렌딩 영역:
  → 오아시스(oasis) 파라미터 자동 생성
  humidity: (0.1 + 1.0) / 2 = 0.55
  vegetation_density: 증가
```

**핵심:** Claude는 주요 바이옴만 정의하고, 경계의 전환 바이옴은 알고리즘이 자동 생성!

---

## 4. 구현 단계

### Phase 1: 기본 바이옴 시스템 (1주)
- [ ] 바이옴 파라미터 인터페이스 정의
- [ ] 5개 사전 정의 바이옴 생성
- [ ] 간단한 2-바이옴 블렌딩 테스트

### Phase 2: Claude AI 통합 (1주)
- [ ] Claude 프롬프트 설계 및 테스트
- [ ] 자연어 → 바이옴 레이아웃 변환

### Phase 3: Blender 구현 (2주)
- [ ] Geometry Nodes 기반 다중 바이옴 생성
- [ ] Perlin Noise 블렌딩 구현
- [ ] Material 시스템 개선

### Phase 4: UI/UX 개선 (1주)
- [ ] 프론트엔드 바이옴 프리셋 선택 UI
- [ ] 실시간 바이옴 맵 미리보기

---

## 5. 참고 자료

- Minecraft World Generation - Alan Zucconi
- Minecraft Wiki - Biomes
- Perlin Noise in Blender

---

## 6. 바이옴 생성 알고리즘 상세

### 6.1 전체 흐름

```
사용자 입력
    ↓
Claude AI (바이옴 포인트 1~N개 생성)
    ↓
100x100 그리드에 바이옴 포인트 배치
    ↓
거리 기반 영향력 계산 (Voronoi 다이어그램 유사)
    ↓
각 셀마다 가중 평균으로 파라미터 블렌딩
    ↓
Perlin Noise 추가 (자연스러운 변화)
    ↓
최종 100x100 바이옴 파라미터 맵 완성
```

### 6.2 영향력 계산 공식

```python
def calculate_influence(point, x, y):
    """
    바이옴 포인트가 특정 셀에 미치는 영향력 계산
    """
    distance = sqrt((x - point.x)^2 + (y - point.y)^2)

    # 영향력 = coverage / (거리 + 1)
    # coverage: 바이옴의 크기/중요도 (0.1 ~ 1.0)
    # +1: 거리 0일 때 무한대 방지
    influence = point.coverage / (distance + 1.0)

    return influence
```

### 6.3 블렌딩 예시

**상황:** 평지 바이옴과 호수 바이옴 사이의 셀 [50, 70]

```
평지 바이옴 포인트: [50, 50], coverage=0.4
호수 바이옴 포인트: [50, 85], coverage=0.1

셀 [50, 70]에서의 계산:
  - 평지 영향력: 0.4 / (20 + 1) = 0.019
  - 호수 영향력: 0.1 / (15 + 1) = 0.006

  정규화:
  - 평지 비율: 0.019 / 0.025 = 76%
  - 호수 비율: 0.006 / 0.025 = 24%

  블렌딩된 파라미터:
  - temperature: 0.5 * 0.76 + 0.3 * 0.24 = 0.45
  - humidity: 0.6 * 0.76 + 1.0 * 0.24 = 0.70
  - ground_color: [0.3,0.25,0.2] * 0.76 + [0.2,0.3,0.5] * 0.24
                = [0.28, 0.26, 0.27] (갈색+파란색 → 습한 흙색)

  → 결과: "습한 평지" 또는 "호수 주변" 바이옴 자동 생성!
```

### 6.4 자동 생성되는 전환 바이옴 예시

| 바이옴 A | 바이옴 B | 경계 블렌딩 결과 |
|---------|---------|----------------|
| 평지 | 바다/호수 | 해변 |
| 산악 | 평지 | 산기슭 |
| 사막 | 호수 | 오아시스 |
| 숲 | 산악 | 고산 숲 |
| 평지 | 사막 | 초원 |
| 눈산 | 평지 | 설원 |

**핵심:** Claude는 명시적으로 "해변"을 정의하지 않아도, 평지와 호수 파라미터가 블렌딩되면서 자연스럽게 해변 특성을 가진 바이옴이 생성됨!

---

## 7. V1 파라미터 확정

### 7.1 최종 파라미터 목록 (13개)

| 분류 | 파라미터 | 범위 | 설명 |
|-----|---------|------|------|
| **지형** | temperature | -1.0 ~ 1.0 | 온도 (눈 ~ 사막) |
| | humidity | 0.0 ~ 1.0 | 습도 (건조 ~ 습함) |
| | erosion | 0.0 ~ 1.0 | 침식도 (평평 ~ 험준) |
| | continentalness | -1.0 ~ 1.0 | 대륙성 (바다 ~ 내륙) |
| | weirdness | 0.0 ~ 1.0 | 기괴함 (일반 ~ 특이) |
| **식생 색상** | vegetation_color_r | 0.0 ~ 1.0 | 식생 Red |
| | vegetation_color_g | 0.0 ~ 1.0 | 식생 Green |
| | vegetation_color_b | 0.0 ~ 1.0 | 식생 Blue |
| **지표 색상** | ground_color_r | 0.0 ~ 1.0 | 지표 Red |
| | ground_color_g | 0.0 ~ 1.0 | 지표 Green |
| | ground_color_b | 0.0 ~ 1.0 | 지표 Blue |
| **기타** | snow_start_height | 0 ~ 5000 | 눈 시작 높이 (미터) |
| | rock_exposure | 0.0 ~ 1.0 | 바위 노출도 |

**특징:**
- ✅ 모든 파라미터 수치형 → 블렌딩 가능
- ✅ 13개로 제한 → Claude 부담 적음
- ✅ 확장 가능 → V2에서 파라미터 추가 예정

### 7.2 V2+ 확장 예정 파라미터

**Phase 2 추가 예정 (10개):**
- season (0.0~1.0: 봄~겨울 순환)
- vegetation_density (0.0~1.0)
- ground_roughness (0.0~1.0)
- fog_density (0.0~1.0)
- ambient_light_intensity (0.0~2.0)
- stratification (0.0~1.0: 지층 구조)
- lava_presence (0.0~1.0)
- water_presence (0.0~1.0)
- crystal_growth (0.0~1.0: 판타지)
- magic_particle_density (0.0~1.0: 판타지)

**Phase 3 추가 예정:**
- 더 세밀한 색상 제어
- 대기 효과
- 판타지 요소

---

## 8. 경사 기반 바위 노출도 (Slope-based Rock Exposure)

### 8.1 개념

**현실 세계 모방:**
- 경사가 급한 곳: 흙이 얇아지고 바위가 드러남
- 평평한 곳: 흙이 두껍게 쌓임

**마인크래프트 방식:**
- 흙 레이어 두께: y축 방향 3~5 블록
- 경사 높으면: 흙 레이어 제거 → 바위 자동 노출
- 수직 절벽: 완전히 바위만 노출

### 8.2 구현 방식

**Blender Geometry Nodes를 이용한 경사 계산:**

```python
# Blender Python 예시 (Geometry Nodes)
def apply_slope_based_rock_exposure(mesh):
    """
    메시의 각 정점에서 경사 계산하여 rock_exposure 조정
    """
    # 1. 메시의 각 면(face)의 법선 벡터 계산
    # 2. 법선과 수직 방향(0,0,1)의 각도 계산
    # 3. 각도가 클수록 (경사가 급할수록) rock_exposure 증가

    for vertex in mesh.vertices:
        # 정점 주변 면들의 평균 법선
        normal = vertex.normal

        # 법선과 수직 방향의 각도 (0° = 평평, 90° = 수직)
        slope_angle = arccos(dot(normal, [0, 0, 1]))

        # 경사도 (0.0 ~ 1.0)
        slope_factor = slope_angle / (π/2)  # 0~90° → 0.0~1.0

        # 기존 바이옴 rock_exposure에 경사 팩터 추가
        # slope_influence: 경사가 rock_exposure에 미치는 영향 (0.0~1.0)
        final_rock_exposure = lerp(
            biome_rock_exposure,       # 바이옴 기본값
            1.0,                       # 최대 바위 노출
            slope_factor * slope_influence
        )

        vertex.rock_exposure = final_rock_exposure
```

**Geometry Nodes 구현:**
```
Input Mesh
  → Position Node
  → Normal Node
  → Vector Math (Dot Product with [0,0,1])
  → Math (Arccos) → Slope Angle
  → Map Range (0~π/2 → 0~1) → Slope Factor
  → Mix (Biome Rock Exposure + Slope Factor) → Final Rock Exposure
  → Set Attribute ("rock_exposure")
  → Output Mesh
```

### 8.3 파라미터

**추가 파라미터 (V2 이후):**
```typescript
interface SlopeRockParams {
  slope_influence: number;  // 0.0 ~ 1.0 (경사가 rock_exposure에 미치는 영향)
  slope_threshold: number;  // 0.0 ~ 1.0 (이 값 이상의 경사에서만 작동)
}
```

**V1에서는:**
- `slope_influence`: 고정값 0.5 (중간 정도 영향)
- `slope_threshold`: 고정값 0.3 (약 27° 이상 경사)

### 8.4 블렌딩 공식

```python
def calculate_final_rock_exposure(biome_rock_exposure, slope_angle):
    """
    바이옴 파라미터 + 경사 기반 조정

    Args:
        biome_rock_exposure: 0.0 ~ 1.0 (바이옴에서 정의된 기본 바위 노출도)
        slope_angle: 0.0 ~ π/2 (경사 각도, 라디안)

    Returns:
        final_rock_exposure: 0.0 ~ 1.0
    """
    # 1. 경사도 계산 (0.0 = 평평, 1.0 = 수직)
    slope_factor = slope_angle / (math.pi / 2)

    # 2. 임계값 이하 경사는 무시
    if slope_factor < SLOPE_THRESHOLD:
        return biome_rock_exposure

    # 3. 임계값 이상 경사: 바위 노출도 증가
    # lerp(a, b, t) = a + (b - a) * t
    adjusted_factor = (slope_factor - SLOPE_THRESHOLD) / (1.0 - SLOPE_THRESHOLD)
    final_exposure = biome_rock_exposure + (1.0 - biome_rock_exposure) * adjusted_factor * SLOPE_INFLUENCE

    return min(final_exposure, 1.0)
```

### 8.5 예시

**케이스 1: 평평한 평지**
```
바이옴 rock_exposure: 0.1
경사 각도: 5° (거의 평평)
slope_factor: 0.09
→ 임계값 0.3 이하 → 바위 노출 없음
→ final_rock_exposure: 0.1 (바이옴 기본값 유지)
```

**케이스 2: 중간 경사 산악**
```
바이옴 rock_exposure: 0.7
경사 각도: 45° (중간 경사)
slope_factor: 0.5
slope_influence: 0.5
→ adjusted_factor: (0.5 - 0.3) / 0.7 = 0.29
→ final_rock_exposure: 0.7 + (1.0 - 0.7) * 0.29 * 0.5
                      = 0.7 + 0.043 = 0.74
```

**케이스 3: 수직 절벽**
```
바이옴 rock_exposure: 0.3 (낮은 바위 노출)
경사 각도: 85° (거의 수직)
slope_factor: 0.94
slope_influence: 0.5
→ adjusted_factor: (0.94 - 0.3) / 0.7 = 0.91
→ final_rock_exposure: 0.3 + (1.0 - 0.3) * 0.91 * 0.5
                      = 0.3 + 0.32 = 0.62
                      (절벽에서 바위 크게 증가!)
```

### 8.6 Material 시스템 통합

**Blender Shader Nodes:**
```
Geometry Node (Normal)
  → Vector Math (Dot Product with [0,0,1])
  → Math (Arccos)
  → ColorRamp (경사 → 바위 텍스처 믹스 비율)
  → Mix Shader
      Input 1: 흙 Material (Diffuse BSDF)
      Input 2: 바위 Material (Principled BSDF with Rock Texture)
  → Material Output
```

**ColorRamp 설정:**
```
Position 0.0 (평평): 100% 흙
Position 0.3 (27°): 100% 흙
Position 0.6 (54°): 50% 흙 / 50% 바위
Position 1.0 (90°): 100% 바위
```

### 8.7 자연스러운 효과

**이 기능으로 자동 생성되는 시각 효과:**
1. **산 정상:** 바이옴 파라미터로 눈 덮임
2. **급경사 면:** 자동으로 바위 드러남 (흙 얇음)
3. **계곡 바닥:** 흙 두껍게 쌓임 (바위 안보임)
4. **절벽:** 완전히 바위만 보임
5. **강둑:** 경사진 부분만 바위 노출

**현실 지형 침식 패턴 재현:**
- 물리적으로 정확: 중력 + 침식으로 경사면은 흙이 쌓이기 어려움
- 자연스러운 전환: 평지 → 중간 경사 → 절벽 순으로 바위 노출 증가

### 8.8 구현 우선순위

**Phase 2에서 구현 권장:**
- Phase 1: 바이옴 파라미터만으로 rock_exposure 사용
- Phase 2: Geometry Nodes 경사 계산 추가
- Phase 3: slope_influence 파라미터를 사용자가 조정 가능하게

**이유:**
- Phase 1에서 바이옴 시스템 안정화 우선
- Geometry Nodes 경사 계산은 복잡도 증가
- 사용자 피드백 후 세밀 조정 필요

---

## 9. Geometry Nodes 지형 메시 생성 (바이옴 파라미터 맵 → 실제 지형)

### 9.1 핵심 개념

**Geometry Nodes의 강력한 기능:**
- ✅ **각 정점마다 다른 파라미터 적용 가능**
- ✅ 100x100 그리드의 10,000개 정점 각각에 고유한 바이옴 파라미터 할당
- ✅ 위치에 따라 다른 느낌의 지형을 **하나의 메시에서** 합성

**예시:**
```
정점 [0, 0]: temperature=-0.7, erosion=0.8 → 눈 덮인 험준한 산
정점 [50, 50]: temperature=0.5, erosion=0.2 → 평평한 초원
정점 [100, 100]: temperature=0.9, erosion=0.3 → 완만한 사막

→ 하나의 메시에서 왼쪽은 산맥, 중앙은 평지, 오른쪽은 사막!
```

---

### 9.2 구현 방법 비교

#### **방법 1: Image Texture 샘플링** ✅ 추천 (V1)

**개념:**
- 100x100 바이옴 파라미터를 PNG 이미지로 저장 (각 파라미터마다 1개)
- Geometry Nodes에서 Position 기반으로 이미지 샘플링
- 각 정점의 XY 좌표로 해당 위치의 바이옴 파라미터 읽기

**장점:**
- 구현 간단
- 이미지로 바이옴 분포 시각화 가능 (클라이언트에 보여주기 좋음)
- Blender 이미지 샘플링 매우 빠름

**단점:**
- 13개 파라미터 = 13개 PNG 파일 필요
- 디스크 공간 사용 (100x100 픽셀 × 13개 ≈ 수백 KB)

**구현:**

```python
# === 1단계: Python - 바이옴 파라미터 맵을 이미지로 저장 ===
import numpy as np
from PIL import Image
import os

# 바이옴 파라미터 맵 (100x100, Section 2에서 생성)
biome_maps = {
    'temperature': np.array([[...], ...]),      # -1.0 ~ 1.0
    'humidity': np.array([[...], ...]),         # 0.0 ~ 1.0
    'erosion': np.array([[...], ...]),          # 0.0 ~ 1.0
    'continentalness': np.array([[...], ...]),  # -1.0 ~ 1.0
    'weirdness': np.array([[...], ...]),        # 0.0 ~ 1.0
    'vegetation_color_r': np.array([[...], ...]),
    'vegetation_color_g': np.array([[...], ...]),
    'vegetation_color_b': np.array([[...], ...]),
    'ground_color_r': np.array([[...], ...]),
    'ground_color_g': np.array([[...], ...]),
    'ground_color_b': np.array([[...], ...]),
    'snow_start_height': np.array([[...], ...]),  # 0 ~ 5000
    'rock_exposure': np.array([[...], ...])       # 0.0 ~ 1.0
}

# 각 파라미터를 PNG로 저장
output_dir = '/tmp/biome_maps/'
os.makedirs(output_dir, exist_ok=True)

for param_name, param_map in biome_maps.items():
    # 파라미터 범위에 따라 정규화 (0~255)
    if param_name in ['temperature', 'continentalness']:
        # -1.0 ~ 1.0 → 0 ~ 255
        normalized = ((param_map + 1.0) / 2.0 * 255).astype(np.uint8)
    elif param_name == 'snow_start_height':
        # 0 ~ 5000 → 0 ~ 255
        normalized = (param_map / 5000.0 * 255).astype(np.uint8)
    else:
        # 0.0 ~ 1.0 → 0 ~ 255
        normalized = (param_map * 255).astype(np.uint8)

    # PNG 저장 (Grayscale)
    img = Image.fromarray(normalized, mode='L')
    img.save(f'{output_dir}biome_{param_name}.png')

print(f'✅ {len(biome_maps)}개 바이옴 맵 이미지 생성 완료')
```

```python
# === 2단계: Python - Blender에서 100x100 그리드 메시 생성 ===
import bpy

# 기존 메시 삭제
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 100x100 그리드 생성 (size=100m)
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=100,
    y_subdivisions=100,
    size=100,
    location=(0, 0, 0)
)

terrain_obj = bpy.context.active_object
terrain_obj.name = "BiomeTerrain"

# 이미지 로드 (Geometry Nodes에서 사용)
for param_name in biome_maps.keys():
    img_path = f'{output_dir}biome_{param_name}.png'
    bpy.data.images.load(img_path)

print(f'✅ 100x100 그리드 메시 생성 완료 (10,201개 정점)')
```

**Geometry Nodes 구조:**

```
[Group Input: Mesh (100x100 Grid)]
  ↓
[Position Node] → [Separate XYZ]
  ↓              ↓
  X (0~100)      Y (0~100)
  ↓              ↓
[Math: Divide by 100] (X/100, Y/100)  # 0~1 범위로 정규화
  ↓
[Combine XY] → UV Coordinate (0~1, 0~1)
  ↓
┌─────────────────────────────────────────┐
│  각 파라미터마다 반복 (13개)             │
├─────────────────────────────────────────┤
│ [Image Texture: biome_temperature.png]  │
│   - Vector 입력: UV Coordinate          │
│   - Interpolation: Linear               │
│   - Color 출력 (Grayscale 0~1)          │
│   ↓                                      │
│ [Map Range]                              │
│   - Input: 0~1 (이미지 값)               │
│   - Output: -1~1 (temperature 범위)      │
│   ↓                                      │
│ [Store Named Attribute]                  │
│   - Name: "temperature"                  │
│   - Value: 변환된 값                      │
└─────────────────────────────────────────┘
  ↓
[Named Attribute: "temperature"] ─┐
[Named Attribute: "erosion"] ─────┤
[Named Attribute: "continentalness"] ─┤
[Named Attribute: "weirdness"] ───────┤
  ↓                                    ↓
[Position Node] → [Noise Texture]
  - Scale: 0.05 (Perlin Noise)
  - Detail: 5
  ↓
[Math Nodes: 지형 높이 계산]
  Height = Noise * erosion * 20.0            # 침식도 높을수록 험준
  Height += continentalness * 10.0           # 대륙성 높을수록 고지대
  Height += weirdness * Noise(scale=0.2) * 5.0  # 기괴함 추가
  Height *= (1.0 - temperature * 0.2)        # 온도 낮을수록 산 높음
  ↓
[Set Position]
  - Offset: (0, 0, Height)
  ↓
[Set Shade Smooth]
  ↓
[Group Output: Mesh]
```

**결과:**
- 각 정점의 XY 위치에 따라 이미지에서 바이옴 파라미터 샘플링
- 정점 [15, 50]: temperature=-0.7, erosion=0.8 (눈 덮인 산맥)
- 정점 [50, 50]: temperature=0.5, erosion=0.2 (평평한 초원)
- 정점 [85, 50]: temperature=0.9, erosion=0.3 (완만한 사막)

---

#### **방법 2: Vertex Attribute 직접 할당** ⚡ 최고 성능 (V2+)

**개념:**
- Python에서 메시 생성 시 각 정점에 바이옴 파라미터를 **Attribute로 직접 저장**
- Geometry Nodes는 이미 저장된 Attribute만 읽어서 사용
- 이미지 파일 불필요 (모든 데이터가 메시에 내장)

**장점:**
- **가장 빠름** (13.8M vertices/sec read, 10.8M/sec write)
- 이미지 파일 불필요 (메모리 효율적)
- Geometry Nodes 매우 간단해짐

**단점:**
- Python 코드 복잡
- 바이옴 맵 변경 시 메시 재생성 필요
- 바이옴 분포 시각화 어려움 (이미지 없음)

**방법 1과의 차이:**
| 측면 | 방법 1 (Image) | 방법 2 (Attribute) |
|-----|---------------|-------------------|
| 파라미터 저장 | PNG 파일 13개 | 메시 내부 Attribute |
| 샘플링 방식 | Image Texture 노드 | Named Attribute 노드 |
| 시각화 | ✅ 이미지로 확인 가능 | ❌ 어려움 |
| 성능 | 빠름 | 매우 빠름 |
| 구현 난이도 | 쉬움 | 중간 |

**구현:**

```python
# === Python - Vertex Attribute로 바이옴 파라미터 저장 ===
import bpy
import numpy as np

# 1. 100x100 그리드 생성
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=100,
    y_subdivisions=100,
    size=100
)
mesh = bpy.context.object.data

# 2. 바이옴 파라미터 맵 (100x100 numpy array)
temperature_map = np.array([[...], [...], ...])  # shape: (100, 100)
erosion_map = np.array([[...], [...], ...])
# ... (13개 파라미터 전부)

# 3. Custom Attribute 생성 및 할당
# 주의: 그리드 메시는 정점 개수가 (101, 101) = 10,201개
# 바이옴 맵은 (100, 100) = 10,000개이므로 보간 필요

def create_vertex_attribute(mesh, name, param_map):
    """
    바이옴 파라미터 맵을 정점 Attribute로 할당

    Args:
        mesh: Blender Mesh 객체
        name: Attribute 이름 (예: "temperature")
        param_map: (100, 100) numpy array
    """
    # Attribute 생성
    attr = mesh.attributes.new(name=name, type='FLOAT', domain='POINT')

    # 정점 개수 (101 x 101 = 10,201)
    vertex_count = len(mesh.vertices)
    values = np.zeros(vertex_count)

    # 각 정점의 XY 좌표로 바이옴 맵 샘플링
    for i, vertex in enumerate(mesh.vertices):
        x = vertex.co.x + 50  # -50~50 → 0~100
        y = vertex.co.y + 50

        # 100x100 그리드 인덱스
        grid_x = int(np.clip(x, 0, 99))
        grid_y = int(np.clip(y, 0, 99))

        # 바이옴 파라미터 값
        values[i] = param_map[grid_y, grid_x]

    # foreach_set으로 빠르게 할당
    attr.data.foreach_set('value', values)

# 모든 파라미터 할당
create_vertex_attribute(mesh, 'temperature', temperature_map)
create_vertex_attribute(mesh, 'humidity', humidity_map)
create_vertex_attribute(mesh, 'erosion', erosion_map)
create_vertex_attribute(mesh, 'continentalness', continentalness_map)
create_vertex_attribute(mesh, 'weirdness', weirdness_map)
create_vertex_attribute(mesh, 'snow_start_height', snow_start_height_map)
create_vertex_attribute(mesh, 'rock_exposure', rock_exposure_map)

# 색상 파라미터 (FLOAT_COLOR 타입)
def create_color_attribute(mesh, name, r_map, g_map, b_map):
    attr = mesh.attributes.new(name=name, type='FLOAT_COLOR', domain='POINT')
    vertex_count = len(mesh.vertices)
    colors = np.zeros((vertex_count, 4))  # RGBA

    for i, vertex in enumerate(mesh.vertices):
        x = int(np.clip(vertex.co.x + 50, 0, 99))
        y = int(np.clip(vertex.co.y + 50, 0, 99))

        colors[i] = [r_map[y, x], g_map[y, x], b_map[y, x], 1.0]

    attr.data.foreach_set('color', colors.flatten())

create_color_attribute(mesh, 'vegetation_color',
                       vegetation_color_r_map,
                       vegetation_color_g_map,
                       vegetation_color_b_map)

create_color_attribute(mesh, 'ground_color',
                       ground_color_r_map,
                       ground_color_g_map,
                       ground_color_b_map)

print('✅ 13개 바이옴 파라미터 Attribute 할당 완료')
```

**Geometry Nodes 구조 (매우 간단!):**

```
[Group Input: Mesh]
  ↓
[Named Attribute: "temperature"] ─┐
[Named Attribute: "erosion"] ─────┤
[Named Attribute: "continentalness"] ─┤
[Named Attribute: "weirdness"] ───────┤
  ↓                                    ↓
[Position Node] → [Noise Texture]
  ↓
[지형 높이 계산 (방법 1과 동일)]
  ↓
[Set Position]
  ↓
[Set Shade Smooth]
  ↓
[Group Output]
```

---

### 9.3 Material 적용 (Shader Nodes)

**지형 높이는 Geometry Nodes, 색상은 Shader Nodes로 분리**

```
[Shader Nodes]

[Named Attribute: "temperature"] ─┐
  ↓                                 ↓
[ColorRamp: 눈 시작 온도]
  - Position 0.0 (-1.0): White (눈)
  - Position 0.6 (-0.3): White (눈)
  - Position 1.0 (1.0): Transparent
  ↓
[Mix Shader] ──────────────────────┐
  Factor: ColorRamp 출력            │
  Shader 1: Snow Material           │
  Shader 2: Ground Material         │
  ↓                                 ↓
[Named Attribute: "ground_color"] ─┤
  ↓                                 │
[Principled BSDF]                   │
  - Base Color: ground_color        │
  ↓                                 │
[Named Attribute: "rock_exposure"] ─┤
  ↓                                 │
[Mix Shader]                        │
  Factor: rock_exposure             │
  Shader 1: Ground Material (위)    │
  Shader 2: Rock Material           │
  ↓
[Material Output]
```

---

### 9.4 최종 추천 방식

**V1 (초기 구현):** 방법 1 (Image Texture) ✅
- 구현 간단
- 이미지로 바이옴 분포 시각화 가능 (클라이언트에 미리보기 전송)
- 충분히 빠름

**V2 (최적화):** 방법 1 + 방법 2 혼합 🔥
- **핵심 파라미터 (5개):** Attribute로 저장 (temperature, erosion, continentalness, humidity, weirdness)
  - 지형 높이 계산에 사용 (Geometry Nodes)
- **시각 파라미터 (8개):** Image Texture 유지
  - Material에서만 사용 (Shader Nodes)
  - 이미지로 클라이언트에 미리보기 전송 가능

**혼합 방식의 장점:**
```python
# 핵심 파라미터만 Attribute (5개)
create_vertex_attribute(mesh, 'temperature', temperature_map)
create_vertex_attribute(mesh, 'erosion', erosion_map)
create_vertex_attribute(mesh, 'continentalness', continentalness_map)
create_vertex_attribute(mesh, 'humidity', humidity_map)
create_vertex_attribute(mesh, 'weirdness', weirdness_map)

# 시각 파라미터는 Image (8개)
# - vegetation_color_r/g/b.png
# - ground_color_r/g/b.png
# - snow_start_height.png
# - rock_exposure.png
```

**결과:**
- Geometry Nodes: Attribute 읽기 (매우 빠름)
- Shader Nodes: Image 샘플링 (충분히 빠름)
- 클라이언트: 8개 이미지로 바이옴 분포 미리보기

---

### 9.5 실제 사용 예시

**사용자 요청:**
```
"왼쪽은 눈 덮인 산맥, 중앙은 초원, 오른쪽은 사막"
```

**처리 흐름:**
```
1. Claude AI → 바이옴 포인트 3개 생성
   - [15, 50]: snowy_mountain (temperature=-0.7, erosion=0.8)
   - [50, 50]: plains (temperature=0.5, erosion=0.2)
   - [85, 50]: desert (temperature=0.9, erosion=0.3)

2. Python → 100x100 바이옴 파라미터 맵 생성
   - 거리 기반 블렌딩
   - 경계 영역 자동 전환 바이옴 생성

3. Python → 이미지/Attribute 저장
   - 방법 1: 13개 PNG 저장
   - 방법 2: 13개 Attribute 저장

4. Geometry Nodes → 지형 메시 생성
   - 정점 [15, 50]: temperature=-0.7, erosion=0.8
     → Height = Noise * 0.8 * 20.0 + 0.6 * 10.0 = 높은 산
   - 정점 [50, 50]: temperature=0.5, erosion=0.2
     → Height = Noise * 0.2 * 20.0 + 0.3 * 10.0 = 평지
   - 정점 [85, 50]: temperature=0.9, erosion=0.3
     → Height = Noise * 0.3 * 20.0 + 0.5 * 10.0 = 완만한 언덕

5. Shader Nodes → Material 적용
   - 정점 [15, 50]: temperature=-0.7 → 눈 덮임 (흰색)
   - 정점 [50, 50]: ground_color=[0.3, 0.25, 0.2] → 갈색 흙
   - 정점 [85, 50]: ground_color=[0.9, 0.8, 0.6] → 노란 모래
```

**최종 결과:**
- 하나의 메시에 왼쪽 산맥, 중앙 평지, 오른쪽 사막 모두 포함
- 경계 영역은 자연스럽게 블렌딩 (산기슭, 초원-사막 전환)
- 각 정점마다 고유한 높이와 색상

---

## 10. 결정 필요 사항

1. **바이옴 포인트 개수:** 최대 개수? (추천: 3~10개)
2. **좌표 해상도:** 1m x 1m 확정? (추천: 유지)
3. **영향력 계산 함수:** 선형 (1/d) 확정? (추천: 유지)
4. **블렌딩 거리:** Perlin Noise 스케일? (추천: 0.1)
5. **UI 방식:** 자연어만? 바이옴 포인트 수동 추가?
6. **구현 방식:** 방법 1 (Image) vs 방법 2 (Attribute) vs 혼합? (추천: V1은 방법 1)
