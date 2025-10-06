import express from 'express';
import { executeBlenderScript } from './services/blenderService';
import { prisma } from './db/client';
import { blenderQueue } from './queue/blenderQueue';
import path from 'path';

const app = express();
const PORT = 3000;

// Middleware
app.use(express.json());

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
      where: { id: req.params.jobId }
    });

    if (!job) {
      return res.status(404).json({ success: false, error: 'Job not found' });
    }

    res.json({ success: true, job });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`✅ Server running on http://localhost:${PORT}`);
});
