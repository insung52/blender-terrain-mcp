# 🏔️ Blender Terrain Generator

## Update 251019, Biome and Water

![Main update 251019](assets/md/1019.png)

### 🎨 Biome-based Terrain System

**자연어 → AI 바이옴 레이아웃 → 현실적인 지형 생성**

이제 Claude AI가 사용자 설명을 분석하여 **여러 바이옴(지형 타입)을 자동 배치**하고, Weighted Voronoi Diagram + Gaussian Blur로 **자연스럽게 블렌딩**된 지형을 생성합니다.

**입력 예시:**
```
"위쪽은 높은 산, 왼쪽아래에는 초록색 평지, 오른쪽 아래에는 사막, 중앙에는 작은 호수"
```

**AI가 자동 생성:**
- 🏔️ **Snowy Mountain** (위쪽): continentalness=0.6, erosion=0.8, coverage=0.12
- 🌾 **Plains** (왼쪽 아래): continentalness=0.3, erosion=0.2, coverage=0.3
- 🏜️ **Desert** (오른쪽 아래): continentalness=0.5, erosion=0.3, coverage=0.3
- 💧 **Lake** (중앙): continentalness=-0.2, erosion=0.0, coverage=0.15

**기술 스택:**
- **16개 바이옴 파라미터**: temperature, humidity, erosion, continentalness, weirdness + 3색상×3타입
- **WVD 알고리즘**: Coverage 기반 영역 할당 + 매 실행마다 랜덤 경계선
- **16bit PNG 맵**: 8bit (0~255) 사용 시 높이 500m 지형에서 2m마다 계단식 층 발생 → 16bit (0~65535)로 0.76cm 정밀도 확보
- **Multi-Octave Noise**: 6단계 디테일 (대륙 → 바위 표면)
- **Erosion Squaring**: 비선형 산-평지 경계
- **Slope-based Rock**: 경사진 곳에 바위 노출

실제 생성된 Biome Map 이미지
![Main update 251019](assets/md/biome_erosion_unblur.png)

Gaussian Blur 적용, 지형들의 파라미터를 블렌딩 하는 효과. 실제 지형 생성시 자연스럽게 지형들이 이어짐
![Main update 251019](assets/md/biome_erosion_blur.png)

총 16개의 Biome Map 이미지들이 사용됨
![alt text](assets/md/maps.png)


**지형 생성 상세 프로세스:**

1. **Multi-Octave Noise System (6단계)**
   ```
   Octave 1: Large-scale (200m 주기) × 2.0    - 대륙 형태
   Octave 2: Medium (50m 주기) × 0.8         - 산맥 굴곡
   Octave 3: Small (10m 주기) × 0.05         - 언덕
   Octave 4: Micro (1m 주기) × 0.005         - 바위 굴곡
   Octave 5: Fine (0.33m 주기) × 0.005       - 바위 표면
   Octave 6: Ultra-fine (0.02m 주기) × 0.05  - 미세 텍스처
   ```
   - 총 가중치 1.7 → 중심값 0.85 제거 (평지에서 불필요한 높이 추가 방지)

2. **Erosion 기반 높이 변동**
   - `erosion²` 적용 → 비선형 산-평지 경계
   - 평지 (erosion=0.1): 0.01² × 1000m = **10m 변동**
   - 산 (erosion=0.9): 0.81² × 1000m = **656m 변동**

3. **경사도 기반 바위 노출**
   - Normal.Z로 경사도 계산: `slope = 1.0 - normal.Z`
   - `rock_exposure` 파라미터로 임계값 조정
   - 경사진 곳 (slope > threshold): 눈 위에 바위 드러남
   - Material 순서: Ground → Snow (높이) → Rock (경사도)

4. **눈 경계 랜덤화**
   - `snow_start_height` ± 30m Noise Texture
   - 자연스러운 눈선 경계 (계단식 X)

5. **계곡 침식**
   - `valley_depth = (1 - continentalness) / 2 × humidity × 100m`
   - 습한 저지대에 자연스러운 계곡 생성 

---

### 💧 Realistic Water System

**투명한 물 메시 + Fresnel 반사 + 깊이별 색상 변화**

수면(z=0) 보다 낮은 지점들, 예를 들어 호수/바다가 이제 **별도의 투명 물 메시**로 렌더링되며, 깊이에 따라 자연스럽게 색이 진해집니다.

