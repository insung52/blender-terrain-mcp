# Blender Terrain + Road Generation Service - 설계 문서

## 1. 프로젝트 개요

웹에서 terrain 설명 또는 이미지를 입력받아 workstation에서 Blender를 이용해 3D terrain과 road를 생성하는 서비스

### 핵심 기능
1. **Terrain 생성**: 텍스트/이미지 입력 → AI 기반 지형 생성
2. **Road 생성**: 사용자가 그린 선 → 지형에 맞는 도로 생성
3. **멀티 유저 지원**: Job Queue 기반 동시 처리

---

## 2. 시스템 아키텍처

```
┌─────────────────┐
│  웹 클라이언트   │
│  (Frontend)     │
└────────┬────────┘
         │ HTTP/WebSocket
         │
┌────────▼─────────────────────────┐
│   Node.js Express 서버           │
│   - API 엔드포인트               │
│   - Job Queue 관리 (Bull)        │
│   - Claude API 통합              │
└────────┬─────────────────────────┘
         │
    ┌────┴─────┐
    │          │
┌───▼────┐  ┌─▼─────────────────┐
│ Claude │  │ Blender Executor  │
│  API   │  │ (Job Worker)      │
└────────┘  └───┬───────────────┘
                │
         ┌──────┴──────┐
         │   Blender   │
         │ (Headless)  │
         └─────────────┘
```

---

## 3. Terrain 생성 방식 (Advanced v2.0)

### 선택한 방법: AI + Geometry Nodes Procedural

#### Step 1: AI 분석 (Claude API 또는 Image Analysis)
```javascript
입력: 텍스트 ("눈 덮인 높은 산") 또는 이미지
  ↓
Claude API: 고급 파라미터 추출
{
  // 기본 형상 파라미터
  "base_scale": 35,           // 5-50, 전체 지형 크기
  "base_roughness": 0.85,     // 0-1, 기본 거칠기
  "height_multiplier": 40,    // 5-100, 최대 높이 (미터)

  // 노이즈 설정
  "noise_type": "musgrave",   // "perlin" | "voronoi" | "musgrave"
  "noise_layers": 3,          // 1-5, 디테일 레이어 수
  "octaves": 6,               // 1-10, 노이즈 복잡도

  // 지형 특성
  "peak_sharpness": 0.8,      // 0-1, 봉우리 날카로움
  "valley_depth": 0.6,        // 0-1, 계곡 깊이
  "erosion": 0.4,             // 0-1, 침식/풍화 효과
  "terrace_levels": 0,        // 0-10, 계단식 지형 (0=없음)

  // 머티리얼 설정 (높이 기반)
  "snow_height": 0.7,         // 0-1, 눈 시작 높이
  "rock_height": 0.3,         // 0-1, 바위 시작 높이
  "grass_height": 0.0,        // 0-1, 풀 시작 높이

  // 색상 설정
  "snow_color": [0.95, 0.95, 1.0],    // RGB
  "rock_color": [0.3, 0.3, 0.35],     // RGB
  "grass_color": [0.2, 0.4, 0.1],     // RGB

  // 환경/분위기
  "climate": "arctic",        // "arctic" | "temperate" | "desert" | "volcanic" | "alien"
  "wetness": 0.2,            // 0-1, 습도 (표면 반사)
  "vegetation_density": 0.1,  // 0-1, 식물 밀도 (미래 확장)

  // 메타데이터
  "description": "눈 덮인 험준한 고산 지형"
}
```

#### Step 2: Geometry Nodes로 지형 생성 (Procedural)
```python
# Blender Geometry Nodes 구조

1. Input Plane (100m x 100m, 고해상도 subdivision)
   ↓
2. Base Noise Layer (noise_type 적용)
   - Musgrave/Perlin/Voronoi
   - Scale: base_scale
   - Octaves: octaves
   ↓
3. Detail Layers (noise_layers만큼 반복)
   - 작은 scale noise 추가 (디테일)
   - 각 레이어마다 강도 감소
   ↓
4. Height Sculpting
   - Peak Sharpness: Math node (power)
   - Valley Depth: Multiply + Clamp
   - Erosion: Blur + Noise distortion
   ↓
5. Optional: Terrace Effect
   - Snap to grid (계단식 지형)
   ↓
6. Set Position (최종 높이 적용)
   - Z축 displacement: height_multiplier
   ↓
7. Material Assignment (높이 기반)
   - Vertex Color 또는 Material Index
   - Snow: z > snow_height
   - Rock: rock_height < z < snow_height
   - Grass: z < rock_height
```

