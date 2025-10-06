# 단계별 구현 계획

## 전체 구조
각 단계마다 **테스트 → 검증 → 다음 단계** 순서로 진행

---

## Stage 0: 환경 셋업 (5분)
### 목표
프로젝트 기본 구조 만들기

### 작업
1. `package.json` 생성 (Node.js + TypeScript)
2. 필요한 패키지 설치
   - express, typescript, ts-node
   - @types/node, @types/express
3. `tsconfig.json` 설정
4. 기본 폴더 구조 생성
   ```
   src/
   ├── server.ts (기본 Express 서버)
   └── config.ts
   ```

### 테스트
```bash
npm run dev
# → "Server running on port 3000" 출력 확인
```

### 성공 조건
- ✅ `http://localhost:3000` 접속 시 응답
- ✅ TypeScript 컴파일 에러 없음

---

## Stage 1: Blender 제어 테스트 (10분)
### 목표
Node.js에서 Blender를 headless로 실행할 수 있는지 확인

### 작업
1. 간단한 Blender Python 스크립트 작성
   ```python
   # src/blender-scripts/test.py
   import bpy
   import sys

   # Cube 생성
   bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

   # 파일 저장
   output_path = sys.argv[-1]
   bpy.ops.wm.save_as_mainfile(filepath=output_path)
   print(f"SUCCESS: {output_path}")
   ```

2. Node.js에서 Blender 실행 함수 작성
   ```typescript
   // src/services/blenderService.ts
   import { exec } from 'child_process';
   import { promisify } from 'util';

   const execAsync = promisify(exec);

   export async function executeBlenderScript(
     scriptPath: string,
     outputPath: string
   ) {
     const command = `blender --background --python ${scriptPath} -- ${outputPath}`;
     const result = await execAsync(command);
     return result;
   }
   ```

3. 테스트 API 엔드포인트 추가
   ```typescript
   // src/server.ts
   app.get('/test-blender', async (req, res) => {
     const result = await executeBlenderScript(
       'src/blender-scripts/test.py',
       'output/test.blend'
     );
     res.json({ success: true, output: result.stdout });
   });
   ```

### 테스트
```bash
curl http://localhost:3000/test-blender
# → output/test.blend 파일 생성 확인
blender output/test.blend  # 큐브가 있는지 확인
```

### 성공 조건
- ✅ Blender가 headless로 실행됨
- ✅ .blend 파일이 정상 생성됨
- ✅ 에러 처리 동작 확인

---

## Stage 2: PostgreSQL + Prisma 셋업 (15분)
### 목표
데이터베이스 연결 및 기본 모델 생성

### 작업
1. PostgreSQL 설치 및 DB 생성
   ```bash
   # PostgreSQL 설치 (이미 설치되어 있다면 스킵)
   createdb blender_terrain
   ```

2. Prisma 설치 및 초기화
   ```bash
   npm install prisma @prisma/client
   npx prisma init
   ```

3. `prisma/schema.prisma` 작성 (일단 Jobs만)
   ```prisma
   datasource db {
     provider = "postgresql"
     url      = env("DATABASE_URL")
   }

   generator client {
     provider = "prisma-client-js"
   }

   model Job {
     id          String   @id @default(uuid())
     userId      String
     type        String   // 'terrain' | 'road'
     status      String   // 'queued' | 'processing' | 'completed' | 'failed'
     inputParams Json
     result      Json?
     createdAt   DateTime @default(now())
     updatedAt   DateTime @updatedAt
   }
   ```

4. 마이그레이션 실행
   ```bash
   npx prisma migrate dev --name init
   ```

5. Prisma Client 사용 테스트
   ```typescript
   // src/db/client.ts
   import { PrismaClient } from '@prisma/client';
   export const prisma = new PrismaClient();

   // src/server.ts
   app.post('/test-db', async (req, res) => {
     const job = await prisma.job.create({
       data: {
         userId: 'test-user',
         type: 'terrain',
         status: 'queued',
         inputParams: { description: 'test' }
       }
     });
     res.json(job);
   });
   ```

