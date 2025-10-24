간단한 나무 배치

C:\graphics\buildup\blender-terrain-mcp\assets\objects\tree : 나무 관련 오브젝트들 폴더

반복문 (대충 1000번)

반복문 내부에서, 랜덤 x y 좌표의 지형들 정보 가져오기

각 포인트의 정보를 읽고, tree 폴더 안의 general(기본, 평지나 숲), big(평지나 숲, 매우 낮은 확률로 생성), tropical(열대), desert(사막, 조금 낮은 확률로 생성) 중 선택

각 분류 별 생성 확률에 따라서 나무를 배치할지 말지 결정함.

배치하기로 결정됬다면, 그 폴더 안의 아무 폴더나 선택. (tree/general 내부에는 여러 나무 모델들이 포함된 폴더들이 여러개 있음)

이후 선택된 폴더 내부의 gltf 파일을 지형에 그 위치에 배치

+ 랜덤 오브젝트 scale(비율 고정), rotation(z축 방향만)

# 지형 오브젝트 배치 구현 계획

## 📋 목표
- 도로를 포함한 지형에 바이옴 기반 오브젝트 배치 (나무, 풀, 바위 등)
- 사용자가 "오브젝트 생성" 버튼 클릭 → 해당 지형에 자동 배치

---

## 0️⃣ 사용 가능한 정보 (총 19개)

특정 위치 (x, y)에서 얻을 수 있는 모든 데이터:

### 📸 A. Biome Map 이미지 픽셀 읽기 (16개)

위치: `output/biome_<terrain_id>/biome_maps/biome_*.png` (16bit PNG, 1000x1000 해상도)

| # | 파라미터 | 범위 | 타입 | 설명 | 오브젝트 배치 활용 예시 |
|---|---------|------|------|------|---------------------|
| 1 | **temperature** | -1.0 ~ 1.0 | float | 온도 (극한 추위 ~ 작열) | 🌲 나무 종류 (침엽수 vs 활엽수) |
| 2 | **humidity** | 0.0 ~ 1.0 | float | 습도 (건조 ~ 열대) | 💧 식물 밀도, 물가 식생 |
| 3 | **erosion** | 0.0 ~ 1.0 | float | 침식도 (평평 ~ 험준) | 🪨 바위 배치 확률 증가 |
| 4 | **continentalness** | -1.0 ~ 1.0 | float | 대륙성 (바다 ~ 고원) | 🌊 물 아래(< -0.2) = 배치 안함 |
| 5 | **weirdness** | 0.0 ~ 1.0 | float | 특이도 (일반 ~ 특이) | 🔮 특수 오브젝트 (버섯, 크리스탈 등) |
| 6 | **vegetation_color_r** | 0.0 ~ 1.0 | float | 식생 색상 R | 🎨 나무/풀 색상 변형 |
| 7 | **vegetation_color_g** | 0.0 ~ 1.0 | float | 식생 색상 G | 🎨 나무/풀 색상 변형 |
| 8 | **vegetation_color_b** | 0.0 ~ 1.0 | float | 식생 색상 B | 🎨 나무/풀 색상 변형 |
| 9 | **ground_color_r** | 0.0 ~ 1.0 | float | 지표 색상 R | 🟫 지면 타입 구분 (사막/초원/설원) |
| 10 | **ground_color_g** | 0.0 ~ 1.0 | float | 지표 색상 G | 🟫 지면 타입 구분 |
| 11 | **ground_color_b** | 0.0 ~ 1.0 | float | 지표 색상 B | 🟫 지면 타입 구분 |
| 12 | **rock_color_r** | 0.0 ~ 1.0 | float | 바위 색상 R | 🪨 바위 색상 변형 |
| 13 | **rock_color_g** | 0.0 ~ 1.0 | float | 바위 색상 G | 🪨 바위 색상 변형 |
| 14 | **rock_color_b** | 0.0 ~ 1.0 | float | 바위 색상 B | 🪨 바위 색상 변형 |
| 15 | **snow_start_height** | 0 ~ 5000m | float | 눈 시작 고도 | ❄️ 설원 오브젝트 전환점 |
| 16 | **rock_exposure** | 0.0 ~ 1.0 | float | 바위 노출도 | 🪨 바위 배치 확률 |