**구현:**
- **1000m × 1000m × 400m 직육면체** 물 메시 (수면 Z=0)
- **Principled BSDF**: IOR=1.333 (물의 굴절률), Transmission=0.95
- **Fresnel 반사**: 수직 → 투명, 비스듬 → 반사 (각도 기반)
- **Volume Absorption**: 깊이 10m → 밝은 파랑, 400m → 진한 파랑
- **Screen Space Reflections**: 물 표면에 지형 반사

**효과:**
- ✅ 얕은 호수: 바닥 흙색 보임 + 물 색 약간
- ✅ 깊은 바다: 진한 어두운 파란색
- ✅ 수면 반사: 주변 지형이 물에 비침
- ✅ 물과 땅 자연스러운 경계

---

### 📊 Technical Details

**파일 구조:**
```
src/
├── types/biome.ts              # 16개 바이옴 파라미터 정의
├── services/biomeService.ts    # Claude AI 프롬프트
└── blender-scripts/
    ├── biome_generator_wvd.py     # WVD + Gaussian Blur
    └── biome_terrain_blender.py   # 지형 + 물 메시 생성
```

**주요 알고리즘:**
1. **Weighted Voronoi Diagram**: Coverage 값으로 영향 범위 조정
2. **Gaussian Blur (σ=100)**: 경계 블렌딩 (`mode='nearest'`로 외삽 방지)
3. **Noise Centering**: 평균 0.85 제거 → 평지에서 불필요한 높이 추가 방지
4. **Continentalness → Height**: `continentalness × 1000m` (0 = 해수면)
5. **Valley Erosion**: `depth = (1 - continentalness) / 2 × humidity × 100m`

**성능:**
- **Vertices**: 2,560,000 (200×200 grid → Subdivision Level 3)
- **Biome Maps**: 1000×1000 × 16개 PNG (16bit)
- **Render Time**: ~5초 (EEVEE_NEXT)

---


## AI 기반 자동 지형 생성 및 도로 배치 시스템

**Blender + Claude AI + Node.js**를 활용하여 자연어 설명만으로 3D 지형을 생성하고, 그림판처럼 간편하게 도로를 그려 배치할 수 있는 웹 서비스입니다.

![Main Demo](assets/md/readme1.png)

![Main Demo](assets/md/readme2.png)

![Main Demo](assets/md/r1.png)
<!-- 스크린샷: 웹 UI 메인 화면 - Terrain Gallery + Road Gallery 전체 모습 -->

---

## ✨ 주요 기능

웹 기반 서비스

localhost:3000 접속 또는 실제 웹 서비스 배포 가능

![Main Demo](assets/md/r6.png)

### 1. 🤖 AI 기반 지형 생성
Claude AI가 한글 설명을 분석하여 자동으로 지형 파라미터를 생성합니다.

**입력 예시:**
- "눈 덮인 높은 산맥" → 높은 봉우리 + 흰색 눈 + 험준한 지형
- "평평한 초원 지대" → 낮은 기복 + 녹색 풀 + 부드러운 경사
- "화산 지형" → 날카로운 봉우리 + 검은 암석 + 붉은 색조

**15+ 파라미터 자동 추출:**
- 높이, 거칠기, 노이즈 타입, 침식도
- 눈/바위/풀 색상 및 높이 임계값
- 기후, 습도, 식생 밀도 등

### 2. 🎨 그림판 스타일 도로 배치
Terrain preview 이미지 위에 마우스로 직접 도로를 그리면, Ramer-Douglas-Peucker 알고리즘이 자동으로 경로를 최적화합니다.

**특징:**
- 🖱️ 마우스 드래그로 자유롭게 도로 그리기
- 🔴 실시간 경로 프리뷰 (빨간 선)
- 🟢 자동 Control Points 추출 (녹색 점)
- 📐 수백 개 점 → 20개 이하로 자동 단순화



![Main Demo](assets/md/r2.png)

- 생성된 도로 preview

![Main Demo](assets/md/r3.png)

- 생성된 blend 파일 다운로드 가능

### 3. 🛣️ 자동 UV Texturing
차선 텍스처가 도로 방향에 맞춰 자동으로 정렬됩니다.

