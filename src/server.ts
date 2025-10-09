import express from 'express';
import cors from 'cors';
import { executeBlenderScript } from './services/blenderService';
import { prisma } from './db/client';
import { blenderQueue } from './queue/blenderQueue';
import { analyzeTerrainDescription } from './services/claudeService';
import path from 'path';

const app = express();
const PORT = 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use('/output', express.static(path.join(__dirname, '../output')));

// Health check
app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Blender Terrain MCP Server',
    version: '1.0.0'
  });
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

    // Delete related roads first
    await prisma.road.deleteMany({
      where: { terrainId }
    });

    // Delete terrain
    await prisma.terrain.delete({
      where: { id: terrainId }
    });

    res.json({ success: true, message: 'Terrain deleted' });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Delete road
app.delete('/api/road/:roadId', async (req, res) => {
  try {
    const { roadId } = req.params;

    // Delete road
    await prisma.road.delete({
      where: { id: roadId }
    });

    res.json({ success: true, message: 'Road deleted' });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Terrain 생성 API
app.post('/api/terrain', async (req, res) => {
  try {
    const { description, scale, roughness, size, terrain_scale, useAI } = req.body;

    let finalParams = {
      scale: scale || 15,
      roughness: roughness || 0.7,
      terrain_scale: terrain_scale || 10,  // 지형 스케일 배율 (기본 10배)
      description: description || ''
    };

    // Claude AI 분석 사용 (useAI가 true이고 description이 있을 때)
    if (useAI && description && process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY !== 'your-api-key-here') {
      console.log(`[API] Analyzing terrain with Claude: "${description}"`);
      try {
        const aiParams = await analyzeTerrainDescription(description);
        // v2.0: Claude의 모든 파라미터를 finalParams에 병합
        finalParams = {
          ...finalParams,
          ...aiParams  // 모든 v2 파라미터 포함
        };
        console.log(`[API] Claude analysis result:`, aiParams);
      } catch (error: any) {
        console.error(`[API] Claude analysis failed, using defaults:`, error.message);
      }
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

    // Queue: Job 추가
    await blenderQueue.add({
      dbJobId: dbJob.id,
      type: 'terrain',
      params: finalParams
    });

    res.json({
      success: true,
      jobId: dbJob.id,
      status: 'queued',
      message: 'Terrain generation started'
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

// Start server
app.listen(PORT, () => {
  console.log(`✅ Server running on http://localhost:${PORT}`);
});