**읽기 방법:**
```python
# 16bit PNG 로드 (0~65535)
from PIL import Image
img = Image.open(f'{biome_maps_dir}/biome_temperature.png')
pixels = list(img.getdata())

# 픽셀 좌표 계산 (x, y는 월드 좌표 0~1000m)
img_x = int(x / 1000 * 1024)  # 1000m → 1024px
img_y = int(y / 1000 * 1024)
pixel_value = pixels[img_y * 1024 + img_x]

# 값 역정규화
if param_name == 'temperature':
    value = (pixel_value / 65535) * 2 - 1  # 0~65535 → -1~1
elif param_name == 'snow_start_height':
    value = (pixel_value / 65535) * 5000    # 0~65535 → 0~5000
else:
    value = pixel_value / 65535             # 0~65535 → 0~1
```

---

### 🎯 B. Blender Raycast 실시간 계산 (3개)

```python
hit, location, normal, face_index, obj, matrix = scene.ray_cast(
    view_layer,
    origin=(x, y, 1000),  # 위에서 아래로
    direction=(0, 0, -1)
)
```

| # | 값 | 타입 | 설명 | 오브젝트 배치 활용 예시 |
|---|---|------|------|---------------------|
| 17 | **z (height)** | float | 지형 높이 (미터) | 🏔️ 고도 기반 식생대 (500m 이하 = 활엽수, 1000m+ = 침엽수) |
| 18 | **normal** | Vector3 | 법선 벡터 (경사 방향) | ⛰️ 경사도 계산, 오브젝트 회전 정렬 |
| 19 | **face_index** | int | 충돌한 면 인덱스 | 🔍 메시 데이터 접근 (필요시) |

**파생 계산:**
```python
# 경사도 (Slope Angle)
slope_angle = math.degrees(math.acos(normal.z))  # 0° = 평지, 90° = 절벽
# ✅ 활용: 경사 > 45° → 나무 배치 안함, 바위만 배치

# 평탄도 (Flatness)
flatness = normal.z  # 1.0 = 완전 평지, 0.0 = 수직 절벽
# ✅ 활용: 평탄도 > 0.9 → 건물/구조물 배치 가능

# 경사 방향 (Slope Direction)
slope_direction = math.atan2(normal.y, normal.x)  # 라디안
# ✅ 활용: 남향 경사 = 더 따뜻 → 특정 식물 선호
```

---

### 📏 C. 추가 계산 가능한 값

| 값 | 계산 방법 | 활용 |
|----|----------|------|
| **distance_to_road** | Road 메시 버텍스와의 최소 2D 거리 | 🛣️ 도로 < 2m = 배치 안함, 2~5m = 가로수 |
| **slope_angle** | `math.degrees(math.acos(normal.z))` | ⛰️ 경사도 기반 오브젝트 제한 |
| **flatness** | `normal.z` | 🏗️ 건물 배치 가능 여부 |

---

### 💡 종합 활용 예시

```python
# 특정 위치 (x, y)에서 오브젝트 타입 결정
def determine_object_at_position(x, y):
    # 1. Raycast로 기본 정보 얻기
    hit, location, normal, _, _, _ = scene.ray_cast(view_layer, (x, y, 1000), (0, 0, -1))
    if not hit:
        return None  # 지형 없음

    z = location.z
    slope_angle = math.degrees(math.acos(normal.z))

    # 2. Biome map 픽셀 읽기 (16개 파라미터)
    temperature = read_biome_pixel('temperature', x, y)      # -1~1
    humidity = read_biome_pixel('humidity', x, y)            # 0~1
    erosion = read_biome_pixel('erosion', x, y)              # 0~1
    continentalness = read_biome_pixel('continentalness', x, y)  # -1~1
    snow_start_height = read_biome_pixel('snow_start_height', x, y)  # 0~5000

    # 3. 결정 로직
    if continentalness < -0.2:
        return None  # 물 아래

    if slope_angle > 50:
        return "rock"  # 급경사 = 바위만

    if z > snow_start_height:
        return "snow_rock"  # 눈선 위 = 눈 덮인 바위

    if temperature < -0.5:
        return "pine_tree" if humidity > 0.3 else "rock"

    if temperature > 0.5 and humidity < 0.3:
        return random.choice([None, None, None, "cactus"])  # 사막

    if humidity > 0.6:
        return random.choice(["oak_tree", "birch_tree", "grass"])  # 숲

    return "grass"  # 기본
```

