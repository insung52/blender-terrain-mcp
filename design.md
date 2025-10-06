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

## 3. Terrain 생성 방식

### 선택한 방법: 하이브리드 AI + Procedural

#### Step 1: AI 분석
```
입력: 텍스트 ("산악지형") 또는 이미지
  ↓
Claude API: 지형 특성 분석
  {
    type: "mountain",
    features: ["peaks", "valleys", "snow"],
    roughness: 0.7,
    scale: 15
  }
```

#### Step 2: Height Map 생성
```
옵션 A: Stable Diffusion (선택사항)
  - "terrain height map, black and white, mountains"
  - 고품질, 느림 (5-10초)

옵션 B: Procedural Noise (기본)
  - Perlin/Simplex noise
  - 빠름 (< 1초)
  - Claude가 분석한 파라미터 사용
```

#### Step 3: Blender 처리
```python
# Blender Python
1. 100m x 100m Plane 생성
2. Subdivision (detail level)
3. Displacement Modifier (height map 적용)
4. Optional: Erosion simulation
5. Top view render → preview image
6. .blend 파일 저장
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

## 10. 파일 구조

```
blender-terrain-mcp/
├── src/
│   ├── server.ts              # Express 서버
│   ├── db/
│   │   ├── connection.ts      # PostgreSQL 연결
│   │   ├── models/
│   │   │   ├── User.ts
│   │   │   ├── Job.ts
│   │   │   ├── Terrain.ts
│   │   │   └── Road.ts
│   │   └── migrations/        # DB 마이그레이션
│   ├── queue/
│   │   ├── blenderQueue.ts    # Bull queue 설정
│   │   └── worker.ts          # Job 처리 worker
│   ├── services/
│   │   ├── claudeService.ts   # Claude API 통합
│   │   └── blenderService.ts  # Blender 실행 로직
│   ├── routes/
│   │   ├── terrain.ts         # Terrain API
│   │   ├── road.ts            # Road API
│   │   └── jobs.ts            # Job 상태 조회 API
│   └── blender-scripts/
│       ├── terrain_generator.py
│       └── road_generator.py
├── output/                     # 생성된 파일 저장
│   ├── user_abc_terrain_123.blend
│   ├── user_abc_preview_123.png
│   └── ...
├── templates/                  # Blender script 템플릿
├── package.json
├── tsconfig.json
├── design.md                   # 이 문서
└── making.md                   # 기존 요구사항
```

---

## 11. 기술 스택

### Backend
- **Runtime**: Node.js + TypeScript
- **Server**: Express.js
- **Database**: PostgreSQL
- **ORM**: Prisma 또는 TypeORM
- **Queue**: Bull (Redis 기반)
- **AI**: Anthropic Claude API
- **3D**: Blender (headless mode)

### 선택적 추가
- **Image Gen**: Stable Diffusion (height map 생성)
- **Storage**: AWS S3 (결과 파일 저장)
- **WebSocket**: Socket.io (실시간 진행 상황)
- **Frontend**: React + Three.js (3D 미리보기)

---

## 12. 구현 우선순위

### Phase 1: 기본 기능 (MVP)
1. ✅ Node.js + Express + TypeScript 서버 셋업
2. ✅ PostgreSQL + Prisma 셋업
3. ✅ Bull Queue + Redis 구성
4. ✅ Blender headless 실행 테스트
5. ✅ Procedural terrain 생성 (Claude 없이)
6. ✅ 기본 road 생성
7. ✅ DB 연동 (Job, Terrain, Road 저장)

### Phase 2: AI 통합
1. ✅ Claude API 연결
2. ✅ 텍스트 → terrain 파라미터 변환
3. ✅ (Optional) Stable Diffusion height map

### Phase 3: 웹 인터페이스
1. ✅ Frontend UI
2. ✅ Road 그리기 캔버스
3. ✅ WebSocket 실시간 업데이트

### Phase 4: 최적화
1. ✅ 결과 파일 캐싱
2. ✅ 이미지 최적화
3. ✅ 에러 처리 & 재시도

---

## 13. 예상 이슈 & 해결 방안

### 이슈 1: Blender 프로세스 과부하
- **해결**: MAX_CONCURRENT 제한, CPU/RAM 모니터링

### 이슈 2: 긴 처리 시간
- **해결**: WebSocket으로 진행 상황 실시간 전송

### 이슈 3: 파일 용량
- **해결**: .blend 파일 압축, 미리보기는 저해상도

### 이슈 4: Claude API 비용
- **해결**: Procedural 방식 기본, AI는 옵션

---

## 14. 다음 단계

1. **프로젝트 초기화**: `npm init` + TypeScript 설정
2. **DB 셋업**: PostgreSQL + Prisma 스키마 작성
3. **Blender 테스트**: 간단한 Python 스크립트 실행 테스트
4. **Queue 구현**: Bull + Redis 셋업
5. **첫 API**: POST /api/terrain (procedural only) + DB 저장
6. **Claude 통합**: 텍스트 분석 기능 추가

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