### 테스트
```bash
curl -X POST http://localhost:3000/test-db
# → Job 레코드가 반환되는지 확인

# DB에서 직접 확인
npx prisma studio
# → Jobs 테이블에 레코드가 있는지 확인
```

### 성공 조건
- ✅ PostgreSQL 연결 성공
- ✅ Prisma 마이그레이션 성공
- ✅ Job 생성/조회 가능

---

## Stage 3: Bull Queue 셋업 (15분)
### 목표
Job Queue 시스템 구축

### 작업
1. Redis 설치 및 실행
   ```bash
   # Redis 설치 (이미 설치되어 있다면 스킵)
   redis-server
   ```

2. Bull 설치
   ```bash
   npm install bull @types/bull
   ```

3. Queue 생성
   ```typescript
   // src/queue/blenderQueue.ts
   import Queue from 'bull';

   export const blenderQueue = new Queue('blender-jobs', {
     redis: {
       host: 'localhost',
       port: 6379
     }
   });

   // Worker (일단 간단하게)
   blenderQueue.process(async (job) => {
     console.log('Processing job:', job.id);
     await new Promise(resolve => setTimeout(resolve, 2000)); // 2초 대기
     return { success: true };
   });
   ```

4. API에서 Queue 사용
   ```typescript
   // src/server.ts
   import { blenderQueue } from './queue/blenderQueue';

   app.post('/test-queue', async (req, res) => {
     const job = await blenderQueue.add({
       type: 'test',
       data: req.body
     });
     res.json({ jobId: job.id, status: 'queued' });
   });

   app.get('/test-queue/:jobId', async (req, res) => {
     const job = await blenderQueue.getJob(req.params.jobId);
     const state = await job.getState();
     res.json({ jobId: job.id, status: state });
   });
   ```

### 테스트
```bash
# Job 추가
curl -X POST http://localhost:3000/test-queue -d '{"test":"data"}' -H "Content-Type: application/json"
# → {jobId: "1", status: "queued"} 반환

# Job 상태 확인
curl http://localhost:3000/test-queue/1
# → {jobId: "1", status: "completed"} (2초 후)
```

### 성공 조건
- ✅ Redis 연결 성공
- ✅ Job이 Queue에 추가됨
- ✅ Worker가 Job 처리
- ✅ Job 상태 조회 가능

---

## Stage 4: Blender + Queue + DB 통합 (20분)
### 목표
실제로 Blender를 Queue로 실행하고 결과를 DB에 저장

### 작업
1. Worker에 Blender 실행 로직 추가
   ```typescript
   // src/queue/worker.ts
   import { blenderQueue } from './blenderQueue';
   import { executeBlenderScript } from '../services/blenderService';
   import { prisma } from '../db/client';

   blenderQueue.process(2, async (job) => {  // 동시 2개
     // DB 업데이트: processing
     await prisma.job.update({
       where: { id: job.data.dbJobId },
       data: { status: 'processing' }
     });

     try {
       // Blender 실행
       const outputPath = `output/${job.data.dbJobId}.blend`;
       await executeBlenderScript(
         'src/blender-scripts/test.py',
         outputPath
       );

       // DB 업데이트: completed
       await prisma.job.update({
         where: { id: job.data.dbJobId },
         data: {
           status: 'completed',
           result: { blendFile: outputPath }
         }
       });

       return { success: true };
     } catch (error) {
       // DB 업데이트: failed
       await prisma.job.update({
         where: { id: job.data.dbJobId },
         data: { status: 'failed' }
       });
       throw error;
     }
   });
   ```