**기술:**
- 평면 Bevel Profile (원통형 ✗ → 평면 ✓)
- 동적 스케일링 (도로 길이 기반 버텍스 개수 조절)
- 10 segments로 정확한 UV 구조

![Main Demo](assets/md/r4.png)

### 4. 📸 갤러리 기반 UI
생성한 지형과 도로를 한눈에 확인하고 관리할 수 있습니다.

**Terrain Gallery:**
- 카드 형태로 preview 이미지 표시
- 생성 날짜, 설명, metadata 확인
- 🛣️ Add Road / 🗑️ Delete 버튼

**Road Gallery:**
- Terrain + Road 결과물 표시
- Control points 개수 표시
- 클릭 시 Job Details 팝업

![Main Demo](assets/md/r5.png)
<!-- 스크린샷: Terrain Gallery + Road Gallery 함께 보이는 화면 -->

---

## 🚀 Quick Start (로컬 서버 실행)

### 필수 요구사항
- **Node.js** v18+ (v20 권장)
- **MySQL** 8.0+
- **Redis** 6.0+
- **Blender** 4.5+
- **Claude API Key** (Anthropic)
- **Docker Desktop** (선택)

### 1. 설치

```bash
# 프로젝트 클론
git clone https://github.com/insung52/blender-terrain-mcp.git
cd blender-terrain-mcp

# 패키지 설치
npm install

# 클라이언트 패키지 설치 및 빌드
cd client && npm install && npx vite build && cd ..
```

### 2. 환경 설정

- Windows PowerShell 에서
```bash
@"
DATABASE_URL="mysql://root:password@localhost:3306/blender_terrain"
REDIS_HOST="localhost"
REDIS_PORT=6379
ANTHROPIC_API_KEY="your-api-key-here"
BLENDER_PATH="C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe"
"@ | Out-File -Encoding UTF8 .env
```

- 또는 리눅스 환경에서
```bash
# .env 파일 생성
cat > .env << EOF
DATABASE_URL="mysql://root:password@localhost:3306/blender_terrain"
REDIS_HOST="localhost"
REDIS_PORT=6379
ANTHROPIC_API_KEY="your-api-key-here"
BLENDER_PATH="C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe"
EOF
```

이후 mysql 비밀번호를 **password** 에 입력,
Claude API Key 를 **'your-api-key-here'** 에 입력


### 3. 데이터베이스 설정

```bash
# MySQL 데이터베이스 생성
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS blender_terrain;"

# Prisma 마이그레이션
npx prisma migrate dev
```

### 4. Redis 실행 (Docker 사용 추천!)

```bash
# Docker 사용
docker run -d -p 6379:6379 redis

# 또는 로컬 설치
redis-server
```

### 5. 실행

```bash
# 서버 실행 (Backend + Frontend 통합)
npm run dev
# → http://localhost:3000
```

**프로덕션 모드**: Frontend가 빌드되어 포트 3000에서 함께 제공됩니다.

**개발 모드** (Frontend 수정 시):
```bash
# 터미널 1: Backend
npm run dev

# 터미널 2: Frontend (Hot Reload)
cd client && npm run dev
# → http://localhost:5173
```

---

## 🌐 외부 배포 (연구실/서버)

프로덕션 환경에서 외부 접속을 허용하려면:

### 1. 포트포워딩 설정
- **포트:** 3000
- **프로토콜:** TCP
- **규칙 종류:** HTTP (또는 사용자 정의)

### 2. 서버 실행
```bash
npm run dev
```

### 3. 외부 접속
```
http://서버IP:3000
http://공인IP:3000
```

**주의사항:**
- MySQL, Redis는 로컬호스트에서만 접근 (외부 노출 불필요)
- 방화벽에서 포트 3000 허용 필요
- HTTPS가 필요한 경우 nginx 리버스 프록시 사용 권장

---

## 📖 사용 방법

### Step 1: Terrain 생성

1. **"1. Create Terrain"** 섹션으로 이동
2. 한글로 지형 설명 입력 (예: "눈 덮인 높은 산맥")
3. **"Use Claude AI"** 체크박스 선택 (권장)
4. **"Create Terrain"** 버튼 클릭
5. Job이 큐에 추가되고 백그라운드에서 처리됨


### Step 2: Terrain 확인

