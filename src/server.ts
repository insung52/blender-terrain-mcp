import express from 'express';
import { executeBlenderScript } from './services/blenderService';
import { prisma } from './db/client';
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

// Start server
app.listen(PORT, () => {
  console.log(`✅ Server running on http://localhost:${PORT}`);
});
