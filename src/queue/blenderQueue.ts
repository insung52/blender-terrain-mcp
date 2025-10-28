import Queue from 'bull';
import { prisma } from '../db/client';
import { executeBlenderScript, generateBiomeTerrain } from '../services/blenderService';
import { progressService } from '../services/progressService';
import path from 'path';
import fs from 'fs';

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

    // Progress 업데이트
    progressService.updateJobStatus(dbJobId, 'processing');

    // 2. Job 타입별 처리
    if (type === 'terrain') {
      const outputPath = path.join(process.cwd(), 'output', `${dbJobId}.blend`);
      const previewPath = path.join(process.cwd(), 'output', `${dbJobId}_preview.png`);

      // **바이옴 모드** vs 일반 모드
      if (params.useBiome && params.biomeLayout) {
        console.log(`[Worker] 🌍 BIOME TERRAIN MODE`);
        console.log(`[Worker] Biome points: ${params.biomeLayout.biome_points.length}`);

        // 바이옴 분석 완료 (이미 API 단계에서 완료됨)
        progressService.completeStep(dbJobId, 'biome_analysis', 'Biome layout analyzed');

        // 바이옴 맵 생성 시작
        progressService.startStep(dbJobId, 'biome_maps', 'Generating biome maps...');

        // 임시 디렉토리 생성
        const tempDir = path.join(process.cwd(), 'output', `biome_${dbJobId}`);
        if (!fs.existsSync(tempDir)) {
          fs.mkdirSync(tempDir, { recursive: true });
        }

        // 바이옴 지형 생성 (with progress callback)
        const result = await generateBiomeTerrain(
          params.biomeLayout,
          outputPath,
          tempDir,
          (message: string) => {
            // 중간 진행 상태 업데이트
            if (message.includes('generated')) {
              progressService.completeStep(dbJobId, 'biome_maps', message);
              progressService.startStep(dbJobId, 'terrain_generation', 'Generating 3D terrain...');
            } else if (message.includes('mesh created')) {
              progressService.completeStep(dbJobId, 'terrain_generation', message);
              progressService.startStep(dbJobId, 'preview_render', 'Rendering preview...');
            } else if (message.includes('Generating biome maps')) {
              progressService.updateStepProgress(dbJobId, 'biome_maps', 50, message);
            } else if (message.includes('Creating 3D terrain')) {
              progressService.updateStepProgress(dbJobId, 'terrain_generation', 50, message);
            }
          }
        );

        console.log(`[Worker] Biome terrain generated`);
        console.log(`[Worker] Image maps: ${result.imagePaths.length}`);

        // 프리뷰 렌더링 완료
        progressService.completeStep(dbJobId, 'preview_render', 'Preview rendered');

      } else {
        console.log(`[Worker] Standard terrain mode`);

        // 지형 생성 시작
        progressService.startStep(dbJobId, 'terrain_generation', 'Generating terrain...');

        // 기존 v2 스크립트 사용
        const scriptPath = path.join(process.cwd(), 'src', 'blender-scripts', 'terrain_generator_v2.py');
        const paramsFilePath = path.join(process.cwd(), 'output', `${dbJobId}_params.json`);
        fs.writeFileSync(paramsFilePath, JSON.stringify(params));

        console.log(`[Worker] Creating terrain with params: ${JSON.stringify(params)}`);

        const { exec } = require('child_process');
        const { promisify } = require('util');
        const execAsync = promisify(exec);
        const { config } = require('../config');

        const command = `"${config.blenderPath}" --background --python "${scriptPath}" -- "${paramsFilePath}" "${outputPath}" "${previewPath}"`;

        console.log(`[Worker] Executing Blender...`);
        const result = await execAsync(command, {
          maxBuffer: 10 * 1024 * 1024,
          encoding: 'utf8',
          windowsHide: true,
          env: { ...process.env }
        });

        try { fs.unlinkSync(paramsFilePath); } catch (e) {}

        console.log(`[Worker] Blender execution completed`);
        if (result.stderr && result.stderr.includes('Error')) {
          console.error(`[Worker] Blender stderr:`, result.stderr);
        }

        // 지형 생성 완료
        progressService.completeStep(dbJobId, 'terrain_generation', 'Terrain created');

        // 프리뷰 렌더링
        progressService.startStep(dbJobId, 'preview_render', 'Rendering preview...');
        progressService.completeStep(dbJobId, 'preview_render', 'Preview rendered');
      }

      // Terrain DB 레코드 업데이트 (이미 API 단계에서 생성됨)
      await prisma.terrain.updateMany({
        where: { jobId: dbJobId },
        data: {
          blendFilePath: outputPath,
          topViewPath: previewPath,
          metadata: { ...params, status: 'completed' }
        }
      });

      // Job 완료
      await prisma.job.update({
        where: { id: dbJobId },
        data: {
          status: 'completed',
          result: { blendFile: outputPath, preview: previewPath }
        }
      });

      // Progress 완료
      progressService.completeJob(dbJobId, { blendFile: outputPath, preview: previewPath });

      console.log(`[Worker] Terrain created: ${outputPath}`);
      return { success: true, outputPath, previewPath };

    } else if (type === 'road') {
      // Road 생성 (logged version for debugging)
      const scriptPath = path.join(process.cwd(), 'src', 'blender-scripts', 'road_generator_logged.py');
      const terrainBlendPath = params.terrainBlendPath;
      const outputPath = path.join(process.cwd(), 'output', `${dbJobId}.blend`);
      const previewPath = path.join(process.cwd(), 'output', `${dbJobId}_preview.png`);

      // 파라미터 파일 생성
      const fs = require('fs');
      const paramsFilePath = path.join(process.cwd(), 'output', `${dbJobId}_params.json`);
      fs.writeFileSync(paramsFilePath, JSON.stringify(params));

      console.log(`[Worker] Creating road with ${params.controlPoints.length} points`);

      // Blender 실행
      const { exec } = require('child_process');
      const { promisify } = require('util');
      const execAsync = promisify(exec);
      const { config } = require('../config');

      const command = `"${config.blenderPath}" --background --python "${scriptPath}" -- "${paramsFilePath}" "${terrainBlendPath}" "${outputPath}" "${previewPath}"`;

      console.log(`[Worker] Executing Blender for road...`);
      const result = await execAsync(command, {
        maxBuffer: 10 * 1024 * 1024,
        encoding: 'utf8',
        windowsHide: true,
        env: { ...process.env }
      });

      // 임시 파일 삭제
      try { fs.unlinkSync(paramsFilePath); } catch (e) {}

      console.log(`[Worker] Road execution completed`);
      if (result.stderr && result.stderr.includes('Error')) {
        console.error(`[Worker] Blender stderr:`, result.stderr);
      }

      // Road DB 레코드 생성
      await prisma.road.create({
        data: {
          jobId: dbJobId,
          terrainId: params.terrainId,
          userId: 'test-user',
          controlPoints: params.controlPoints,
          blendFilePath: outputPath,
          previewPath: previewPath,
          widthMeters: params.width,
          metadata: params
        }
      });

      // Job 완료
      await prisma.job.update({
        where: { id: dbJobId },
        data: {
          status: 'completed',
          result: { blendFile: outputPath, preview: previewPath }
        }
      });

      console.log(`[Worker] Road created: ${outputPath}`);
      return { success: true, outputPath, previewPath };

    } else {
      // 기본 테스트 (기존 코드)
      const scriptPath = path.join(process.cwd(), 'src', 'blender-scripts', 'test.py');
      const outputPath = path.join(process.cwd(), 'output', `${dbJobId}.blend`);

      console.log(`[Worker] Executing Blender script...`);
      await executeBlenderScript(scriptPath, outputPath);

      await prisma.job.update({
        where: { id: dbJobId },
        data: {
          status: 'completed',
          result: { blendFile: outputPath }
        }
      });

      console.log(`[Worker] Job ${job.id} completed successfully`);
      return { success: true, outputPath };
    }

  } catch (error: any) {
    console.error(`[Worker] Job ${job.id} failed:`, error.message);

    // DB 상태 업데이트: failed
    await prisma.job.update({
      where: { id: dbJobId },
      data: { status: 'failed' }
    });

    // Progress 실패 처리
    progressService.failJob(dbJobId, error.message);

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