2. API 통합
   ```typescript
   // src/routes/test.ts
   app.post('/api/test-full', async (req, res) => {
     // 1. DB에 Job 생성
     const dbJob = await prisma.job.create({
       data: {
         userId: 'test-user',
         type: 'test',
         status: 'queued',
         inputParams: req.body
       }
     });

     // 2. Queue에 Job 추가
     await blenderQueue.add({ dbJobId: dbJob.id });

     res.json({ jobId: dbJob.id, status: 'queued' });
   });

   app.get('/api/job/:jobId', async (req, res) => {
     const job = await prisma.job.findUnique({
       where: { id: req.params.jobId }
     });
     res.json(job);
   });
   ```

### 테스트
```bash
# Job 생성
curl -X POST http://localhost:3000/api/test-full -d '{}' -H "Content-Type: application/json"
# → {jobId: "uuid", status: "queued"}

# 상태 확인 (여러 번)
curl http://localhost:3000/api/job/uuid
# → status: "queued" → "processing" → "completed"

# 파일 확인
ls output/*.blend
```

### 성공 조건
- ✅ API → DB → Queue → Worker → Blender 전체 흐름 동작
- ✅ Job 상태가 올바르게 업데이트됨
- ✅ .blend 파일 생성됨
- ✅ 에러 시 상태가 'failed'로 변경

---

## Stage 5: Procedural Terrain 생성 (30분)
### 목표
실제로 지형을 생성하는 Blender 스크립트 작성

### 작업
1. Terrain 생성 스크립트
   ```python
   # src/blender-scripts/terrain_generator.py
   import bpy
   import sys
   import json

   # 파라미터 읽기
   args = sys.argv[sys.argv.index("--") + 1:]
   params = json.loads(args[0])
   output_path = args[1]

   # 기존 메쉬 삭제
   bpy.ops.object.select_all(action='SELECT')
   bpy.ops.object.delete()

   # Plane 생성 (100m x 100m)
   bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, 0))
   plane = bpy.context.active_object

   # Subdivision
   bpy.ops.object.modifier_add(type='SUBSURF')
   plane.modifiers["Subdivision"].levels = 6

   # Displacement (Noise Texture)
   bpy.ops.object.modifier_add(type='DISPLACE')
   displace = plane.modifiers["Displace"]

   # Texture 생성
   texture = bpy.data.textures.new("NoiseTexture", type='CLOUDS')
   texture.noise_scale = params.get('scale', 15)
   displace.texture = texture
   displace.strength = params.get('roughness', 0.7) * 10

   # Top view 렌더링
   bpy.context.scene.camera.location = (0, 0, 100)
   bpy.context.scene.camera.rotation_euler = (0, 0, 0)

   preview_path = output_path.replace('.blend', '_preview.png')
   bpy.context.scene.render.filepath = preview_path
   bpy.ops.render.render(write_still=True)

   # 저장
   bpy.ops.wm.save_as_mainfile(filepath=output_path)

   print(f"SUCCESS: {output_path}")
   ```

2. Terrain 모델 추가
   ```prisma
   // prisma/schema.prisma
   model Terrain {
     id            String   @id @default(uuid())
     jobId         String   @unique
     job           Job      @relation(fields: [jobId], references: [id])
     userId        String
     description   String?
     blendFilePath String
     topViewPath   String
     metadata      Json?
     createdAt     DateTime @default(now())
   }

   model Job {
     // ... 기존 필드
     terrain       Terrain?
   }
   ```

3. Terrain API
   ```typescript
   // src/routes/terrain.ts
   app.post('/api/terrain', async (req, res) => {
     const { description } = req.body;

     // DB: Job 생성
     const job = await prisma.job.create({
       data: {
         userId: 'test-user',
         type: 'terrain',
         status: 'queued',
         inputParams: { description }
       }
     });

     // Queue: Job 추가
     await blenderQueue.add({
       dbJobId: job.id,
       type: 'terrain',
       params: {
         scale: 15,
         roughness: 0.7
       }
     });

     res.json({ jobId: job.id });
   });
   ```

