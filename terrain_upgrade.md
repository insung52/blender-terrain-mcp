# 지형 생성 시스템 - 현재 구현 상태

## 1. 바이옴 시스템 개요

### 1.1 바이옴 파라미터 (16개)

```typescript
interface BiomeParametersV1 {
  // === 핵심 지형 파라미터 (5개) ===
  temperature: number;      // -1.0 ~ 1.0
  humidity: number;         // 0.0 ~ 1.0
  erosion: number;          // 0.0 ~ 1.0
  continentalness: number;  // -1.0 ~ 1.0
  weirdness: number;        // 0.0 ~ 1.0

  // === 식생 색상 (3개) ===
  vegetation_color_r: number;  // 0.0 ~ 1.0
  vegetation_color_g: number;
  vegetation_color_b: number;

  // === 지표 색상 (3개) ===
  ground_color_r: number;  // 0.0 ~ 1.0
  ground_color_g: number;
  ground_color_b: number;

  // === 바위 색상 (3개) - 경사진 곳 노출 ===
  rock_color_r: number;  // 0.0 ~ 1.0
  rock_color_g: number;
  rock_color_b: number;

  // === 추가 파라미터 (2개) ===
  snow_start_height: number;  // 미터
  rock_exposure: number;      // 0.0 ~ 1.0
}
```

---

## 2. 지형 생성 파이프라인

### 2.1 전체 흐름

```
사용자 자연어 입력
    ↓
Claude AI (바이옴 포인트 생성)
    ↓
Weighted Voronoi Diagram (WVD) + Gaussian Blur
    ↓
16개 파라미터 맵 (1000x1000 PNG, 16bit)
    ↓
Blender Geometry Nodes (지형 메시 생성)
    ↓
Material Shader Nodes (색상/눈/바위 적용)
    ↓
최종 .blend 파일 + 프리뷰 이미지
```

### 2.2 바이옴 맵 생성 (Python)

**파일:** `src/blender-scripts/biome_generator_wvd.py`

**알고리즘:**
1. **Weighted Voronoi Diagram**: 각 픽셀을 가장 가까운 바이옴에 할당
   - Coverage가 클수록 영향 범위 넓어짐
   - Multi-octave noise로 자연스러운 경계
2. **Gaussian Blur** (blur_radius=100): 경계 블렌딩
   - `mode='nearest'`: 맵 경계에서 값 복제 (외삽 방지)
3. **16bit PNG 저장**: 0~65535 범위 (0.76cm 정밀도)

**주요 설정:**
```python
grid_size = 1000  # 1000x1000 해상도
blur_radius = 100  # 가우시안 블러 반경
```

---

## 3. Blender 지형 생성 (Geometry Nodes)

### 3.1 메시 초기화

```python
# 200×200 그리드 생성
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=200,
    y_subdivisions=200,
    size=100  # 100m × 100m
)

# Subdivision Surface (Level 3)
# 200×200 → 1600×1600 = 2.5M vertices
```

### 3.2 높이 계산 알고리즘

**파일:** `src/blender-scripts/biome_terrain_blender.py:490-850`

#### Phase 1: Continentalness → 기본 고도

```python
# -1.0 ~ 1.0 → -50m ~ 1500m
base_height = map_range(continentalness, -1~1, -50~1500)
```

#### Phase 2: Multi-Octave Noise (6단계)

```python
# Octave 1: Large-scale (scale=0.005) × 2.0
# Octave 2: Medium (scale=0.02) × 0.8
# Octave 3: Small (scale=0.1) × 0.05
# Octave 4: Micro (scale=1.0) × 0.005
# Octave 5: Fine (scale=3.0) × 0.005
# Octave 6: Ultra-fine (scale=50.0) × 0.05

combined_noise = sum(octaves)
# 중심값 제거: combined_noise -= 0.85
```

**중요:** Noise 중심값(0.85) 제거로 평지에서 불필요한 높이 추가 방지

#### Phase 3: Erosion → 높이 변동폭

```python
# Erosion 제곱으로 산-평지 차이 극대화
erosion_squared = erosion ** 2.0

# 0~1 → 10m~1000m (최소 10m로 완전 평평 방지)
variation_range = map_range(erosion_squared, 0~1, 10~1000)

height_variation = combined_noise × variation_range
```

**효과:**
- 평지 (erosion=0.1): 0.01² × 1000m = 10m 변동
- 산 (erosion=0.9): 0.81² × 1000m = 656m 변동

