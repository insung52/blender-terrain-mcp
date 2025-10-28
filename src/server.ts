import express from 'express';
import cors from 'cors';
import { executeBlenderScript, exportToGLTF } from './services/blenderService';
import { prisma } from './db/client';
import { blenderQueue } from './queue/blenderQueue';
import { analyzeTerrainDescription } from './services/claudeService';
import { generateBiomeLayout } from './services/biomeService';
import { progressService } from './services/progressService';
import path from 'path';
import fs from 'fs';

const app = express();
const PORT = 3000;

// Ensure output directory exists
const outputDir = path.join(process.cwd(), 'output');
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
  console.log('📁 Created output directory');
}

// Check API key on startup
console.log('🔑 ANTHROPIC_API_KEY:', process.env.ANTHROPIC_API_KEY
  ? `${process.env.ANTHROPIC_API_KEY.substring(0, 20)}... (${process.env.ANTHROPIC_API_KEY.length} chars)`
  : 'NOT SET');

// Middleware
app.use(cors());
app.use(express.json());
app.use('/output', express.static(path.join(__dirname, '../output')));

// Health check API (moved before wildcard route)
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Blender Terrain MCP Server',
    version: '1.0.0'
  });
});

// SSE endpoint for job progress
app.get('/api/job/:jobId/progress', (req, res) => {
  const { jobId } = req.params;

  // SSE 헤더 설정
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('Access-Control-Allow-Origin', '*');

  // 연결 등록
  progressService.addConnection(jobId, res);

  // 현재 상태 즉시 전송
  const progress = progressService.getJobProgress(jobId);
  if (progress) {
    res.write(`data: ${JSON.stringify({
      type: 'connected',
      status: progress.status,
      currentStep: progress.currentStep,
      steps: progress.steps
    })}\n\n`);
  } else {
    res.write(`data: ${JSON.stringify({
      type: 'not_found',
      message: 'Job not found'
    })}\n\n`);
  }

  console.log(`[SSE] Client connected to job ${jobId}`);

  // 연결 해제 시
  req.on('close', () => {
    console.log(`[SSE] Client disconnected from job ${jobId}`);
  });
});