---

## 🎯 Phase 1: 도로 포함 지형 오브젝트 배치 (우선 구현)

### 1.1 사용자 플로우
```
지형 갤러리 → Road 항목 선택 → "오브젝트 생성" 버튼 클릭
→ Road의 Blend 파일 열기
→ 오브젝트 배치 스크립트 실행
→ Blend 파일 저장
→ 미리보기 이미지 업데이트
```

### 1.2 API 엔드포인트
```typescript
POST /api/road/:roadId/add-objects
{
  objectDensity?: number,  // 0.1 ~ 1.0 (기본값: 0.5)
  objectTypes?: string[]   // ['tree', 'grass', 'rock'] (기본값: 모두)
}

Response:
{
  success: true,
  roadId: string,
  objectCount: number,
  previewPath: string
}
```

### 1.3 데이터베이스 스키마 (필요시 확장)
```prisma
model Road {
  // ... 기존 필드
  hasObjects    Boolean @default(false)  // 오브젝트가 배치되었는지 여부
  objectCount   Int?                     // 배치된 오브젝트 개수
}
```

### 1.4 Blender Python 스크립트 구조
**파일명**: `object_placer.py`

```python
"""
지형 오브젝트 배치 스크립트
Usage:
    blender <road.blend> --background --python object_placer.py -- \
        <biome_maps_dir> <assets_dir> <object_count> <output_blend> <preview_png>
"""

# 주요 기능:
# 1. Road Blend 파일 로드 (지형 + 도로 포함)
# 2. Biome map 이미지 로드 (16개 PNG 파일)
# 3. Assets 폴더 구조 스캔 (tree/general/, tree/tropical/ 등)
# 4. 랜덤 XY 좌표 생성 (object_count 기반, 기본 1000개)
# 5. Raycast로 지형 Z 좌표 + 법선 벡터 찾기
# 6. Biome 픽셀 값 읽어서 카테고리 결정 (general/big/tropical/desert)
# 7. 도로와 겹치지 않는지 체크 (최소 2m 거리)
# 8. 카테고리 폴더에서 랜덤 GLTF 파일 선택
# 9. GLTF Import 후 지형에 배치 (회전 정렬)
# 10. Blend 파일 저장 + 미리보기 렌더링
```

