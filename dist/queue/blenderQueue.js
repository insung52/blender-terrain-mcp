"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.blenderQueue = void 0;
const bull_1 = __importDefault(require("bull"));
const client_1 = require("../db/client");
const blenderService_1 = require("../services/blenderService");
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
exports.blenderQueue = new bull_1.default('blender-jobs', {
    redis: {
        host: 'localhost',
        port: 6379
    }
});
// Worker (Blender + DB 통합)
exports.blenderQueue.process(2, async (job) => {
    const { dbJobId, type, params } = job.data;
    console.log(`[Worker] Processing job ${job.id}, DB Job ID: ${dbJobId}`);
    try {
        // 1. DB 상태 업데이트: processing
        await client_1.prisma.job.update({
            where: { id: dbJobId },
            data: { status: 'processing' }
        });
        // 2. Job 타입별 처리
        if (type === 'terrain') {
            const outputPath = path_1.default.join(process.cwd(), 'output', `${dbJobId}.blend`);
            const previewPath = path_1.default.join(process.cwd(), 'output', `${dbJobId}_preview.png`);
            // **바이옴 모드** vs 일반 모드
            if (params.useBiome && params.biomeLayout) {
                console.log(`[Worker] 🌍 BIOME TERRAIN MODE`);
                console.log(`[Worker] Biome points: ${params.biomeLayout.biome_points.length}`);
                // 임시 디렉토리 생성
                const tempDir = path_1.default.join(process.cwd(), 'output', `biome_${dbJobId}`);
                if (!fs_1.default.existsSync(tempDir)) {
                    fs_1.default.mkdirSync(tempDir, { recursive: true });
                }
                // 바이옴 지형 생성
                const result = await (0, blenderService_1.generateBiomeTerrain)(params.biomeLayout, outputPath, tempDir);
                console.log(`[Worker] Biome terrain generated`);
                console.log(`[Worker] Image maps: ${result.imagePaths.length}`);
                // Preview 이미지는 biome_terrain_blender.py에서 이미 생성됨
                console.log(`[Worker] Preview image created by Blender script`);
            }
            else {
                console.log(`[Worker] Standard terrain mode`);
                // 기존 v2 스크립트 사용
                const scriptPath = path_1.default.join(process.cwd(), 'src', 'blender-scripts', 'terrain_generator_v2.py');
                const paramsFilePath = path_1.default.join(process.cwd(), 'output', `${dbJobId}_params.json`);
                fs_1.default.writeFileSync(paramsFilePath, JSON.stringify(params));
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
                try {
                    fs_1.default.unlinkSync(paramsFilePath);
                }
                catch (e) { }
                console.log(`[Worker] Blender execution completed`);
                if (result.stderr && result.stderr.includes('Error')) {
                    console.error(`[Worker] Blender stderr:`, result.stderr);
                }
            }
            // Terrain DB 레코드 생성
            await client_1.prisma.terrain.create({
                data: {
                    jobId: dbJobId,
                    userId: 'test-user',
                    description: params.description || null,
                    blendFilePath: outputPath,
                    topViewPath: previewPath,
                    metadata: params
                }
            });
            // Job 완료
            await client_1.prisma.job.update({
                where: { id: dbJobId },
                data: {
                    status: 'completed',
                    result: { blendFile: outputPath, preview: previewPath }
                }
            });
            console.log(`[Worker] Terrain created: ${outputPath}`);
            return { success: true, outputPath, previewPath };
        }
        else if (type === 'road') {
            // Road 생성 (logged version for debugging)
            const scriptPath = path_1.default.join(process.cwd(), 'src', 'blender-scripts', 'road_generator_logged.py');
            const terrainBlendPath = params.terrainBlendPath;
            const outputPath = path_1.default.join(process.cwd(), 'output', `${dbJobId}.blend`);
            const previewPath = path_1.default.join(process.cwd(), 'output', `${dbJobId}_preview.png`);
            // 파라미터 파일 생성
            const fs = require('fs');
            const paramsFilePath = path_1.default.join(process.cwd(), 'output', `${dbJobId}_params.json`);
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
            try {
                fs.unlinkSync(paramsFilePath);
            }
            catch (e) { }
            console.log(`[Worker] Road execution completed`);
            if (result.stderr && result.stderr.includes('Error')) {
                console.error(`[Worker] Blender stderr:`, result.stderr);
            }
            // Road DB 레코드 생성
            await client_1.prisma.road.create({
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
            await client_1.prisma.job.update({
                where: { id: dbJobId },
                data: {
                    status: 'completed',
                    result: { blendFile: outputPath, preview: previewPath }
                }
            });
            console.log(`[Worker] Road created: ${outputPath}`);
            return { success: true, outputPath, previewPath };
        }
        else {
            // 기본 테스트 (기존 코드)
            const scriptPath = path_1.default.join(process.cwd(), 'src', 'blender-scripts', 'test.py');
            const outputPath = path_1.default.join(process.cwd(), 'output', `${dbJobId}.blend`);
            console.log(`[Worker] Executing Blender script...`);
            await (0, blenderService_1.executeBlenderScript)(scriptPath, outputPath);
            await client_1.prisma.job.update({
                where: { id: dbJobId },
                data: {
                    status: 'completed',
                    result: { blendFile: outputPath }
                }
            });
            console.log(`[Worker] Job ${job.id} completed successfully`);
            return { success: true, outputPath };
        }
    }
    catch (error) {
        console.error(`[Worker] Job ${job.id} failed:`, error.message);
        // DB 상태 업데이트: failed
        await client_1.prisma.job.update({
            where: { id: dbJobId },
            data: { status: 'failed' }
        });
        throw error;
    }
});
// 에러 핸들링
exports.blenderQueue.on('error', (error) => {
    console.error('[Queue] Error:', error);
});
exports.blenderQueue.on('failed', (job, err) => {
    console.error(`[Queue] Job ${job.id} failed:`, err.message);
});
exports.blenderQueue.on('completed', (job, result) => {
    console.log(`[Queue] Job ${job.id} completed:`, result);
});