#### Step 3: Material System (Shader Nodes)
```python
# Material Node 구조

Geometry Input
  ↓ Position Z
ColorRamp (높이 기반 재질 분리)
  - Stop 1 (0.0-grass_height): Grass Color
  - Stop 2 (grass_height-rock_height): Rock Color
  - Stop 3 (rock_height-snow_height): Rock → Snow Blend
  - Stop 4 (snow_height-1.0): Snow Color
  ↓
Principled BSDF
  - Base Color: ColorRamp 결과
  - Roughness: 재질별 다름 (눈=0.3, 바위=0.9, 풀=0.6)
  - Specular: wetness 값 적용
  ↓
Add Noise Texture (표면 디테일)
  - Bump mapping
  - 재질별 다른 scale
```

#### Step 4: 렌더링 및 저장
```python
1. Top view camera 설정
2. Sun light + 환경 조명
3. EEVEE_NEXT 렌더링
4. Preview PNG 저장 (1024x1024)
5. .blend 파일 저장
```

---

### 기술적 구현 방식 비교

| 방식 | 현재 (v1.0) | 업그레이드 (v2.0) |
|------|------------|------------------|
| **지형 생성** | Displacement Modifier | Geometry Nodes |
| **노이즈** | 1개 (Clouds) | 다중 레이어 (3-5개) |
| **파라미터 수** | 2개 (scale, roughness) | 15+ 개 |
| **머티리얼** | 없음 (흰색) | 높이 기반 3-4 재질 |
| **특수 효과** | 없음 | Erosion, Terracing, Sharpness |
| **이미지 입력** | 불가능 | 가능 (heightmap → params) |
| **처리 속도** | ~3초 | ~5-8초 |
| **파일 크기** | 800KB | 1-2MB |

---

### 새로운 파라미터 설명

#### 지형 형상 파라미터
- **base_scale** (5-50): 지형의 전체적인 기복 크기. 큰 산=40+, 언덕=15-25, 평지=5-10
- **height_multiplier** (5-100): 최고점 높이 (미터). 히말라야=80-100, 일반 산=30-50
- **noise_type**:
  - `perlin`: 부드러운 언덕
  - `voronoi`: 각진 바위산, 화산
  - `musgrave`: 복잡한 산악 지형 (추천)
- **noise_layers** (1-5): 디테일 수준. 많을수록 복잡함
- **octaves** (1-10): 노이즈 반복 횟수. 높을수록 디테일 증가

#### 지형 특성 파라미터
- **peak_sharpness** (0-1):
  - 0.0-0.3: 완만한 정상
  - 0.4-0.7: 일반 산
  - 0.8-1.0: 날카로운 봉우리 (에베레스트)
- **valley_depth** (0-1):
  - 0.0-0.3: 얕은 골짜기
  - 0.4-0.7: 일반 계곡
  - 0.8-1.0: 깊은 협곡
- **erosion** (0-1): 물/바람 침식 효과. 오래된 산=0.7+, 젊은 산=0.2-
- **terrace_levels** (0-10): 계단식 지형 (논, 단층 지형)

#### 머티리얼 파라미터
- **snow_height** (0-1): 이 높이 이상 눈. 0.7 = 상위 30%만 눈
- **rock_height** (0-1): 이 높이 이상 바위 노출
- **grass_height** (0-1): 이 높이 이하 풀/흙
- **wetness** (0-1): 표면 반사도. 비 온 후=0.8, 건조=0.2
- **climate**: 전체 색상 톤 조정
  - `arctic`: 차가운 파란 톤, 많은 눈
  - `temperate`: 균형잡힌 초록/갈색
  - `desert`: 따뜻한 노란/갈색, 눈 없음
  - `volcanic`: 검은 바위, 붉은 톤
  - `alien`: 비현실적 색상

---

### 이미지 입력 처리 (미래 확장)