### 1.5 오브젝트 배치 알고리즘
```python
# 1. Assets 폴더 스캔 (한 번만 실행)
tree_assets = scan_tree_assets(assets_dir)
# tree_assets = {
#     'general': ['assets/objects/tree/general/tree1/', 'assets/.../tree2/', ...],
#     'big': ['assets/objects/tree/big/oak/', ...],
#     'tropical': ['assets/objects/tree/tropical/palm/', ...],
#     'desert': ['assets/objects/tree/desert/cactus/', ...]
# }

# 2. 랜덤 XY 좌표 생성 (기본 1000개)
placed_count = 0
for _ in range(object_count):
    x = random.uniform(0, 1000)
    y = random.uniform(0, 1000)

    # 3. Raycast로 지형 정보 찾기
    hit, location, normal, _, _, _ = scene.ray_cast(
        view_layer,
        origin=(x, y, 1000),
        direction=(0, 0, -1)
    )

    if not hit:
        continue  # 지형 없음

    z = location.z
    slope_angle = math.degrees(math.acos(normal.z))

    # 4. 도로 충돌 체크
    if is_too_close_to_road(x, y, road_mesh, min_distance=2.0):
        continue  # 도로 너무 가까움

    # 5. Biome map 픽셀 읽기 (16개 파라미터)
    biome_data = read_biome_pixels(x, y, biome_maps)
    temperature = biome_data['temperature']       # -1~1
    humidity = biome_data['humidity']             # 0~1
    continentalness = biome_data['continentalness']  # -1~1
    erosion = biome_data['erosion']               # 0~1

    # 6. 카테고리 결정 (general/big/tropical/desert)
    category = determine_tree_category(
        temperature, humidity, continentalness, erosion, slope_angle
    )

    if category is None:
        continue  # 배치 안함

    # 7. 해당 카테고리의 랜덤 폴더 선택
    if category not in tree_assets or len(tree_assets[category]) == 0:
        continue

    tree_folder = random.choice(tree_assets[category])

    # 8. 폴더 내부의 GLTF 파일 찾기
    gltf_file = find_gltf_in_folder(tree_folder)
    if gltf_file is None:
        continue

    # 9. GLTF 임포트 및 배치
    import_and_place_gltf(gltf_file, x, y, z, normal)
    placed_count += 1

print(f"✅ Placed {placed_count} trees")
```

### 1.6 카테고리 결정 룰 (실제 Assets 폴더 기반)
```python
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
        return None  # 너무 급경사 (45° 이상)

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
```

**확률 요약:**
- `general`: 70% (가장 흔함)
- `big`: 5% (희귀)
- `tropical`: 100% (조건 만족 시 항상 배치)
- `desert`: 30% (사막에서도 드물게 배치)

### 1.7 도로 충돌 체크
```python
def is_on_road(x, y, road_mesh, min_distance=2.0):
    """
    해당 XY 좌표가 도로와 너무 가까운지 체크
    """
    # Road 메시의 모든 버텍스와의 최소 거리 계산
    # (최적화: KD-Tree 또는 BVH 사용)

    for vert in road_mesh.data.vertices:
        world_pos = road_mesh.matrix_world @ vert.co
        dist_2d = math.sqrt((world_pos.x - x)**2 + (world_pos.y - y)**2)

        if dist_2d < min_distance:
            return True

    return False
```

---

## 🎨 Phase 2: Assets 폴더 구조 및 GLTF 처리

### 2.1 Assets 폴더 구조
```
assets/objects/tree/
├── general/          # 일반 나무 (온대 기후, 70% 확률)
│   ├── tree1/
│   │   └── tree1.gltf
│   ├── tree2/
│   │   └── tree2.gltf
│   └── ...
├── big/              # 큰 나무 (평지 숲, 5% 희귀)
│   ├── oak_big/
│   │   └── oak_big.gltf
│   └── ...
├── tropical/         # 열대 나무 (열대 기후, 100% 확률)
│   ├── palm/
│   │   └── palm.gltf
│   └── ...
└── desert/           # 사막 식물 (사막, 30% 확률)
    ├── cactus1/
    │   └── cactus1.gltf
    └── ...
```

### 2.2 Assets 폴더 스캔 함수
```python
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
    tree_dir = os.path.join(assets_dir, 'objects', 'tree')
    categories = ['general', 'big', 'tropical', 'desert']

    result = {}
    for category in categories:
        category_path = os.path.join(tree_dir, category)
        if not os.path.exists(category_path):
            result[category] = []
            continue

        # 카테고리 폴더 내부의 모든 하위 폴더 수집
        subfolders = [
            os.path.join(category_path, d)
            for d in os.listdir(category_path)
            if os.path.isdir(os.path.join(category_path, d))
        ]
        result[category] = subfolders

    return result
```