1. **"2. Terrain Gallery"** 섹션에서 생성된 지형 확인
2. 카드 이미지 클릭 → **Job Details** 팝업 표시
3. Status, Preview 이미지, .blend 파일 다운로드 링크 확인

### Step 3: Road 그리기

1. Terrain 카드에서 **"🛣️ Add Road"** 버튼 클릭
2. Road Modal이 팝업으로 표시됨
3. **"🎨 Draw Mode"** 탭 선택 (기본)
4. Canvas 위에 마우스로 도로 경로 그리기
   - 드래그: 경로 그리기 (빨간 선)
   - 떼기: 자동으로 Control Points 추출 (녹색 점)
5. **"Clear Drawing"** 버튼으로 다시 그리기 가능
6. **"🛣️ Create Road"** 버튼 클릭

**Alternative: Manual Input**
- **"⌨️ Manual Input"** 탭 선택
- JSON 형식으로 직접 입력: `[[10,10],[50,30],[90,80]]`

### Step 4: Road 결과 확인

1. **"3. Road Gallery"** 섹션에서 생성된 도로 확인
2. Preview 이미지에서 지형 위 도로 확인
3. .blend 파일 다운로드하여 Blender에서 열기

### Step 5: Blender에서 확인

다운로드한 `.blend` 파일을 Blender에서 열어 3D 뷰로 확인:
- 지형 높낮이에 맞춰 도로가 배치됨
- 차선 텍스처가 정확히 정렬됨
- 10 segments로 세밀한 메시 구조

---

## 🎯 API 사용 예시

### Terrain 생성

```bash
curl -X POST http://localhost:3000/api/terrain \
  -H "Content-Type: application/json" \
  -d '{
    "description": "눈 덮인 높은 산맥",
    "useAI": true
  }'

# Response:
# {
#   "success": true,
#   "jobId": "123e4567-e89b-12d3-a456-426614174000",
#   "status": "queued"
# }
```

### Road 생성

```bash
curl -X POST http://localhost:3000/api/road \
  -H "Content-Type: application/json" \
  -d '{
    "terrainId": "123e4567-e89b-12d3-a456-426614174000",
    "controlPoints": [[10,10],[50,30],[90,80]]
  }'

# Response:
# {
#   "success": true,
#   "jobId": "234e5678-f90c-23e4-b567-537725285111",
#   "status": "queued"
# }
```

### Job 상태 확인

```bash
curl http://localhost:3000/api/job/123e4567-e89b-12d3-a456-426614174000

# Response:
# {
#   "success": true,
#   "job": {
#     "id": "123e4567-e89b-12d3-a456-426614174000",
#     "type": "terrain",
#     "status": "completed",
#     "terrain": {
#       "id": "terrain-id",
#       "description": "눈 덮인 높은 산맥",
#       "blendFilePath": "output/terrain-id.blend",
#       "topViewPath": "output/terrain-id_preview.png"
#     }
#   }
# }
```

---

## 🏗️ 프로젝트 구조

```
blender-terrain-mcp/
├── src/
│   ├── server.ts                    # Express 서버 + API
│   ├── config.ts                    # 설정 파일
│   ├── db/
│   │   └── client.ts                # Prisma 클라이언트
│   ├── services/
│   │   ├── blenderService.ts        # Blender 실행 로직
│   │   └── claudeService.ts         # Claude API 연동
│   ├── queue/
│   │   └── blenderQueue.ts          # Bull Queue (작업 관리)
│   └── blender-scripts/
│       ├── terrain_generator_v2.py  # 지형 생성 (15+ 파라미터)
│       └── road_generator.py        # 도로 생성 + UV Texturing
├── client/                          # React 프론트엔드
│   ├── src/
│   │   ├── App.tsx                  # 메인 UI
│   │   └── utils/
│   │       └── simplifyPath.ts      # RDP 알고리즘
│   └── public/
├── prisma/
│   └── schema.prisma                # DB 스키마
├── output/                          # 생성된 .blend 파일 및 이미지
├── assets/                          # 텍스처, 스크린샷 등
└── README.md
```

---

## 🔧 기술 스택

### Backend
- **Node.js** + **TypeScript**
- **Express** - REST API
- **Prisma** - ORM (MySQL)
- **Bull** - Job Queue (Redis)
- **Anthropic SDK** - Claude API