```javascript
// 사용자가 이미지 업로드
입력: terrain_reference.jpg
  ↓
1. Image Analysis (Claude Vision API)
   - 지형 타입 인식 ("snow-capped mountains")
   - 색상 분석 (주요 색상 추출)
   - 형태 분석 (날카로움, 거칠기)
   ↓
2. Heightmap 추출 (OpenCV)
   - Grayscale 변환
   - Edge detection
   - Depth estimation (AI 모델)
   ↓
3. 파라미터 자동 생성
   {
     base_scale: 이미지 분석 결과,
     peak_sharpness: edge sharpness,
     snow_height: 흰색 픽셀 분포,
     colors: 주요 색상 3개,
     ...
   }
   ↓
4. Geometry Nodes로 생성 (Step 2와 동일)
```

---

## 4. Road 생성 방식

### Step 1: 사용자 입력
```
웹 화면: Terrain top view 이미지 표시
사용자: 마우스 드래그로 선 그리기
출력: Control points 배열
  [{x: 10, y: 20}, {x: 30, y: 45}, {x: 50, y: 80}, ...]
```

### Step 2: Blender 처리
```python
# Blender Python
1. Bezier Curve 생성 (control points 기반)
2. Spline fitting (smooth curve)
3. Curve → Mesh 변환
   - Width: 1.6m (1차선)
   - Extrude along curve
4. Shrinkwrap Modifier
   - Target: Terrain mesh
   - 지형 표면에 맞춤
5. Boolean/Displacement
   - Terrain에 indent (도로 자국)
6. Material 적용
   - Asphalt texture
   - Lane markings
```

---

## 5. 멀티 유저 처리 (Job Queue)

### Bull Queue 구조
```typescript
interface BlenderJob {
  userId: string;
  jobId: string;
  type: 'terrain' | 'road';
  params: {
    // terrain
    description?: string;
    image?: string;
    // road
    terrainId?: string;
    controlPoints?: {x: number, y: number}[];
  };
  outputPath: string;
}
```

### 동시 처리 설정
```typescript
const MAX_CONCURRENT_JOBS = 4; // 서버 사양에 따라 조정

blenderQueue.process(MAX_CONCURRENT_JOBS, async (job) => {
  // Blender headless 실행
  const result = await execBlender(job.data);
  return result;
});
```

### 리소스 예상치
```
Blender 1개 프로세스:
- RAM: 500MB ~ 2GB
- CPU: 1-2 cores
- 처리 시간: 5-30초

16GB RAM, 8 cores 서버:
→ 동시 4개 프로세스 안전
```

---

## 6. API 엔드포인트 설계

### 6.1 Terrain 생성
```
POST /api/terrain
Request:
{
  "description": "산악지형, 눈 덮인",
  "image": "base64..." (optional),
  "userId": "user_abc"
}

Response:
{
  "jobId": "job_123",
  "status": "queued",
  "estimatedTime": 15
}
```

### 6.2 Job 상태 확인
```
GET /api/job/:jobId

Response:
{
  "jobId": "job_123",
  "status": "completed", // queued | processing | completed | failed
  "progress": 100,
  "result": {
    "terrainId": "terrain_abc",
    "topViewUrl": "/output/terrain_abc_top.png",
    "blendFileUrl": "/output/terrain_abc.blend"
  }
}
```

### 6.3 Road 생성
```
POST /api/road
Request:
{
  "terrainId": "terrain_abc",
  "controlPoints": [
    {x: 10, y: 20},
    {x: 30, y: 45},
    {x: 50, y: 80}
  ],
  "userId": "user_abc"
}

Response:
{
  "jobId": "job_456",
  "status": "queued"
}
```

---

## 7. 데이터베이스 스키마

### 7.1 Users 테이블
```sql
CREATE TABLE users (
  id VARCHAR(255) PRIMARY KEY,
  email VARCHAR(255),
  api_key_encrypted TEXT,  -- 사용자 Claude API Key (암호화)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 7.2 Jobs 테이블
```sql
CREATE TABLE jobs (
  id VARCHAR(255) PRIMARY KEY,
  user_id VARCHAR(255) REFERENCES users(id),
  type VARCHAR(50) NOT NULL,  -- 'terrain' | 'road'
  status VARCHAR(50) NOT NULL,  -- 'queued' | 'processing' | 'completed' | 'failed'
  progress INT DEFAULT 0,

  -- Input 파라미터
  input_params JSONB NOT NULL,
  -- 예: {"description": "산악지형", "image": "..."}
  -- 또는: {"terrainId": "xxx", "controlPoints": [...]}

  -- Output 결과
  result JSONB,
  -- 예: {"blendFile": "...", "preview": "...", "terrainId": "..."}

  error_message TEXT,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);

CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
```

### 7.3 Terrains 테이블
```sql
CREATE TABLE terrains (
  id VARCHAR(255) PRIMARY KEY,
  job_id VARCHAR(255) REFERENCES jobs(id),
  user_id VARCHAR(255) REFERENCES users(id),

  -- 생성 정보
  description TEXT,
  input_image_url TEXT,

  -- 파일 경로
  blend_file_path TEXT NOT NULL,
  top_view_path TEXT NOT NULL,

  -- 메타데이터
  size_meters FLOAT DEFAULT 100,  -- 100m x 100m
  metadata JSONB,
  -- 예: {"roughness": 0.7, "scale": 15, "features": ["peaks", "valleys"]}

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_terrains_user_id ON terrains(user_id);
```

### 7.4 Roads 테이블
```sql
CREATE TABLE roads (
  id VARCHAR(255) PRIMARY KEY,
  job_id VARCHAR(255) REFERENCES jobs(id),
  terrain_id VARCHAR(255) REFERENCES terrains(id),
  user_id VARCHAR(255) REFERENCES users(id),

  -- 입력 데이터
  control_points JSONB NOT NULL,
  -- 예: [{"x": 10, "y": 20}, {"x": 30, "y": 45}]

  -- 파일 경로
  blend_file_path TEXT NOT NULL,
  preview_path TEXT,

  -- 메타데이터
  width_meters FLOAT DEFAULT 1.6,  -- 1차선
  metadata JSONB,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roads_terrain_id ON roads(terrain_id);
CREATE INDEX idx_roads_user_id ON roads(user_id);
```

### 7.5 사용 통계 (선택사항)
```sql
CREATE TABLE usage_stats (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(255) REFERENCES users(id),
  date DATE NOT NULL,

  terrain_count INT DEFAULT 0,
  road_count INT DEFAULT 0,
  total_processing_time_seconds INT DEFAULT 0,

  UNIQUE(user_id, date)
);
```

---

## 8. 전체 워크플로우 (DB 포함)

### Terrain 생성 플로우
```
1. 사용자: 웹에서 "산악지형" 입력
   ↓
2. 서버: POST /api/terrain 받음
   ↓
3. DB: Job 레코드 생성 (status: queued)
   INSERT INTO jobs (id, user_id, type, status, input_params)
   ↓
4. Queue: Bull Queue에 job 추가
   ↓
5. Worker: Job 처리 시작
   - DB 업데이트: status = 'processing'
   - Claude API: 지형 특성 분석
   - Blender 스크립트 생성
   - blender --background --python terrain_xxx.py
   ↓
6. Blender:
   - Terrain 생성
   - Top view 렌더링
   - 파일 저장 (output/terrain_xxx.blend)
   ↓
7. Worker: Job 완료
   - DB: Terrain 레코드 생성
     INSERT INTO terrains (id, blend_file_path, top_view_path, ...)
   - DB: Job 업데이트
     UPDATE jobs SET status='completed', result={...}, completed_at=NOW()
   ↓
8. 웹: WebSocket으로 완료 알림
   - Top view 이미지 표시
```

### Road 생성 플로우
```
1. 사용자: Top view 이미지 위에 선 그리기
   ↓
2. 서버: POST /api/road (terrainId + control points)
   ↓
3. DB: Terrain 존재 확인 (SELECT FROM terrains WHERE id=?)
   ↓
4. DB: Job 레코드 생성 (status: queued)
   INSERT INTO jobs (type='road', input_params={terrainId, controlPoints})
   ↓
5. Queue: Bull Queue에 job 추가
   ↓
6. Worker:
   - DB 업데이트: status = 'processing'
   - DB에서 terrain 정보 조회 (blend_file_path)
   - 기존 terrain.blend 파일 로드
   - Road curve 생성 (control points 기반)
   - Shrinkwrap modifier 적용
   - 렌더링
   - 새 파일 저장 (output/road_xxx.blend)
   ↓
7. Worker: Job 완료
   - DB: Road 레코드 생성
     INSERT INTO roads (id, terrain_id, control_points, blend_file_path, ...)
   - DB: Job 업데이트
     UPDATE jobs SET status='completed', result={...}
   ↓
8. 완료: 도로가 포함된 새 .blend 파일 + DB 기록
```

---

## 9. Claude API 사용 방식

### 옵션 1: 서버 단일 API Key (추천 - 초기)
```typescript
// 서버 환경변수
ANTHROPIC_API_KEY=sk-ant-...

// 모든 사용자 요청에 서버 키 사용
const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY
});
```
- **장점**: 간단, 빠른 구현
- **단점**: 서버가 비용 부담

### 옵션 2: 사용자 API Key 입력 (추후)
```typescript
// 사용자가 본인 API Key 입력
POST /api/terrain
{
  "description": "...",
  "apiKey": "sk-ant-user-key..."
}
```
- **장점**: 비용 분산
- **단점**: 사용자 진입 장벽

---

## 10. 파일 구조 (실제 구현)

```
blender-terrain-mcp/
├── src/
│   ├── server.ts              # Express 서버 (모든 API 엔드포인트 포함)
│   ├── config.ts              # 설정 (Blender 경로 등)
│   ├── db/
│   │   └── client.ts          # Prisma client
│   ├── queue/
│   │   └── blenderQueue.ts    # Bull queue + worker (통합)
│   ├── services/
│   │   ├── claudeService.ts   # Claude API 통합
│   │   └── blenderService.ts  # Blender 실행 로직
│   └── blender-scripts/
│       ├── terrain_generator.py  # Perlin noise terrain
│       └── road_generator.py     # Bezier curve road
├── prisma/
│   └── schema.prisma          # DB 스키마 (Job, Terrain, Road)
├── client/                     # React 프론트엔드
│   ├── src/
│   │   ├── App.tsx            # 메인 UI 컴포넌트
│   │   ├── App.css            # 스타일
│   │   └── main.tsx           # Entry point
│   ├── package.json
│   └── vite.config.ts
├── output/                     # 생성된 파일 저장
│   ├── {jobId}.blend
│   ├── {jobId}_preview.png
│   └── {jobId}_params.json    # 임시 파일 (자동 삭제)
├── .env                        # 환경변수 (DB, API key)
├── package.json
├── tsconfig.json
├── design.md                   # 설계 문서
└── implementation-plan.md      # 구현 계획