### 2.3 GLTF 파일 찾기 및 임포트
```python
def find_gltf_in_folder(folder_path):
    """폴더 내부의 첫 번째 .gltf 또는 .glb 파일 찾기"""
    for filename in os.listdir(folder_path):
        if filename.endswith(('.gltf', '.glb')):
            return os.path.join(folder_path, filename)
    return None

def import_and_place_gltf(gltf_path, x, y, z, normal):
    """
    GLTF 파일 임포트 후 지형에 배치

    Args:
        gltf_path: GLTF 파일 경로
        x, y, z: 월드 좌표
        normal: 법선 벡터 (지형 경사)
    """
    # GLTF 임포트
    bpy.ops.import_scene.gltf(filepath=gltf_path)

    # 방금 임포트된 오브젝트 찾기 (마지막 선택된 오브젝트)
    imported_obj = bpy.context.selected_objects[-1]

    # 위치 설정
    imported_obj.location = (x, y, z)

    # 법선 벡터에 맞춰 회전 (지형 경사에 정렬)
    z_axis = normal
    x_axis = mathutils.Vector((1, 0, 0))
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
```

---

## 🚀 Phase 3: 클라이언트 UI

### 3.1 Road 갤러리에 버튼 추가
```tsx
// RoadCard.tsx
<button onClick={() => handleAddObjects(road.id)}>
  🌲 오브젝트 생성
</button>

const handleAddObjects = async (roadId: string) => {
  setLoading(true);
  const response = await fetch(`/api/road/${roadId}/add-objects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ objectDensity: 0.5 })
  });

  const data = await response.json();
  if (data.success) {
    toast.success(`✅ ${data.objectCount}개 오브젝트 배치 완료`);
    refreshRoadList();
  }
  setLoading(false);
};
```

---

## ⚙️ 구현 순서

1. **Backend API** (`src/server.ts`)
   - `POST /api/road/:roadId/add-objects` 엔드포인트 추가

2. **Blender Service** (`src/services/blenderService.ts`)
   - `placeObjectsOnTerrain()` 함수 추가

3. **Python Script** (`src/blender-scripts/object_placer.py`)
   - 오브젝트 배치 로직 구현

4. **Database** (선택)
   - Road 모델에 `hasObjects`, `objectCount` 필드 추가

5. **Frontend** (클라이언트)
   - Road 갤러리에 "오브젝트 생성" 버튼 추가

---

## 🔧 기술적 고려사항

### 성능
- **예상 오브젝트 개수**: 1000 ~ 5000개 (density 0.5 기준)
- **Raycast 속도**: ~0.1ms per cast → 총 0.5초
- **픽셀 읽기 속도**: ~1μs per read → 총 0.005초 (무시 가능)
- **Blender 렌더링**: 2-5초 (미리보기)
- **총 예상 시간**: **5-10초**

### 메모리
- Biome maps: 1024x1024 x 13 images x 4 bytes = ~50MB
- 오브젝트 메시: 5000개 x ~1KB = ~5MB
- 총: **~55MB** (문제없음)

### 파일 크기
- `.blend` 파일: 5000개 primitive → ~10MB 증가 예상
- `.glb` 파일: 오브젝트 포함 시 ~20MB (허용 범위)

---

## 📝 추후 개선 아이디어

1. **가로수 배치**: 도로 양쪽에 일정 간격으로 나무 배치
2. **가드레일**: 도로 가장자리에 Curve 기반 메시 생성
3. **신호등**: 교차로 감지 후 자동 배치
4. **LOD (Level of Detail)**: 거리 기반 오브젝트 단순화
5. **Instancing**: GPU Instancing으로 성능 최적화
6. **Collision Mesh**: 게임 엔진용 충돌 메시 생성

---

## ✅ Phase 1 완료 조건

- [ ] `POST /api/road/:roadId/add-objects` API 동작
- [ ] `object_placer.py` 스크립트 완성
- [ ] 바이옴 기반 오브젝트 배치 룰 동작
- [ ] 도로와 충돌 방지 동작
- [ ] 프론트엔드 버튼 및 UI 완성
- [ ] 미리보기 이미지 업데이트 확인