// Get job progress status (for polling or reconnect)
app.get('/api/job/:jobId/status', async (req, res) => {
  try {
    const { jobId } = req.params;

    // 1. 먼저 progressService에서 실시간 진행 상태 확인
    const progress = progressService.getJobProgress(jobId);

    // 2. DB에서 job 정보 조회
    const job = await prisma.job.findUnique({
      where: { id: jobId },
      include: { terrain: true, road: true }
    });

    if (!job) {
      return res.status(404).json({ success: false, error: 'Job not found' });
    }

    res.json({
      success: true,
      job: {
        id: job.id,
        type: job.type,
        status: job.status,
        createdAt: job.createdAt,
        terrain: job.terrain,
        road: job.road
      },
      progress: progress ? {
        currentStep: progress.currentStep,
        steps: progress.steps,
        status: progress.status
      } : null
    });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Test Blender execution
app.get('/test-blender', async (req, res) => {
  try {
    const scriptPath = path.join(__dirname, 'blender-scripts', 'test.py');
    const outputPath = path.join(process.cwd(), 'output', 'test.blend');

    console.log('Executing Blender script...');
    const result = await executeBlenderScript(scriptPath, outputPath);

    res.json({
      success: true,
      message: 'Blender executed successfully',
      outputPath,
      stdout: result.stdout.slice(-200) // Last 200 chars
    });
  } catch (error: any) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Test Database
app.post('/test-db', async (req, res) => {
  try {
    const job = await prisma.job.create({
      data: {
        userId: 'test-user',
        type: 'terrain',
        status: 'queued',
        inputParams: { description: 'test terrain' }
      }
    });
    res.json({ success: true, job });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

app.get('/test-db/:jobId', async (req, res) => {
  try {
    const job = await prisma.job.findUnique({
      where: { id: req.params.jobId }
    });
    res.json({ success: true, job });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Test Queue
app.post('/test-queue', async (req, res) => {
  try {
    const job = await blenderQueue.add({
      type: 'test',
      data: req.body
    });
    res.json({ success: true, jobId: job.id, status: 'queued' });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

app.get('/test-queue/:jobId', async (req, res) => {
  try {
    const job = await blenderQueue.getJob(req.params.jobId);
    if (!job) {
      return res.status(404).json({ success: false, error: 'Job not found' });
    }
    const state = await job.getState();
    res.json({
      success: true,
      jobId: job.id,
      status: state,
      data: job.data,
      returnvalue: job.returnvalue
    });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Full workflow test: API → DB → Queue → Blender → DB
app.post('/api/test-full', async (req, res) => {
  try {
    // 1. DB에 Job 생성
    const dbJob = await prisma.job.create({
      data: {
        userId: 'test-user',
        type: 'test',
        status: 'queued',
        inputParams: req.body || {}
      }
    });

    console.log(`[API] Created DB Job: ${dbJob.id}`);

    // 2. Queue에 Job 추가
    await blenderQueue.add({
      dbJobId: dbJob.id,
      type: 'test',
      params: {}
    });

    console.log(`[API] Added to Queue: ${dbJob.id}`);

    res.json({
      success: true,
      jobId: dbJob.id,
      status: 'queued',
      message: 'Job created and queued for processing'
    });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Get job status (DB)
app.get('/api/job/:jobId', async (req, res) => {
  try {
    const job = await prisma.job.findUnique({
      where: { id: req.params.jobId },
      include: { terrain: true, road: true }
    });

    if (!job) {
      return res.status(404).json({ success: false, error: 'Job not found' });
    }

    res.json({ success: true, job });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Get job by terrain ID
app.get('/api/job/terrain/:terrainId', async (req, res) => {
  try {
    const job = await prisma.job.findFirst({
      where: {
        terrain: { id: req.params.terrainId }
      },
      include: { terrain: true, road: true },
      orderBy: { createdAt: 'desc' }
    });

    if (!job) {
      return res.status(404).json({ success: false, error: 'Job not found' });
    }

    res.json({ success: true, job });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Get job by road ID
app.get('/api/job/road/:roadId', async (req, res) => {
  try {
    const job = await prisma.job.findFirst({
      where: {
        road: { id: req.params.roadId }
      },
      include: { terrain: true, road: true },
      orderBy: { createdAt: 'desc' }
    });

    if (!job) {
      return res.status(404).json({ success: false, error: 'Job not found' });
    }

    res.json({ success: true, job });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Get all completed terrains
app.get('/api/terrains', async (req, res) => {
  try {
    const terrains = await prisma.terrain.findMany({
      orderBy: { createdAt: 'desc' },
      take: 50  // 최근 50개
    });

    res.json({ success: true, terrains });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Get all roads
app.get('/api/roads', async (req, res) => {
  try {
    const roads = await prisma.road.findMany({
      include: { terrain: true },
      orderBy: { createdAt: 'desc' },
      take: 50
    });

    res.json({ success: true, roads });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Delete terrain
app.delete('/api/terrain/:terrainId', async (req, res) => {
  try {
    const { terrainId } = req.params;

    // Get terrain data first to delete files
    const terrain = await prisma.terrain.findUnique({
      where: { id: terrainId }
    });

    if (!terrain) {
      return res.status(404).json({ success: false, error: 'Terrain not found' });
    }

    // Delete related roads and their files
    const roads = await prisma.road.findMany({
      where: { terrainId }
    });

    for (const road of roads) {
      // Delete road files
      if (road.blendFilePath) {
        try {
          const fs = require('fs');
          if (fs.existsSync(road.blendFilePath)) {
            fs.unlinkSync(road.blendFilePath);
          }
        } catch (err) {
          console.error(`Failed to delete road blend file: ${road.blendFilePath}`, err);
        }
      }
      if (road.previewPath) {
        try {
          const fs = require('fs');
          if (fs.existsSync(road.previewPath)) {
            fs.unlinkSync(road.previewPath);
          }
        } catch (err) {
          console.error(`Failed to delete road preview: ${road.previewPath}`, err);
        }
      }
    }

    // Delete roads from DB
    await prisma.road.deleteMany({
      where: { terrainId }
    });

    // Delete terrain files
    const fs = require('fs');
    const path = require('path');

    if (terrain.blendFilePath) {
      try {
        if (fs.existsSync(terrain.blendFilePath)) {
          fs.unlinkSync(terrain.blendFilePath);
          console.log(`Deleted blend file: ${terrain.blendFilePath}`);
        }
      } catch (err) {
        console.error(`Failed to delete terrain blend file: ${terrain.blendFilePath}`, err);
      }
    }

    if (terrain.topViewPath) {
      try {
        if (fs.existsSync(terrain.topViewPath)) {
          fs.unlinkSync(terrain.topViewPath);
          console.log(`Deleted preview: ${terrain.topViewPath}`);
        }

        // 로그 파일 삭제 (preview 경로 기반)
        const logPath = terrain.topViewPath.replace('.png', '_log.txt');
        if (fs.existsSync(logPath)) {
          fs.unlinkSync(logPath);
          console.log(`Deleted log file: ${logPath}`);
        }

        // 바이옴 폴더 삭제 (preview 경로에서 ID 추출)
        const previewBasename = path.basename(terrain.topViewPath, '_preview.png');
        const biomeFolderPath = path.join(path.dirname(terrain.topViewPath), `biome_${previewBasename}`);
        if (fs.existsSync(biomeFolderPath)) {
          fs.rmSync(biomeFolderPath, { recursive: true, force: true });
          console.log(`Deleted biome folder: ${biomeFolderPath}`);
        }
      } catch (err) {
        console.error(`Failed to delete terrain preview files: ${terrain.topViewPath}`, err);
      }
    }

    // Delete terrain from DB
    await prisma.terrain.delete({
      where: { id: terrainId }
    });

    res.json({ success: true, message: 'Terrain and files deleted' });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Delete road
app.delete('/api/road/:roadId', async (req, res) => {
  try {
    const { roadId } = req.params;

    // Get road data first to delete files
    const road = await prisma.road.findUnique({
      where: { id: roadId }
    });

    if (!road) {
      return res.status(404).json({ success: false, error: 'Road not found' });
    }

    // Delete road files
    const fs = require('fs');
    const path = require('path');

    if (road.blendFilePath) {
      try {
        if (fs.existsSync(road.blendFilePath)) {
          fs.unlinkSync(road.blendFilePath);
          console.log(`Deleted road blend file: ${road.blendFilePath}`);
        }

        // 파라미터 파일 삭제 (blend 파일과 같은 이름)
        const paramsPath = road.blendFilePath.replace('.blend', '_params.json');
        if (fs.existsSync(paramsPath)) {
          fs.unlinkSync(paramsPath);
          console.log(`Deleted road params: ${paramsPath}`);
        }
      } catch (err) {
        console.error(`Failed to delete road blend file: ${road.blendFilePath}`, err);
      }
    }

    if (road.previewPath) {
      try {
        if (fs.existsSync(road.previewPath)) {
          fs.unlinkSync(road.previewPath);
          console.log(`Deleted road preview: ${road.previewPath}`);
        }

        // 로그 파일 삭제 (preview 경로 기반)
        const logPath = road.previewPath.replace('.png', '_log.txt');
        if (fs.existsSync(logPath)) {
          fs.unlinkSync(logPath);
          console.log(`Deleted road log file: ${logPath}`);
        }
      } catch (err) {
        console.error(`Failed to delete road preview files: ${road.previewPath}`, err);
      }
    }

    // Delete road from DB
    await prisma.road.delete({
      where: { id: roadId }
    });

    res.json({ success: true, message: 'Road and files deleted' });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Terrain 생성 API
app.post('/api/terrain', async (req, res) => {
  try {
    const { description, scale, roughness, size, terrain_scale, useAI, useBiome } = req.body;

    let finalParams: any = {
      scale: scale || 15,
      roughness: roughness || 0.7,
      terrain_scale: terrain_scale || 10,
      description: description || '',
      useBiome: useBiome || false
    };

    // **바이옴 모드**: useAI가 true이고 description이 있으면 바이옴 지형 생성
    if (useAI && description && process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY !== 'your-api-key-here') {
      console.log(`[API] 🌍 BIOME MODE: Generating biome layout from: "${description}"`);
      console.log(`[API] Using API key: ${process.env.ANTHROPIC_API_KEY.substring(0, 20)}... (${process.env.ANTHROPIC_API_KEY.length} chars)`);

      try {
        const biomeLayout = await generateBiomeLayout(description);
        console.log(`[API] ✅ Biome layout generated: ${biomeLayout.biome_points.length} biome points`);

        finalParams = {
          ...finalParams,
          useBiome: true,
          biomeLayout: biomeLayout
        };
      } catch (error: any) {
        console.error(`[API] ❌ Biome generation FAILED:`, error.message);
        console.error(`[API] Full error:`, error);
        // Fallback: 기존 방식으로 진행
        finalParams.useBiome = false;
      }
    } else {
      console.log(`[API] Standard terrain mode - useAI: ${useAI}, description: ${!!description}, API key: ${!!process.env.ANTHROPIC_API_KEY}`);
    }

    // DB: Job 생성
    const dbJob = await prisma.job.create({
      data: {
        userId: 'test-user',
        type: 'terrain',
        status: 'queued',
        inputParams: { ...finalParams, useAI }
      }
    });

    console.log(`[API] Created terrain job: ${dbJob.id}`);

    // Terrain 레코드를 미리 생성 (status: processing)
    const terrain = await prisma.terrain.create({
      data: {
        jobId: dbJob.id,
        userId: 'test-user',
        description: finalParams.description || null,
        blendFilePath: '', // 아직 생성 안됨
        topViewPath: '', // 아직 생성 안됨
        metadata: { ...finalParams, status: 'processing' }
      }
    });

    console.log(`[API] Created placeholder terrain: ${terrain.id}`);

    // Progress 추적 등록
    if (finalParams.useBiome) {
      progressService.registerJob(dbJob.id, [
        'biome_analysis',
        'biome_maps',
        'terrain_generation',
        'preview_render'
      ]);
    } else {
      progressService.registerJob(dbJob.id, [
        'terrain_generation',
        'preview_render'
      ]);
    }

    // Queue: Job 추가
    await blenderQueue.add({
      dbJobId: dbJob.id,
      type: 'terrain',
      params: finalParams
    });

    res.json({
      success: true,
      jobId: dbJob.id,
      terrainId: terrain.id,
      status: 'queued',
      message: finalParams.useBiome ? 'Biome terrain generation started' : 'Terrain generation started'
    });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Road 생성 API
app.post('/api/road', async (req, res) => {
  try {
    const { terrainId, controlPoints, width } = req.body;

    // Terrain 조회
    const terrain = await prisma.terrain.findUnique({
      where: { id: terrainId }
    });

    if (!terrain) {
      return res.status(404).json({ success: false, error: 'Terrain not found' });
    }

    // DB: Job 생성
    const dbJob = await prisma.job.create({
      data: {
        userId: 'test-user',
        type: 'road',
        status: 'queued',
        inputParams: { terrainId, controlPoints, width }
      }
    });

    console.log(`[API] Created road job: ${dbJob.id}`);

    // Queue: Job 추가
    await blenderQueue.add({
      dbJobId: dbJob.id,
      type: 'road',
      params: {
        terrainId,
        terrainBlendPath: terrain.blendFilePath,
        controlPoints,
        width: width || 1.6
      }
    });

    res.json({
      success: true,
      jobId: dbJob.id,
      status: 'queued',
      message: 'Road generation started'
    });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GLTF Export API
app.post('/api/terrain/:terrainId/export-gltf', async (req, res) => {
  try {
    const { terrainId } = req.params;

    // 1. Terrain 조회
    const terrain = await prisma.terrain.findUnique({
      where: { id: terrainId }
    });

    if (!terrain || !terrain.blendFilePath) {
      return res.status(404).json({ success: false, error: 'Terrain not found' });
    }

    // 2. 이미 GLTF 파일이 있는지 확인 (캐싱)
    const glbPath = terrain.blendFilePath.replace('.blend', '.glb');

    if (fs.existsSync(glbPath)) {
      console.log(`[API] GLTF file already exists (cached): ${glbPath}`);
      return res.json({ success: true, glbPath: glbPath, cached: true });
    }

    // 3. GLTF Export 실행
    console.log(`[API] Exporting terrain to GLTF: ${terrainId}`);
    const result = await exportToGLTF(terrain.blendFilePath, glbPath);

    // 4. DB 업데이트 (metadata에 GLTF 경로 저장)
    await prisma.terrain.update({
      where: { id: terrainId },
      data: { metadata: { ...(terrain.metadata as any), gltfPath: glbPath } }
    });

    console.log(`[API] ✅ GLTF export completed: ${glbPath}`);
    res.json({ success: true, glbPath: glbPath, cached: false });
  } catch (error: any) {
    console.error(`[API] ❌ GLTF export failed:`, error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// GLTF 파일 다운로드
app.get('/api/terrain/:terrainId/download-gltf', async (req, res) => {
  try {
    const { terrainId } = req.params;
    const terrain = await prisma.terrain.findUnique({ where: { id: terrainId } });

    if (!terrain) {
      return res.status(404).json({ error: 'Terrain not found' });
    }

    const glbPath = terrain.blendFilePath!.replace('.blend', '.glb');

    if (!fs.existsSync(glbPath)) {
      return res.status(404).json({ error: 'GLTF file not found. Please export first.' });
    }

    console.log(`[API] Downloading GLTF: ${glbPath}`);
    res.download(glbPath, `terrain_${terrainId}.glb`);
  } catch (error: any) {
    console.error(`[API] ❌ GLTF download failed:`, error.message);
    res.status(500).json({ error: error.message });
  }
});

// Road GLTF Export API
app.post('/api/road/:roadId/export-gltf', async (req, res) => {
  try {
    const { roadId } = req.params;

    // 1. Road 조회
    const road = await prisma.road.findUnique({
      where: { id: roadId }
    });

    if (!road || !road.blendFilePath) {
      return res.status(404).json({ success: false, error: 'Road not found' });
    }

    // 2. 이미 GLTF 파일이 있는지 확인 (캐싱)
    const glbPath = road.blendFilePath.replace('.blend', '.glb');

    if (fs.existsSync(glbPath)) {
      console.log(`[API] GLTF file already exists (cached): ${glbPath}`);
      return res.json({ success: true, glbPath: glbPath, cached: true });
    }

    // 3. GLTF Export 실행
    console.log(`[API] Exporting road to GLTF: ${roadId}`);
    const result = await exportToGLTF(road.blendFilePath, glbPath);

    console.log(`[API] ✅ GLTF export completed: ${glbPath}`);
    res.json({ success: true, glbPath: glbPath, cached: false });
  } catch (error: any) {
    console.error(`[API] ❌ GLTF export failed:`, error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// Road GLTF 파일 다운로드
app.get('/api/road/:roadId/download-gltf', async (req, res) => {
  try {
    const { roadId } = req.params;
    const road = await prisma.road.findUnique({ where: { id: roadId } });

    if (!road) {
      return res.status(404).json({ error: 'Road not found' });
    }

    const glbPath = road.blendFilePath!.replace('.blend', '.glb');

    if (!fs.existsSync(glbPath)) {
      return res.status(404).json({ error: 'GLTF file not found. Please export first.' });
    }

    console.log(`[API] Downloading Road GLTF: ${glbPath}`);
    res.download(glbPath, `road_${roadId}.glb`);
  } catch (error: any) {
    console.error(`[API] ❌ GLTF download failed:`, error.message);
    res.status(500).json({ error: error.message });
  }
});

// ============================================================
// Objects API (독립 엔티티)
// ============================================================

// POST /api/objects - 새로운 오브젝트 생성
app.post('/api/objects', async (req, res) => {
  try {
    const { terrainId, roadId, objectCount = 100, userId = 'test-user' } = req.body;

    console.log(`[API] Creating objects: terrainId=${terrainId}, roadId=${roadId}, count=${objectCount}`);

    // 1. Terrain 조회
    const terrain = await prisma.terrain.findUnique({
      where: { id: terrainId }
    });

    if (!terrain) {
      return res.status(404).json({ success: false, error: 'Terrain not found' });
    }

    // 2. Road 조회 (optional)
    let baseBlendPath = terrain.blendFilePath;
    if (roadId) {
      const road = await prisma.road.findUnique({
        where: { id: roadId }
      });
      if (road) {
        baseBlendPath = road.blendFilePath;
      }
    }

    // 3. Biome maps 경로 찾기
    const terrainPreviewPath = terrain.topViewPath;
    const previewBasename = path.basename(terrainPreviewPath, '_preview.png');
    const biomeMapsDir = path.join(path.dirname(terrainPreviewPath), `biome_${previewBasename}`, 'biome_maps');

    if (!fs.existsSync(biomeMapsDir)) {
      return res.status(404).json({ success: false, error: 'Biome maps not found' });
    }

    // 4. 출력 경로 생성
    const objectsId = `objects_${Date.now()}`;
    const outputBlendPath = path.join(outputDir, `${objectsId}.blend`);
    const assetsDir = path.join(process.cwd(), 'assets');

    // 5. Job 생성
    const dbJob = await prisma.job.create({
      data: {
        userId,
        type: 'objects',
        status: 'queued',
        inputParams: { terrainId, roadId, objectCount, baseBlendPath, biomeMapsDir, assetsDir, outputBlendPath }
      }
    });

    console.log(`[API] Created objects job: ${dbJob.id}`);

    // 6. Objects 레코드를 미리 생성 (status: processing)
    const objects = await prisma.objects.create({
      data: {
        terrainId,
        roadId: roadId || null,
        userId,
        blendFilePath: '', // 아직 생성 안됨
        previewPath: '', // 프리뷰 없음
        objectCount: 0, // 아직 배치 안됨
        metadata: {
          status: 'processing',
          requestedCount: objectCount,
          jobId: dbJob.id
        }
      }
    });

    console.log(`[API] Created placeholder objects: ${objects.id}`);

    // 7. Progress 추적 등록
    progressService.registerJob(dbJob.id, ['object_placement']);

    // 8. 백그라운드 작업 시작 (비동기)
    (async () => {
      try {
        progressService.updateJobStatus(dbJob.id, 'processing');
        progressService.startStep(dbJob.id, 'object_placement', 'Starting object placement...');

        console.log(`[Background] Placing objects...`);
        console.log(`  - Base blend: ${baseBlendPath}`);
        console.log(`  - Output blend: ${outputBlendPath}`);
        console.log(`  - Biome maps: ${biomeMapsDir}`);

        const { placeObjectsOnTerrain } = await import('./services/blenderService');
        const result = await placeObjectsOnTerrain(
          baseBlendPath,
          biomeMapsDir,
          assetsDir,
          objectCount,
          outputBlendPath,
          '', // 프리뷰 없음
          (current: number, total: number, eta: number) => {
            // Progress 업데이트
            const progress = (current / total) * 100;
            const etaMin = Math.floor(eta / 60);
            const etaSec = Math.floor(eta % 60);
            progressService.updateStepProgress(
              dbJob.id,
              'object_placement',
              progress,
              `Placed ${current}/${total} objects (ETA: ${etaMin}m ${etaSec}s)`
            );
          }
        );

        console.log(`[Background] ✅ Objects placed: ${result.placedCount}/${objectCount}`);

        // Objects 레코드 업데이트 (먼저 수행)
        await prisma.objects.update({
          where: { id: objects.id },
          data: {
            blendFilePath: outputBlendPath,
            objectCount: result.placedCount,
            metadata: {
              status: 'completed',
              requestedCount: objectCount,
              actualCount: result.placedCount,
              jobId: dbJob.id
            }
          }
        });

        // Job 완료
        await prisma.job.update({
          where: { id: dbJob.id },
          data: { status: 'completed', result: { objectCount: result.placedCount } }
        });

        // Progress 완료 (DB 업데이트 후에 SSE 전송)
        progressService.completeStep(dbJob.id, 'object_placement', `Placed ${result.placedCount} objects`);
        progressService.completeJob(dbJob.id, { objectCount: result.placedCount });

      } catch (error: any) {
        console.error(`[Background] ❌ Objects creation failed:`, error.message);

        // Progress 실패 처리
        progressService.failJob(dbJob.id, error.message);

        // Job 실패
        await prisma.job.update({
          where: { id: dbJob.id },
          data: { status: 'failed' }
        });

        // Objects 레코드 업데이트 (실패 상태)
        await prisma.objects.update({
          where: { id: objects.id },
          data: {
            metadata: {
              status: 'failed',
              error: error.message,
              jobId: dbJob.id
            }
          }
        });
      }
    })();

    // 즉시 응답 반환
    res.json({
      success: true,
      jobId: dbJob.id,
      objectsId: objects.id
    });
  } catch (error: any) {
    console.error(`[API] ❌ Objects creation failed:`, error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/objects - 오브젝트 목록 조회
app.get('/api/objects', async (req, res) => {
  try {
    const { userId = 'test-user' } = req.query;

    const objects = await prisma.objects.findMany({
      where: { userId: userId as string },
      include: {
        terrain: { select: { id: true, description: true } },
        road: { select: { id: true } }
      },
      orderBy: { createdAt: 'desc' }
    });

    res.json({ success: true, objects });
  } catch (error: any) {
    console.error(`[API] ❌ Failed to fetch objects:`, error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/objects/:id/download - GLB 다운로드
app.get('/api/objects/:id/download', async (req, res) => {
  try {
    const { id } = req.params;

    console.log(`[API] Exporting objects to GLTF: ${id}`);

    const objects = await prisma.objects.findUnique({
      where: { id }
    });

    if (!objects || !objects.blendFilePath) {
      return res.status(404).json({ success: false, error: 'Objects not found' });
    }

    // GLB 파일이 없으면 생성
    let glbPath = objects.glbFilePath;
    if (!glbPath || !fs.existsSync(glbPath)) {
      glbPath = objects.blendFilePath.replace('.blend', '.glb');

      const { exportToGLTF } = await import('./services/blenderService');
      await exportToGLTF(objects.blendFilePath, glbPath);

      // DB 업데이트
      await prisma.objects.update({
        where: { id },
        data: { glbFilePath: glbPath }
      });
    }

    console.log(`[API] ✅ GLB ready: ${glbPath}`);
    res.download(glbPath);
  } catch (error: any) {
    console.error(`[API] ❌ GLTF export failed:`, error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET /api/objects/:id/download-blend - Blend 파일 다운로드
app.get('/api/objects/:id/download-blend', async (req, res) => {
  try {
    const { id } = req.params;

    console.log(`[API] Downloading blend file for objects: ${id}`);

    const objects = await prisma.objects.findUnique({
      where: { id }
    });

    if (!objects || !objects.blendFilePath) {
      return res.status(404).json({ success: false, error: 'Objects not found' });
    }

    if (!fs.existsSync(objects.blendFilePath)) {
      return res.status(404).json({ success: false, error: 'Blend file not found' });
    }

    console.log(`[API] ✅ Blend file ready: ${objects.blendFilePath}`);
    res.download(objects.blendFilePath);
  } catch (error: any) {
    console.error(`[API] ❌ Blend download failed:`, error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// DELETE /api/objects/:id - 오브젝트 삭제
app.delete('/api/objects/:id', async (req, res) => {
  try {
    const { id } = req.params;

    const objects = await prisma.objects.findUnique({
      where: { id }
    });

    if (!objects) {
      return res.status(404).json({ success: false, error: 'Objects not found' });
    }

    // 파일 삭제
    if (fs.existsSync(objects.blendFilePath)) {
      fs.unlinkSync(objects.blendFilePath);
    }
    if (fs.existsSync(objects.previewPath)) {
      fs.unlinkSync(objects.previewPath);
    }
    if (objects.glbFilePath && fs.existsSync(objects.glbFilePath)) {
      fs.unlinkSync(objects.glbFilePath);
    }

    // DB 삭제
    await prisma.objects.delete({
      where: { id }
    });

    res.json({ success: true });
  } catch (error: any) {
    console.error(`[API] ❌ Failed to delete objects:`, error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// Serve static files from React app (프로덕션 모드)
app.use(express.static(path.join(__dirname, '../client/dist')));

// All remaining requests return the React app (프론트엔드 라우팅 지원)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../client/dist/index.html'));
});

// Start server
app.listen(PORT, () => {
  console.log(`✅ Server running on http://localhost:${PORT}`);
});
