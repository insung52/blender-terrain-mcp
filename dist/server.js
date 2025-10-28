"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const blenderService_1 = require("./services/blenderService");
const client_1 = require("./db/client");
const blenderQueue_1 = require("./queue/blenderQueue");
const biomeService_1 = require("./services/biomeService");
const progressService_1 = require("./services/progressService");
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const app = (0, express_1.default)();
const PORT = 3000;
// Ensure output directory exists
const outputDir = path_1.default.join(process.cwd(), 'output');
if (!fs_1.default.existsSync(outputDir)) {
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    console.log('📁 Created output directory');
}
// Check API key on startup
console.log('🔑 ANTHROPIC_API_KEY:', process.env.ANTHROPIC_API_KEY
    ? `${process.env.ANTHROPIC_API_KEY.substring(0, 20)}... (${process.env.ANTHROPIC_API_KEY.length} chars)`
    : 'NOT SET');
// Middleware
app.use((0, cors_1.default)());
app.use(express_1.default.json());
app.use('/output', express_1.default.static(path_1.default.join(__dirname, '../output')));
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
    progressService_1.progressService.addConnection(jobId, res);
    // 현재 상태 즉시 전송
    const progress = progressService_1.progressService.getJobProgress(jobId);
    if (progress) {
        res.write(`data: ${JSON.stringify({
            type: 'connected',
            status: progress.status,
            currentStep: progress.currentStep,
            steps: progress.steps
        })}\n\n`);
    }
    else {
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
        const progress = progressService_1.progressService.getJobProgress(jobId);
        // 2. DB에서 job 정보 조회
        const job = await client_1.prisma.job.findUnique({
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
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Test Blender execution
app.get('/test-blender', async (req, res) => {
    try {
        const scriptPath = path_1.default.join(__dirname, 'blender-scripts', 'test.py');
        const outputPath = path_1.default.join(process.cwd(), 'output', 'test.blend');
        console.log('Executing Blender script...');
        const result = await (0, blenderService_1.executeBlenderScript)(scriptPath, outputPath);
        res.json({
            success: true,
            message: 'Blender executed successfully',
            outputPath,
            stdout: result.stdout.slice(-200) // Last 200 chars
        });
    }
    catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});
// Test Database
app.post('/test-db', async (req, res) => {
    try {
        const job = await client_1.prisma.job.create({
            data: {
                userId: 'test-user',
                type: 'terrain',
                status: 'queued',
                inputParams: { description: 'test terrain' }
            }
        });
        res.json({ success: true, job });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
app.get('/test-db/:jobId', async (req, res) => {
    try {
        const job = await client_1.prisma.job.findUnique({
            where: { id: req.params.jobId }
        });
        res.json({ success: true, job });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Test Queue
app.post('/test-queue', async (req, res) => {
    try {
        const job = await blenderQueue_1.blenderQueue.add({
            type: 'test',
            data: req.body
        });
        res.json({ success: true, jobId: job.id, status: 'queued' });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
app.get('/test-queue/:jobId', async (req, res) => {
    try {
        const job = await blenderQueue_1.blenderQueue.getJob(req.params.jobId);
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
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Full workflow test: API → DB → Queue → Blender → DB
app.post('/api/test-full', async (req, res) => {
    try {
        // 1. DB에 Job 생성
        const dbJob = await client_1.prisma.job.create({
            data: {
                userId: 'test-user',
                type: 'test',
                status: 'queued',
                inputParams: req.body || {}
            }
        });
        console.log(`[API] Created DB Job: ${dbJob.id}`);
        // 2. Queue에 Job 추가
        await blenderQueue_1.blenderQueue.add({
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
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Get job status (DB)
app.get('/api/job/:jobId', async (req, res) => {
    try {
        const job = await client_1.prisma.job.findUnique({
            where: { id: req.params.jobId },
            include: { terrain: true, road: true }
        });
        if (!job) {
            return res.status(404).json({ success: false, error: 'Job not found' });
        }
        res.json({ success: true, job });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Get job by terrain ID
app.get('/api/job/terrain/:terrainId', async (req, res) => {
    try {
        const job = await client_1.prisma.job.findFirst({
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
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Get job by road ID
app.get('/api/job/road/:roadId', async (req, res) => {
    try {
        const job = await client_1.prisma.job.findFirst({
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
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Get all completed terrains
app.get('/api/terrains', async (req, res) => {
    try {
        const terrains = await client_1.prisma.terrain.findMany({
            orderBy: { createdAt: 'desc' },
            take: 50 // 최근 50개
        });
        res.json({ success: true, terrains });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Get all roads
app.get('/api/roads', async (req, res) => {
    try {
        const roads = await client_1.prisma.road.findMany({
            include: { terrain: true },
            orderBy: { createdAt: 'desc' },
            take: 50
        });
        res.json({ success: true, roads });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Delete terrain
app.delete('/api/terrain/:terrainId', async (req, res) => {
    try {
        const { terrainId } = req.params;
        // Get terrain data first to delete files
        const terrain = await client_1.prisma.terrain.findUnique({
            where: { id: terrainId }
        });
        if (!terrain) {
            return res.status(404).json({ success: false, error: 'Terrain not found' });
        }
        // Delete related roads and their files
        const roads = await client_1.prisma.road.findMany({
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
                }
                catch (err) {
                    console.error(`Failed to delete road blend file: ${road.blendFilePath}`, err);
                }
            }
            if (road.previewPath) {
                try {
                    const fs = require('fs');
                    if (fs.existsSync(road.previewPath)) {
                        fs.unlinkSync(road.previewPath);
                    }
                }
                catch (err) {
                    console.error(`Failed to delete road preview: ${road.previewPath}`, err);
                }
            }
        }
        // Delete roads from DB
        await client_1.prisma.road.deleteMany({
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
            }
            catch (err) {
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
            }
            catch (err) {
                console.error(`Failed to delete terrain preview files: ${terrain.topViewPath}`, err);
            }
        }
        // Delete terrain from DB
        await client_1.prisma.terrain.delete({
            where: { id: terrainId }
        });
        res.json({ success: true, message: 'Terrain and files deleted' });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Delete road
app.delete('/api/road/:roadId', async (req, res) => {
    try {
        const { roadId } = req.params;
        // Get road data first to delete files
        const road = await client_1.prisma.road.findUnique({
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
            }
            catch (err) {
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
            }
            catch (err) {
                console.error(`Failed to delete road preview files: ${road.previewPath}`, err);
            }
        }
        // Delete road from DB
        await client_1.prisma.road.delete({
            where: { id: roadId }
        });
        res.json({ success: true, message: 'Road and files deleted' });
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Terrain 생성 API
app.post('/api/terrain', async (req, res) => {
    try {
        const { description, scale, roughness, size, terrain_scale, useAI, useBiome } = req.body;
        let finalParams = {
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
                const biomeLayout = await (0, biomeService_1.generateBiomeLayout)(description);
                console.log(`[API] ✅ Biome layout generated: ${biomeLayout.biome_points.length} biome points`);
                finalParams = {
                    ...finalParams,
                    useBiome: true,
                    biomeLayout: biomeLayout
                };
            }
            catch (error) {
                console.error(`[API] ❌ Biome generation FAILED:`, error.message);
                console.error(`[API] Full error:`, error);
                // Fallback: 기존 방식으로 진행
                finalParams.useBiome = false;
            }
        }
        else {
            console.log(`[API] Standard terrain mode - useAI: ${useAI}, description: ${!!description}, API key: ${!!process.env.ANTHROPIC_API_KEY}`);
        }
        // DB: Job 생성
        const dbJob = await client_1.prisma.job.create({
            data: {
                userId: 'test-user',
                type: 'terrain',
                status: 'queued',
                inputParams: { ...finalParams, useAI }
            }
        });
        console.log(`[API] Created terrain job: ${dbJob.id}`);
        // Terrain 레코드를 미리 생성 (status: processing)
        const terrain = await client_1.prisma.terrain.create({
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
            progressService_1.progressService.registerJob(dbJob.id, [
                'biome_analysis',
                'biome_maps',
                'terrain_generation',
                'preview_render'
            ]);
        }
        else {
            progressService_1.progressService.registerJob(dbJob.id, [
                'terrain_generation',
                'preview_render'
            ]);
        }
        // Queue: Job 추가
        await blenderQueue_1.blenderQueue.add({
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
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// Road 생성 API
app.post('/api/road', async (req, res) => {
    try {
        const { terrainId, controlPoints, width } = req.body;
        // Terrain 조회
        const terrain = await client_1.prisma.terrain.findUnique({
            where: { id: terrainId }
        });
        if (!terrain) {
            return res.status(404).json({ success: false, error: 'Terrain not found' });
        }
        // DB: Job 생성
        const dbJob = await client_1.prisma.job.create({
            data: {
                userId: 'test-user',
                type: 'road',
                status: 'queued',
                inputParams: { terrainId, controlPoints, width }
            }
        });
        console.log(`[API] Created road job: ${dbJob.id}`);
        // Queue: Job 추가
        await blenderQueue_1.blenderQueue.add({
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
    }
    catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});
// GLTF Export API
app.post('/api/terrain/:terrainId/export-gltf', async (req, res) => {
    try {
        const { terrainId } = req.params;
        // 1. Terrain 조회
        const terrain = await client_1.prisma.terrain.findUnique({
            where: { id: terrainId }
        });
        if (!terrain || !terrain.blendFilePath) {
            return res.status(404).json({ success: false, error: 'Terrain not found' });
        }
        // 2. 이미 GLTF 파일이 있는지 확인 (캐싱)
        const glbPath = terrain.blendFilePath.replace('.blend', '.glb');
        if (fs_1.default.existsSync(glbPath)) {
            console.log(`[API] GLTF file already exists (cached): ${glbPath}`);
            return res.json({ success: true, glbPath: glbPath, cached: true });
        }
        // 3. GLTF Export 실행
        console.log(`[API] Exporting terrain to GLTF: ${terrainId}`);
        const result = await (0, blenderService_1.exportToGLTF)(terrain.blendFilePath, glbPath);
        // 4. DB 업데이트 (metadata에 GLTF 경로 저장)
        await client_1.prisma.terrain.update({
            where: { id: terrainId },
            data: { metadata: { ...terrain.metadata, gltfPath: glbPath } }
        });
        console.log(`[API] ✅ GLTF export completed: ${glbPath}`);
        res.json({ success: true, glbPath: glbPath, cached: false });
    }
    catch (error) {
        console.error(`[API] ❌ GLTF export failed:`, error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});
// GLTF 파일 다운로드
app.get('/api/terrain/:terrainId/download-gltf', async (req, res) => {
    try {
        const { terrainId } = req.params;
        const terrain = await client_1.prisma.terrain.findUnique({ where: { id: terrainId } });
        if (!terrain) {
            return res.status(404).json({ error: 'Terrain not found' });
        }
        const glbPath = terrain.blendFilePath.replace('.blend', '.glb');
        if (!fs_1.default.existsSync(glbPath)) {
            return res.status(404).json({ error: 'GLTF file not found. Please export first.' });
        }
        console.log(`[API] Downloading GLTF: ${glbPath}`);
        res.download(glbPath, `terrain_${terrainId}.glb`);
    }
    catch (error) {
        console.error(`[API] ❌ GLTF download failed:`, error.message);
        res.status(500).json({ error: error.message });
    }
});
// Road GLTF Export API
app.post('/api/road/:roadId/export-gltf', async (req, res) => {
    try {
        const { roadId } = req.params;
        // 1. Road 조회
        const road = await client_1.prisma.road.findUnique({
            where: { id: roadId }
        });
        if (!road || !road.blendFilePath) {
            return res.status(404).json({ success: false, error: 'Road not found' });
        }
        // 2. 이미 GLTF 파일이 있는지 확인 (캐싱)
        const glbPath = road.blendFilePath.replace('.blend', '.glb');
        if (fs_1.default.existsSync(glbPath)) {
            console.log(`[API] GLTF file already exists (cached): ${glbPath}`);
            return res.json({ success: true, glbPath: glbPath, cached: true });
        }
        // 3. GLTF Export 실행
        console.log(`[API] Exporting road to GLTF: ${roadId}`);
        const result = await (0, blenderService_1.exportToGLTF)(road.blendFilePath, glbPath);
        console.log(`[API] ✅ GLTF export completed: ${glbPath}`);
        res.json({ success: true, glbPath: glbPath, cached: false });
    }
    catch (error) {
        console.error(`[API] ❌ GLTF export failed:`, error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});
// Road GLTF 파일 다운로드
app.get('/api/road/:roadId/download-gltf', async (req, res) => {
    try {
        const { roadId } = req.params;
        const road = await client_1.prisma.road.findUnique({ where: { id: roadId } });
        if (!road) {
            return res.status(404).json({ error: 'Road not found' });
        }
        const glbPath = road.blendFilePath.replace('.blend', '.glb');
        if (!fs_1.default.existsSync(glbPath)) {
            return res.status(404).json({ error: 'GLTF file not found. Please export first.' });
        }
        console.log(`[API] Downloading Road GLTF: ${glbPath}`);
        res.download(glbPath, `road_${roadId}.glb`);
    }
    catch (error) {
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
        const terrain = await client_1.prisma.terrain.findUnique({
            where: { id: terrainId }
        });
        if (!terrain) {
            return res.status(404).json({ success: false, error: 'Terrain not found' });
        }
        // 2. Road 조회 (optional)
        let baseBlendPath = terrain.blendFilePath;
        if (roadId) {
            const road = await client_1.prisma.road.findUnique({
                where: { id: roadId }
            });
            if (road) {
                baseBlendPath = road.blendFilePath;
            }
        }
        // 3. Biome maps 경로 찾기
        const terrainPreviewPath = terrain.topViewPath;
        const previewBasename = path_1.default.basename(terrainPreviewPath, '_preview.png');
        const biomeMapsDir = path_1.default.join(path_1.default.dirname(terrainPreviewPath), `biome_${previewBasename}`, 'biome_maps');
        if (!fs_1.default.existsSync(biomeMapsDir)) {
            return res.status(404).json({ success: false, error: 'Biome maps not found' });
        }
        // 4. 출력 경로 생성
        const objectsId = `objects_${Date.now()}`;
        const outputBlendPath = path_1.default.join(outputDir, `${objectsId}.blend`);
        const assetsDir = path_1.default.join(process.cwd(), 'assets');
        // 5. Job 생성
        const dbJob = await client_1.prisma.job.create({
            data: {
                userId,
                type: 'objects',
                status: 'queued',
                inputParams: { terrainId, roadId, objectCount, baseBlendPath, biomeMapsDir, assetsDir, outputBlendPath }
            }
        });
        console.log(`[API] Created objects job: ${dbJob.id}`);
        // 6. Objects 레코드를 미리 생성 (status: processing)
        const objects = await client_1.prisma.objects.create({
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
        progressService_1.progressService.registerJob(dbJob.id, ['object_placement']);
        // 8. 백그라운드 작업 시작 (비동기)
        (async () => {
            try {
                progressService_1.progressService.updateJobStatus(dbJob.id, 'processing');
                progressService_1.progressService.startStep(dbJob.id, 'object_placement', 'Starting object placement...');
                console.log(`[Background] Placing objects...`);
                console.log(`  - Base blend: ${baseBlendPath}`);
                console.log(`  - Output blend: ${outputBlendPath}`);
                console.log(`  - Biome maps: ${biomeMapsDir}`);
                const { placeObjectsOnTerrain } = await Promise.resolve().then(() => __importStar(require('./services/blenderService')));
                const result = await placeObjectsOnTerrain(baseBlendPath, biomeMapsDir, assetsDir, objectCount, outputBlendPath, '', // 프리뷰 없음
                (current, total, eta) => {
                    // Progress 업데이트
                    const progress = (current / total) * 100;
                    const etaMin = Math.floor(eta / 60);
                    const etaSec = Math.floor(eta % 60);
                    progressService_1.progressService.updateStepProgress(dbJob.id, 'object_placement', progress, `Placed ${current}/${total} objects (ETA: ${etaMin}m ${etaSec}s)`);
                });
                console.log(`[Background] ✅ Objects placed: ${result.placedCount}/${objectCount}`);
                // Objects 레코드 업데이트 (먼저 수행)
                await client_1.prisma.objects.update({
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
                await client_1.prisma.job.update({
                    where: { id: dbJob.id },
                    data: { status: 'completed', result: { objectCount: result.placedCount } }
                });
                // Progress 완료 (DB 업데이트 후에 SSE 전송)
                progressService_1.progressService.completeStep(dbJob.id, 'object_placement', `Placed ${result.placedCount} objects`);
                progressService_1.progressService.completeJob(dbJob.id, { objectCount: result.placedCount });
            }
            catch (error) {
                console.error(`[Background] ❌ Objects creation failed:`, error.message);
                // Progress 실패 처리
                progressService_1.progressService.failJob(dbJob.id, error.message);
                // Job 실패
                await client_1.prisma.job.update({
                    where: { id: dbJob.id },
                    data: { status: 'failed' }
                });
                // Objects 레코드 업데이트 (실패 상태)
                await client_1.prisma.objects.update({
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
    }
    catch (error) {
        console.error(`[API] ❌ Objects creation failed:`, error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});
// GET /api/objects - 오브젝트 목록 조회
app.get('/api/objects', async (req, res) => {
    try {
        const { userId = 'test-user' } = req.query;
        const objects = await client_1.prisma.objects.findMany({
            where: { userId: userId },
            include: {
                terrain: { select: { id: true, description: true } },
                road: { select: { id: true } }
            },
            orderBy: { createdAt: 'desc' }
        });
        res.json({ success: true, objects });
    }
    catch (error) {
        console.error(`[API] ❌ Failed to fetch objects:`, error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});
// GET /api/objects/:id/download - GLB 다운로드
app.get('/api/objects/:id/download', async (req, res) => {
    try {
        const { id } = req.params;
        console.log(`[API] Exporting objects to GLTF: ${id}`);
        const objects = await client_1.prisma.objects.findUnique({
            where: { id }
        });
        if (!objects || !objects.blendFilePath) {
            return res.status(404).json({ success: false, error: 'Objects not found' });
        }
        // GLB 파일이 없으면 생성
        let glbPath = objects.glbFilePath;
        if (!glbPath || !fs_1.default.existsSync(glbPath)) {
            glbPath = objects.blendFilePath.replace('.blend', '.glb');
            const { exportToGLTF } = await Promise.resolve().then(() => __importStar(require('./services/blenderService')));
            await exportToGLTF(objects.blendFilePath, glbPath);
            // DB 업데이트
            await client_1.prisma.objects.update({
                where: { id },
                data: { glbFilePath: glbPath }
            });
        }
        console.log(`[API] ✅ GLB ready: ${glbPath}`);
        res.download(glbPath);
    }
    catch (error) {
        console.error(`[API] ❌ GLTF export failed:`, error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});
// GET /api/objects/:id/download-blend - Blend 파일 다운로드
app.get('/api/objects/:id/download-blend', async (req, res) => {
    try {
        const { id } = req.params;
        console.log(`[API] Downloading blend file for objects: ${id}`);
        const objects = await client_1.prisma.objects.findUnique({
            where: { id }
        });
        if (!objects || !objects.blendFilePath) {
            return res.status(404).json({ success: false, error: 'Objects not found' });
        }
        if (!fs_1.default.existsSync(objects.blendFilePath)) {
            return res.status(404).json({ success: false, error: 'Blend file not found' });
        }
        console.log(`[API] ✅ Blend file ready: ${objects.blendFilePath}`);
        res.download(objects.blendFilePath);
    }
    catch (error) {
        console.error(`[API] ❌ Blend download failed:`, error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});
// DELETE /api/objects/:id - 오브젝트 삭제
app.delete('/api/objects/:id', async (req, res) => {
    try {
        const { id } = req.params;
        const objects = await client_1.prisma.objects.findUnique({
            where: { id }
        });
        if (!objects) {
            return res.status(404).json({ success: false, error: 'Objects not found' });
        }
        // 파일 삭제
        if (fs_1.default.existsSync(objects.blendFilePath)) {
            fs_1.default.unlinkSync(objects.blendFilePath);
        }
        if (fs_1.default.existsSync(objects.previewPath)) {
            fs_1.default.unlinkSync(objects.previewPath);
        }
        if (objects.glbFilePath && fs_1.default.existsSync(objects.glbFilePath)) {
            fs_1.default.unlinkSync(objects.glbFilePath);
        }
        // DB 삭제
        await client_1.prisma.objects.delete({
            where: { id }
        });
        res.json({ success: true });
    }
    catch (error) {
        console.error(`[API] ❌ Failed to delete objects:`, error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});
// Serve static files from React app (프로덕션 모드)
app.use(express_1.default.static(path_1.default.join(__dirname, '../client/dist')));
// All remaining requests return the React app (프론트엔드 라우팅 지원)
app.get('*', (req, res) => {
    res.sendFile(path_1.default.join(__dirname, '../client/dist/index.html'));
});
// Start server
app.listen(PORT, () => {
    console.log(`✅ Server running on http://localhost:${PORT}`);
});
