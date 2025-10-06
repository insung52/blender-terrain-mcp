import Queue from 'bull';
import { prisma } from '../db/client';
import { executeBlenderScript } from '../services/blenderService';
import path from 'path';

export const blenderQueue = new Queue('blender-jobs', {
  redis: {
    host: 'localhost',
    port: 6379
  }
});

// Worker (Blender + DB 통합)
blenderQueue.process(2, async (job) => {
  const { dbJobId, type, params } = job.data;

  console.log(`[Worker] Processing job ${job.id}, DB Job ID: ${dbJobId}`);

  try {
    // 1. DB 상태 업데이트: processing
    await prisma.job.update({
      where: { id: dbJobId },
      data: { status: 'processing' }
    });

    // 2. Blender 실행
    const scriptPath = path.join(process.cwd(), 'src', 'blender-scripts', 'test.py');
    const outputPath = path.join(process.cwd(), 'output', `${dbJobId}.blend`);

    console.log(`[Worker] Executing Blender script...`);
    await executeBlenderScript(scriptPath, outputPath);

    // 3. DB 상태 업데이트: completed
    await prisma.job.update({
      where: { id: dbJobId },
      data: {
        status: 'completed',
        result: { blendFile: outputPath }
      }
    });

    console.log(`[Worker] Job ${job.id} completed successfully`);
    return { success: true, outputPath };

  } catch (error: any) {
    console.error(`[Worker] Job ${job.id} failed:`, error.message);

    // DB 상태 업데이트: failed
    await prisma.job.update({
      where: { id: dbJobId },
      data: { status: 'failed' }
    });

    throw error;
  }
});

// 에러 핸들링
blenderQueue.on('error', (error) => {
  console.error('[Queue] Error:', error);
});

blenderQueue.on('failed', (job, err) => {
  console.error(`[Queue] Job ${job.id} failed:`, err.message);
});

blenderQueue.on('completed', (job, result) => {
  console.log(`[Queue] Job ${job.id} completed:`, result);
});