4. Worker 수정 (terrain 타입 처리)
   ```typescript
   // src/queue/worker.ts
   blenderQueue.process(2, async (job) => {
     if (job.data.type === 'terrain') {
       const outputPath = `output/${job.data.dbJobId}.blend`;
       const params = JSON.stringify(job.data.params);

       await executeBlenderScript(
         'src/blender-scripts/terrain_generator.py',
         `-- '${params}' ${outputPath}`
       );

       // DB: Terrain 생성
       await prisma.terrain.create({
         data: {
           jobId: job.data.dbJobId,
           userId: 'test-user',
           blendFilePath: outputPath,
           topViewPath: outputPath.replace('.blend', '_preview.png'),
           metadata: job.data.params
         }
       });
     }
   });
   ```

### 테스트
```bash
curl -X POST http://localhost:3000/api/terrain \
  -d '{"description":"산악지형"}' \
  -H "Content-Type: application/json"

# 결과 확인
curl http://localhost:3000/api/job/uuid
blender output/uuid.blend  # 지형 확인
```

### 성공 조건
- ✅ 100m x 100m Plane 생성
- ✅ Displacement로 지형 생성
- ✅ Top view 이미지 렌더링
- ✅ DB에 Terrain 레코드 저장

---

## Stage 6: Road 생성 (30분)
### 목표
Control points로 도로 생성

### 작업
1. Road 생성 스크립트
   ```python
   # src/blender-scripts/road_generator.py
   import bpy
   import json
   import sys

   args = sys.argv[sys.argv.index("--") + 1:]
   terrain_path = args[0]
   control_points = json.loads(args[1])
   output_path = args[2]

   # Terrain 파일 로드
   bpy.ops.wm.open_mainfile(filepath=terrain_path)

   # Bezier Curve 생성
   curve_data = bpy.data.curves.new('RoadCurve', type='CURVE')
   curve_data.dimensions = '3D'

   spline = curve_data.splines.new('BEZIER')
   spline.bezier_points.add(len(control_points) - 1)

   for i, point in enumerate(control_points):
     bp = spline.bezier_points[i]
     bp.co = (point['x'], point['y'], 0)
     bp.handle_left_type = 'AUTO'
     bp.handle_right_type = 'AUTO'

   # Curve Object 생성
   curve_obj = bpy.data.objects.new('Road', curve_data)
   bpy.context.collection.objects.link(curve_obj)

   # Curve를 Mesh로 변환 (extrude)
   curve_data.bevel_depth = 0.8  # 1.6m width (양쪽 0.8m)

   # Shrinkwrap Modifier (terrain에 맞춤)
   terrain_obj = bpy.data.objects['Plane']  # terrain object
   modifier = curve_obj.modifiers.new('Shrinkwrap', 'SHRINKWRAP')
   modifier.target = terrain_obj
   modifier.wrap_method = 'PROJECT'

   # 저장
   bpy.ops.wm.save_as_mainfile(filepath=output_path)
   ```

2. Road API
   ```typescript
   app.post('/api/road', async (req, res) => {
     const { terrainId, controlPoints } = req.body;

     // Terrain 조회
     const terrain = await prisma.terrain.findUnique({
       where: { id: terrainId }
     });

     if (!terrain) {
       return res.status(404).json({ error: 'Terrain not found' });
     }

     // Job 생성
     const job = await prisma.job.create({
       data: {
         userId: 'test-user',
         type: 'road',
         status: 'queued',
         inputParams: { terrainId, controlPoints }
       }
     });

     // Queue 추가
     await blenderQueue.add({
       dbJobId: job.id,
       type: 'road',
       terrainPath: terrain.blendFilePath,
       controlPoints
     });

     res.json({ jobId: job.id });
   });
   ```