#### Phase 4: Weirdness → 특수 지형 (Ridge)

```python
# Voronoi Distance로 능선 생성
voronoi = voronoi_texture(scale=0.1)
ridge_mask = 1.0 - |distance - 0.5| × 2.0
ridge_mask = pow(ridge_mask, 2.0)  # Sharpen

ridge_height = ridge_mask × 200m × erosion × weirdness
```

#### Phase 5: Valley (계곡) 침식

```python
valley_mask = (1.0 - continentalness) / 2.0
valley_strength = humidity × 100m
valley_depth = valley_mask × valley_strength
```

#### 최종 높이 합성

```python
final_height = base_height + height_variation + ridge_height - valley_depth
```

---

## 4. Material 시스템

### 4.1 구조

```
Ground Material (지표)
    ↓
Snow Material (높이 기반) - 먼저 적용
    ↓
Rock Material (경사도 기반) - 나중 적용
```

### 4.2 Specular 설정 (무광)

```python
ground_bsdf.inputs["Roughness"] = 1.0
ground_bsdf.inputs["Specular IOR Level"] = 0.0

snow_bsdf.inputs["Roughness"] = 0.9
snow_bsdf.inputs["Specular IOR Level"] = 0.1

rock_bsdf.inputs["Roughness"] = 1.0
rock_bsdf.inputs["Specular IOR Level"] = 0.0
```

### 4.3 Snow 적용 (Temperature 기반)

```python
# Temperature에 따라 눈선 높이 변화
# -1.0 ~ 1.0 → 500m ~ 4000m
snowline_height = map_range(temperature, -1~1, 500~4000)

# 랜덤 노이즈 추가 (±30m)
noise = noise_texture(scale=5.0)
noise_offset = map_range(noise, 0~1, -30~30)
height_with_noise = vertex_height + noise_offset

# 눈선 ±50m에서 부드럽게 전환
snow_factor = map_range(
    height_with_noise,
    from_min = snowline_height - 50,
    from_max = snowline_height + 50,
    to_min = 0.0,
    to_max = 1.0
)

mix_snow(ground, snow, snow_factor)
```

### 4.4 Rock 적용 (경사도 기반)

```python
# Normal.Z로 경사도 계산
slope = 1.0 - normal.Z

# rock_exposure로 임계값 조정
# 낮출수록 더 쉽게 바위 노출
threshold = 0.5 - rock_exposure × 0.5

# 경사 → 바위 블렌딩
rock_factor = map_range(slope, threshold, threshold+0.2, 0, 1)

# Snow 위에 Rock 적용
mix_rock(snow_result, rock, rock_factor)
```

---

## 5. Claude AI 프롬프트 가이드라인

### 5.1 바이옴 포인트 배치

**파일:** `src/services/biomeService.ts:72-101`

```typescript
// Coverage 규칙
- Mountains: 0.05~0.15 (작게, 뾰족한 봉우리)
- Plains/Forests: 0.25~0.35
- Lakes/Swamps: 0.15~0.25

// Erosion 가이드라인
- Mountains: 0.7~0.9 (험준)
- Plains/Grasslands: 0.1~0.2 (완만)
- Forests: 0.3~0.5 (구릉)
- Perfectly flat: 0.0 (명시적 요청 시만)

// Continentalness & Water
- Shallow water (lakes, ponds): -0.1 ~ -0.3
  NEVER -0.8 unless "deep ocean" explicitly requested
- Swamps: continentalness = 0.0, erosion = 0.3
  (지면 높이에 erosion으로 웅덩이 생성)
- Deep ocean: -0.8 ~ -1.0 (명시적 요청 시만)
```

### 5.2 사전 정의 프리셋

**파일:** `src/types/biome.ts`

- `snowy_mountain`: snow_start_height = **750m** (50% 낮춤)
- `desert`: sand color, no snow
- `plains`: grass green
- `lake`: shallow water (-0.3)
- `forest`: medium erosion

---

## 6. 주요 버그 수정 내역

### 6.1 Noise 중심값 문제

**문제:** Noise 출력 0.0~1.7, 평균 0.85 → 평지도 85m 높이 추가

**해결:**
```python
# biome_terrain_blender.py:619-630
combined_noise_raw = octave_1 + ... + octave_6
center_noise = combined_noise_raw - 0.85  # 중심값 제거
```