---

## 11. 기술 스택

### Backend
- **Runtime**: Node.js 20.15.0 + TypeScript
- **Server**: Express.js + CORS
- **Database**: MySQL 8.0
- **ORM**: Prisma
- **Queue**: Bull (Redis 기반)
- **Redis**: Docker Container (port 6379)
- **AI**: Anthropic Claude API (Sonnet 4.5)
- **3D**: Blender 4.5 (headless mode)

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: CSS (custom dark theme)
- **HTTP Client**: Fetch API

### 구현하지 않은 기능
- ❌ WebSocket 실시간 업데이트 (polling으로 대체)
- ❌ Stable Diffusion height map (Perlin noise로 충분)
- ❌ Three.js 3D 미리보기 (PNG 이미지로 충분)
- ❌ AWS S3 저장 (로컬 파일 시스템)

---

## 12. 구현 우선순위

### Phase 1: 기본 기능 (MVP) ✅ 완료
1. ✅ Node.js + Express + TypeScript 서버 셋업
2. ✅ MySQL + Prisma 셋업
3. ✅ Bull Queue + Redis (Docker) 구성
4. ✅ Blender headless 실행 테스트
5. ✅ Procedural terrain 생성 (Perlin noise displacement)
6. ✅ 기본 road 생성 (Bezier curve + Shrinkwrap)
7. ✅ DB 연동 (Job, Terrain, Road 저장)

### Phase 2: AI 통합 ✅ 완료
1. ✅ Claude API 연결 (Sonnet 4.5)
2. ✅ 텍스트 → terrain 파라미터 변환 (한글 지원)
3. ✅ Fallback 메커니즘 (AI 실패 시 기본값)

### Phase 3: 웹 인터페이스 ✅ 완료
1. ✅ React + Vite Frontend UI
2. ✅ Terrain 생성 폼 (AI/수동 파라미터)
3. ✅ Road 생성 폼 (Control points JSON)
4. ✅ Job 상태 조회 및 Preview 이미지 표시
5. ✅ .blend 파일 다운로드 링크

### Phase 4: 최적화 (선택사항)
1. ⏳ 결과 파일 캐싱
2. ⏳ 이미지 최적화
3. ✅ 에러 처리 & Fallback

---

## 13. 실제 발생한 이슈 & 해결 방안