### 테스트
```bash
# 먼저 terrain 생성
TERRAIN_ID=$(curl -X POST http://localhost:3000/api/terrain -d '{"description":"평지"}' -H "Content-Type: application/json" | jq -r .jobId)

# 완료 대기 후 road 생성
curl -X POST http://localhost:3000/api/road \
  -d "{\"terrainId\":\"$TERRAIN_ID\",\"controlPoints\":[{\"x\":0,\"y\":0},{\"x\":20,\"y\":30},{\"x\":50,\"y\":50}]}" \
  -H "Content-Type: application/json"
```

### 성공 조건
- ✅ 기존 terrain에 road 추가
- ✅ Control points로 curve 생성
- ✅ Shrinkwrap으로 지형에 맞춤
- ✅ 새 .blend 파일 저장

---

## Stage 7: Claude API 통합 (20분)
### 목표
텍스트 설명을 terrain 파라미터로 변환

### 작업
1. Claude API 서비스
   ```typescript
   // src/services/claudeService.ts
   import Anthropic from '@anthropic-ai/sdk';

   const client = new Anthropic({
     apiKey: process.env.ANTHROPIC_API_KEY
   });

   export async function analyzeTerrainDescription(description: string) {
     const response = await client.messages.create({
       model: 'claude-3-5-sonnet-20241022',
       max_tokens: 1024,
       messages: [{
         role: 'user',
         content: `
지형 설명: "${description}"

이 설명을 Blender terrain 파라미터로 변환해줘.
JSON 형식으로만 답변:
{
  "scale": 5-50 (지형 크기, 큰 산일수록 높음),
  "roughness": 0-1 (거칠기, 바위산=0.9, 평지=0.1),
  "features": ["peaks", "valleys", "snow", ...],
  "description": "한줄 요약"
}
         `
       }]
     });

     const text = response.content[0].text;
     const json = JSON.parse(text);
     return json;
   }
   ```

2. Terrain API 수정
   ```typescript
   app.post('/api/terrain', async (req, res) => {
     const { description } = req.body;

     // Claude로 분석
     const params = await analyzeTerrainDescription(description);

     // Job 생성 (params 포함)
     const job = await prisma.job.create({
       data: {
         userId: 'test-user',
         type: 'terrain',
         status: 'queued',
         inputParams: { description, aiParams: params }
       }
     });

     // Queue 추가
     await blenderQueue.add({
       dbJobId: job.id,
       type: 'terrain',
       params: {
         scale: params.scale,
         roughness: params.roughness
       }
     });

     res.json({ jobId: job.id, params });
   });
   ```

### 테스트
```bash
curl -X POST http://localhost:3000/api/terrain \
  -d '{"description":"눈 덮인 높은 산맥"}' \
  -H "Content-Type: application/json"

# → params에 scale, roughness 값 확인
```

### 성공 조건
- ✅ Claude API 연결
- ✅ 텍스트 → 파라미터 변환
- ✅ 변환된 파라미터로 terrain 생성

---

## Stage 8: 웹 인터페이스 (선택사항, 1-2시간)
### 목표
간단한 프론트엔드

### 작업
- React + Vite 셋업
- Terrain 생성 폼
- Road 그리기 캔버스
- Job 상태 폴링

---

## 요약: 단계별 체크리스트

- [ ] **Stage 0**: 환경 셋업 (5분)
- [ ] **Stage 1**: Blender 제어 테스트 (10분)
- [ ] **Stage 2**: PostgreSQL + Prisma (15분)
- [ ] **Stage 3**: Bull Queue (15분)
- [ ] **Stage 4**: Blender + Queue + DB 통합 (20분)
- [ ] **Stage 5**: Procedural Terrain 생성 (30분)
- [ ] **Stage 6**: Road 생성 (30분)
- [ ] **Stage 7**: Claude API 통합 (20분)
- [ ] **Stage 8**: 웹 인터페이스 (선택)

**총 예상 시간: 약 2-3시간**

---

## 다음 단계

이제 Stage 0부터 하나씩 진행할까요?