### 6.2 Gaussian Blur 경계 문제

**문제:** `mode='reflect'` → 경계 반사로 예상치 못한 값 생성

**해결:**
```python
# biome_generator_wvd.py:266
gaussian_filter(normalized, sigma=blur_radius, mode='nearest')
```

### 6.3 Material 순서 문제

**문제:** Rock → Snow 순서로 경사진 곳에도 눈 쌓임

**해결:**
```python
# biome_terrain_blender.py:873-915
# Snow 먼저 적용 → Rock 나중 적용
# 경사진 곳은 눈 위에 바위 드러남
```

---

## 7. 파일 구조

```
src/
  ├── types/biome.ts           # 바이옴 타입 정의 (16 params)
  ├── services/biomeService.ts # Claude AI 프롬프트
  └── blender-scripts/
      ├── biome_generator_wvd.py      # 바이옴 맵 생성 (WVD)
      └── biome_terrain_blender.py    # Blender 지형 생성
```

---

## 8. 성능 사양

```
Grid: 200×200 → Subdivision Level 3 → 1600×1600
Vertices: 2,560,000
Biome Maps: 1000×1000 × 16개 PNG (16bit)
Memory: ~100MB (render)
Render Time (EEVEE_NEXT): ~5초
```

---

## 9. 향후 개선 사항

### 9.1 물 시스템 구현 (진행 중)

**현재 문제:**
- 호수/바다 바이옴의 ground_color가 파란색으로 설정됨
- 실제 물처럼 보이지 않음 (투명도, 깊이감, 반사 없음)

**구현 계획: 직육면체 물 메시 + Volume Shader**

```
구조:
┌─────────────────────┐
│   수면 (Z=0)        │ ← 투명한 물 표면
│                     │
│   Volume Shader     │ ← 깊이에 따라 파란색 진해짐
│   (파란색 흡수)      │
│                     │
└─────────────────────┘
  바닥 (Z=-400)
```

**상세 스펙:**
1. **메시 생성**
   - 크기: 1000m × 1000m × 400m (지형 전체 커버)
   - 위치: 수면(윗면) Z=0, 바닥면 Z=-400
   - 타입: 단순 큐브 메시 (최적화 없이 먼저 구현)

2. **Material 설정**
   - **Surface Shader:**
     - Glass BSDF 또는 Principled BSDF
     - Transmission = 0.9~0.95 (투명도 90~95%)
     - Roughness = 0.05 (약간의 수면 반사)
     - IOR = 1.333 (물의 굴절률)

   - **Volume Shader:**
     - Volume Absorption (파란색 흡수)
     - Color = (0.1, 0.3, 0.6) 파란색
     - Density = 0.005~0.02 (조정 필요)
     - 효과: 깊이 10m → 밝은 파랑, 100m → 중간 파랑, 400m → 진한 파랑

3. **렌더링 효과**
   - ✅ 얕은 호수: 바닥 지형 보임 + 밝은 파란색
   - ✅ 깊은 바다: 어두운 진한 파란색
   - ✅ 자연스러운 깊이 그라데이션
   - ✅ 수면 반사/굴절 효과

4. **향후 확장**
   - [ ] Displacement Modifier로 물결 애니메이션
   - [ ] Wave Texture로 파도 표현
   - [ ] Geometry Nodes로 continentalness < 0 영역만 물 메시 생성 (최적화)
   - [ ] 호수/강/바다 물 색상 차별화 (온도, 깊이 기반)

**파일 수정 대상:**
- `src/blender-scripts/biome_terrain_blender.py` (물 메시 생성 추가)

---

### 9.2 단기
- [ ] Erosion 제곱 power 값 조정 가능하게
- [ ] Weirdness 절벽/메사 효과 강화
- [ ] 바이옴 프리셋 추가 (늪지대, 툰드라 등)
- [ ] 프리뷰 렌더링 설정 개선 (그림자/반사 끄기, Diffuse만)

### 9.3 중기
- [ ] Adaptive LOD (거리 기반 해상도)
- [ ] Displacement Texture 활용
- [ ] Normal Map 생성
- [ ] 나무/식생 오브젝트 배치 (Geometry Nodes)

### 9.4 장기
- [ ] 실시간 프리뷰 (클라이언트)
- [ ] 바이옴 포인트 수동 편집 UI
- [ ] Export to GLTF/FBX
- [ ] 도로와 지형 메시 자연스러운 연결