### Frontend
- **React** + **TypeScript**
- **Vite** - Build tool
- **HTML Canvas** - 도로 그리기

### 3D Graphics
- **Blender 4.5** - Procedural terrain + Road mesh
- **Blender Python API** - 자동화 스크립트
- **Geometry Nodes** - 머티리얼 시스템

### Algorithms
- **Ramer-Douglas-Peucker** - 경로 단순화
- **Height-based Material System** - 높이에 따른 색상 자동 적용
- **UV Dynamic Scaling** - 도로 길이 기반 텍스처 스케일

---

## 📊 시스템 아키텍처

```
┌─────────────┐
│   Browser   │
│  (React UI) │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────┐
│  Express Server │
│   (Node.js)     │
└────┬───────┬────┘
     │       │
     │       └────────┐
     ▼                ▼
┌─────────┐    ┌──────────────┐
│  MySQL  │    │ Claude API   │
│ (Prisma)│    │ (AI Analysis)│
└─────────┘    └──────────────┘
     │
     ▼
┌──────────────┐
│  Bull Queue  │
│   (Redis)    │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ Blender (Python) │
│  - Terrain Gen   │
│  - Road Gen      │
│  - UV Mapping    │
└──────────────────┘
       │
       ▼
┌──────────────┐
│ .blend Files │
│ PNG Previews │
└──────────────┘
```

---

## 🎓 주요 알고리즘

### 1. Ramer-Douglas-Peucker (RDP)

경로 단순화 알고리즘으로, 사용자가 그린 수백 개의 점을 20개 이하의 핵심 Control Points로 축소합니다.

```typescript
function simplifyPath(points: Point[], epsilon: number): Point[] {
  // 시작-끝 선분에서 가장 먼 점 찾기
  let maxDistance = 0;
  let maxIndex = 0;

  for (let i = 1; i < points.length - 1; i++) {
    const distance = perpendicularDistance(points[i], start, end);
    if (distance > maxDistance) {
      maxDistance = distance;
      maxIndex = i;
    }
  }

  // 재귀적으로 단순화
  if (maxDistance > epsilon) {
    const left = simplifyPath(points.slice(0, maxIndex + 1), epsilon);
    const right = simplifyPath(points.slice(maxIndex), epsilon);
    return [...left.slice(0, -1), ...right];
  } else {
    return [start, end];
  }
}
```

### 2. UV Dynamic Scaling

도로 길이에 비례하여 텍스처 반복 횟수를 자동 조정합니다.

```python
# 도로 총 길이 계산
total_length = sum([
    (points[i+1] - points[i]).length
    for i in range(len(points)-1)
])

# 동적 스케일 계산 (10m당 1회 반복)
y_scale_factor = total_length / 10.0

# UV 좌표 변환
uv.x = -v  # 90도 회전
uv.y = u * y_scale_factor  # 동적 스케일
```

---

## 🐛 트러블슈팅

### 1. Blender가 실행되지 않음
```bash
# Blender 경로 확인
blender --version

# .env 파일에 올바른 경로 설정
BLENDER_PATH="C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe"
```

### 2. Redis 연결 오류
```bash
# Redis 실행 확인
redis-cli ping
# → PONG 응답 확인

# Docker로 실행
docker run -d -p 6379:6379 redis
```

### 3. Claude API 키 오류
```bash
# .env 파일에 올바른 API 키 설정
ANTHROPIC_API_KEY="sk-ant-api03-..."

# API 키 테스트
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

### 4. Job이 처리되지 않음
```bash
# Queue 상태 확인
npm run dev
# → [Worker] Worker started, processing jobs...

# Redis에서 Queue 확인
redis-cli
> KEYS bull:blender-jobs:*
```

---

## 📝 라이선스

MIT License

---

## 📧 문의

프로젝트 관련 문의사항이 있으시면 이슈를 등록해주세요.

---

## 활용한 서비스

- **Blender Foundation** - 오픈소스 3D 소프트웨어
- **Anthropic** - Claude AI API
- **Bull** - Redis 기반 Job Queue
- **Prisma** - 차세대 Node.js ORM

---

![Final Result](assets/md/readme1.png)
<!-- 원본 이미지 유지 -->

![Final Result 2](assets/md/readme2.png)
<!-- 원본 이미지 유지 -->