### 이슈 1: Windows 명령줄 JSON 파라미터 파싱 실패
- **문제**: `blender.exe --python script.py -- '{"scale":20}'` 에서 Windows가 작은따옴표를 제거
- **에러**: `json.decoder.JSONDecodeError: Expecting value: line 1 column 1`
- **해결**: 임시 JSON 파일로 변경
  ```typescript
  const paramsFile = `output/${jobId}_params.json`;
  fs.writeFileSync(paramsFile, JSON.stringify(params));
  const command = `blender --python script.py -- "${paramsFile}"`;
  // 실행 후 파일 삭제
  fs.unlinkSync(paramsFile);
  ```

### 이슈 2: Blender 4.5 Render Engine 이름 변경
- **문제**: `BLENDER_EEVEE` 이름이 Blender 4.5에서 변경됨
- **에러**: `TypeError: enum "BLENDER_EEVEE" not found`
- **해결**: `BLENDER_EEVEE_NEXT` 사용
  ```python
  bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
  ```

### 이슈 3: Claude API 모델명 404 오류
- **문제**: `claude-3-5-sonnet-20241022`, `claude-3-5-sonnet-latest` 등이 404 반환
- **원인**: Claude 3.5 Sonnet이 Claude Sonnet 4.5로 업그레이드됨
- **해결**: 최신 모델명 사용
  ```typescript
  model: 'claude-sonnet-4-5-20250929'
  ```

### 이슈 4: Claude 한글 설명 분석 정확도 낮음
- **문제**: 한글 프롬프트에서 "눈 덮인 높은 산맥" → "평평한 지형"으로 잘못 분석
- **해결**: 영어 프롬프트 + 한글 키워드 예시 추가
  ```typescript
  content: `You are a terrain parameter expert...
  Important:
  - "눈 덮인", "높은", "산" means snowy, tall mountains → high scale (35-45)
  - "바위산", "험준한" means rocky, rugged → high roughness (0.8-0.95)`
  ```

### 이슈 5: Terrain ID vs Job ID 혼동
- **문제**: Road 생성 시 Job ID를 Terrain ID로 사용하여 "Terrain not found" 오류
- **해결**: Job API에서 관계 포함하여 반환
  ```typescript
  await prisma.job.findUnique({
    where: { id: jobId },
    include: { terrain: true, road: true }
  });
  ```

### 예상했지만 발생하지 않은 이슈
- ✅ Blender 프로세스 과부하 (Bull MAX_CONCURRENT=2로 충분)
- ✅ 파일 용량 (100m terrain = 약 425KB, preview PNG = 약 600KB)
- ✅ Claude API 비용 (useAI 옵션으로 제어 가능)

### 이슈 6: Terrain v2.0 - 파라미터 전달 안됨
- **문제**: Claude API가 15개 파라미터를 정확하게 추출했지만, 모든 terrain이 동일하게 생성됨
- **원인**: `server.ts`에서 scale/roughness만 Queue로 전달, 나머지 13개 파라미터 무시
- **해결**: 전체 객체 스프레드로 변경
  ```typescript
  // Before
  finalParams.scale = aiParams.scale;
  finalParams.roughness = aiParams.roughness;

  // After
  finalParams = { ...finalParams, ...aiParams };
  ```

### 이슈 7: Road 생성 - Control Points TypeError
- **문제**: `TypeError: list indices must be integers or slices, not str`
- **원인**: UI는 `[[10,20]]` (list) 전송, 스크립트는 `[{"x":10}]` (dict) 기대
- **해결**: 양쪽 포맷 모두 지원
  ```python
  if isinstance(point, dict):
      x = point['x'] - 50
  else:
      x = point[0] - 50
  ```

### 이슈 8: Road Preview 이미지 경로 오류
- **문제**: Preview 이미지가 `C:\output\`에 저장됨 (잘못된 위치)
- **원인**: Blender가 terrain.blend 로드 후 작업 디렉토리 변경, 상대경로 해석 오류
- **해결**: 모든 경로를 절대경로로 변환
  ```python
  import os
  preview_path = os.path.abspath(args[3])
  ```

---

## 14. 프로젝트 완료 상태 (2025-10-07 업데이트)

### ✅ 완료된 기능
1. ✅ Express + TypeScript 서버
2. ✅ MySQL + Prisma ORM
3. ✅ Bull Queue + Redis (Docker)
4. ✅ Blender 4.5 Headless 실행
5. ✅ Procedural Terrain 생성 v1.0 (Perlin Noise - 2개 파라미터)
6. ✅ **Procedural Terrain 생성 v2.0** (15+ 파라미터 + 높이 기반 머티리얼)
7. ✅ Road 생성 (Bezier Curve + Shrinkwrap)
8. ✅ Claude API 통합 (Sonnet 4.5) - 한글 지원 강화
9. ✅ React 웹 UI (Vite) - Preview 이미지, Terrain ID 복사 기능

### 🔧 API 엔드포인트
- `POST /api/terrain` - Terrain 생성 (AI 또는 수동 파라미터)
- `POST /api/road` - Road 생성 (terrainId + control points)
- `GET /api/job/:jobId` - Job 상태 조회
- `GET /output/:filename` - 파일 다운로드 (static serving)

### 📁 출력 파일
- `output/{jobId}.blend` - Blender 파일 (Terrain: ~3.9GB, Road: ~3.9GB)
- `output/{jobId}_preview.png` - Top-view 미리보기 (1024x1024, ~1.5MB)
- `output/{jobId}_params.json` - 임시 파라미터 파일 (실행 후 자동 삭제)

### 🚀 실행 방법
```bash
# 1. Redis 실행 (Docker)
docker run -d -p 6379:6379 redis

# 2. Backend 실행
npm run dev

# 3. Frontend 실행
cd client && npm run dev

# 4. 브라우저에서 접속
http://localhost:5173
```

### 📊 v2.0 업그레이드 주요 개선사항
1. **파라미터 시스템**: 2개 → 15+ 개로 확장
   - 기본: `scale`, `roughness` → `base_scale`, `base_roughness`, `height_multiplier`
   - 노이즈: `noise_type`, `noise_layers`, `octaves`
   - 지형 특성: `peak_sharpness`, `valley_depth`, `erosion`, `terrace_levels`
   - 머티리얼: `snow_height`, `rock_height`, `grass_height` + RGB 색상
   - 환경: `climate`, `wetness`, `vegetation_density`

2. **머티리얼 시스템**: 높이 기반 자동 색상 적용
   - ColorRamp 노드로 Z 좌표에 따라 눈/바위/풀 색상 자동 변경
   - 각 재질마다 다른 Roughness 값 (눈=0.3, 바위=0.9, 풀=0.6)

3. **Claude API 프롬프트**: 한글 지원 강화
   - "눈 덮인 높은 산" → `height_multiplier: 70-85, snow_height: 0.4-0.6, climate: "arctic"`
   - "평평한 파란색 흙" → `base_scale: 5-10, grass_color: [0.3, 0.4, 0.6]`

4. **Road 생성 안정화**:
   - Control points 포맷 양쪽 지원 (dict/list)
   - 절대경로 사용으로 경로 문제 해결
   - Preview 이미지 정상 표시

### 🎯 테스트 시나리오
```bash
# Terrain v2.0 테스트
curl -X POST http://localhost:3000/api/terrain \
  -d '{"description":"눈으로 덮인 높고 웅장한 산악 지형","useAI":true}' \
  -H "Content-Type: application/json"
# 결과: 높은 봉우리 + 흰색 눈 재질 + 높은 height_multiplier

curl -X POST http://localhost:3000/api/terrain \
  -d '{"description":"매우 평평한 파란색 흙으로 덮인 평지","useAI":true}' \
  -H "Content-Type: application/json"
# 결과: 낮은 지형 + 파란 톤 풀 색상 + 낮은 height_multiplier

# Road 생성 테스트
curl -X POST http://localhost:3000/api/road \
  -d '{"terrainId":"<terrain-id>","controlPoints":[[15,15],[45,35],[85,75]]}' \
  -H "Content-Type: application/json"
# 결과: 지형에 맞춰 도로 생성 + Preview 이미지 표시
```

---

## 부록: Blender Headless 실행 예시

```bash
# Background 모드로 실행
blender --background \
  --python scripts/terrain.py \
  -- \
  --output output/terrain_123.blend \
  --preview output/preview_123.png \
  --scale 15 \
  --roughness 0.7

# Python 스크립트에서 인자 받기
import sys
argv = sys.argv[sys.argv.index("--") + 1:]
output_path = argv[argv.index("--output") + 1]
```