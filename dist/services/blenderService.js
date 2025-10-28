"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.executeBlenderScript = executeBlenderScript;
exports.exportToGLTF = exportToGLTF;
exports.generateBiomeTerrain = generateBiomeTerrain;
exports.placeObjectsOnTerrain = placeObjectsOnTerrain;
const child_process_1 = require("child_process");
const util_1 = require("util");
const promises_1 = require("fs/promises");
const path_1 = __importDefault(require("path"));
const config_1 = require("../config");
const execAsync = (0, util_1.promisify)(child_process_1.exec);
async function executeBlenderScript(scriptPath, outputPath) {
    const command = `"${config_1.config.blenderPath}" --background --python "${scriptPath}" -- "${outputPath}"`;
    try {
        const result = await execAsync(command);
        return result;
    }
    catch (error) {
        throw new Error(`Blender execution failed: ${error.message}`);
    }
}
/**
 * .blend 파일을 .glb (GLTF Binary)로 변환
 */
async function exportToGLTF(blendFilePath, outputGlbPath) {
    const fs = require('fs');
    const scriptPath = path_1.default.join(config_1.config.blenderScriptsDir, 'export_gltf_simple.py');
    const command = `"${config_1.config.blenderPath}" "${blendFilePath}" --background --python "${scriptPath}" -- "${outputGlbPath}"`;
    console.log(`🔄 Exporting to GLTF (simple): ${command}`);
    try {
        const { stdout, stderr } = await execAsync(command, {
            maxBuffer: 10 * 1024 * 1024,
            timeout: 180000 // 3분 타임아웃 (Baking 시간 고려)
        });
        console.log('GLTF Export Output:', stdout);
        if (stderr)
            console.error('GLTF Export Errors:', stderr);
        return { success: true, glbPath: outputGlbPath };
    }
    catch (error) {
        // Blender가 경고(WARNING) 때문에 non-zero exit code를 반환할 수 있음
        // 실제로 GLB 파일이 생성되었는지 확인
        if (fs.existsSync(outputGlbPath)) {
            const stats = fs.statSync(outputGlbPath);
            if (stats.size > 0) {
                console.log(`✅ GLB file exists (${(stats.size / 1024 / 1024).toFixed(2)} MB), treating as success despite warnings`);
                console.log('Warning message:', error.message);
                return { success: true, glbPath: outputGlbPath };
            }
        }
        // 파일이 없거나 크기가 0이면 진짜 에러
        throw new Error(`GLTF export failed: ${error.message}`);
    }
}
/**
 * 바이옴 지형 생성
 */
async function generateBiomeTerrain(biomeLayout, outputBlendPath, tempDir, onProgress) {
    // 1. 바이옴 레이아웃을 JSON 파일로 저장
    const biomeLayoutPath = path_1.default.join(tempDir, 'biome_layout.json');
    await (0, promises_1.writeFile)(biomeLayoutPath, JSON.stringify(biomeLayout, null, 2));
    // 2. Python 스크립트 실행 (biome_generator_wvd.py)
    if (onProgress)
        onProgress('Generating biome maps...');
    const biomeGeneratorScript = path_1.default.join(config_1.config.blenderScriptsDir, 'biome_generator_wvd.py');
    const pythonCommand = `python "${biomeGeneratorScript}" "${biomeLayoutPath}" "${tempDir}"`;
    console.log(`🔄 Generating biome maps: ${pythonCommand}`);
    const { stdout: genStdout, stderr: genStderr } = await execAsync(pythonCommand);
    console.log('Biome Generator Output:', genStdout);
    if (genStderr)
        console.error('Biome Generator Errors:', genStderr);
    if (onProgress)
        onProgress('Biome maps generated');
    // 3. Blender에서 지형 생성 (biome_terrain_blender.py)
    if (onProgress)
        onProgress('Creating 3D terrain mesh...');
    const biomeBlenderScript = path_1.default.join(config_1.config.blenderScriptsDir, 'biome_terrain_blender.py');
    const imageDir = path_1.default.join(tempDir, 'biome_maps');
    const paramsFile = path_1.default.join(tempDir, 'terrain_params.json');
    const previewPath = outputBlendPath.replace('.blend', '_preview.png');
    const blenderCommand = `"${config_1.config.blenderPath}" --background --python "${biomeBlenderScript}" -- "${imageDir}" "${paramsFile}" "${outputBlendPath}" "${previewPath}"`;
    console.log(`🔄 Generating terrain in Blender: ${blenderCommand}`);
    // maxBuffer 증가 및 타임아웃 설정
    const { stdout: blenderStdout, stderr: blenderStderr } = await execAsync(blenderCommand, {
        maxBuffer: 10 * 1024 * 1024, // 10MB
        timeout: 5 * 60 * 1000, // 5분
    });
    console.log('Blender Output:', blenderStdout);
    if (blenderStderr)
        console.error('Blender Errors:', blenderStderr);
    if (onProgress)
        onProgress('Terrain mesh created');
    // Blender 프로세스 종료 후 파일 시스템 flush 대기
    await new Promise(resolve => setTimeout(resolve, 2000));
    console.log('Waited 2 seconds for file system to flush');
    // 4. 생성된 이미지 경로 리스트
    const paramNames = [
        'temperature', 'humidity', 'erosion', 'continentalness', 'weirdness',
        'vegetation_color_r', 'vegetation_color_g', 'vegetation_color_b',
        'ground_color_r', 'ground_color_g', 'ground_color_b',
        'snow_start_height', 'rock_exposure'
    ];
    const imagePaths = paramNames.map(name => path_1.default.join(imageDir, `biome_${name}.png`));
    return {
        stdout: genStdout + '\n' + blenderStdout,
        stderr: genStderr + '\n' + blenderStderr,
        imagePaths
    };
}
/**
 * 지형에 오브젝트 배치 (나무 등) - 독립 blend 파일 생성
 */
async function placeObjectsOnTerrain(baseBlendPath, // terrain 또는 road blend 파일
biomeMapsDir, assetsDir, objectCount, outputBlendPath, // 새로운 독립 blend 파일
previewPath, onProgress) {
    const scriptPath = path_1.default.join(config_1.config.blenderScriptsDir, 'object_placer.py');
    const logPath = outputBlendPath.replace('.blend', '_log.txt');
    const command = `"${config_1.config.blenderPath}" "${baseBlendPath}" --background --python "${scriptPath}" -- "${biomeMapsDir}" "${assetsDir}" ${objectCount} "${outputBlendPath}" "${previewPath}"`;
    console.log(`🔄 Placing objects on terrain: ${command}`);
    const fs = require('fs');
    const { spawn } = require('child_process');
    return new Promise((resolve, reject) => {
        // Blender 프로세스를 spawn으로 실행
        const blenderProcess = spawn(config_1.config.blenderPath, [
            baseBlendPath,
            '--background',
            '--python',
            scriptPath,
            '--',
            biomeMapsDir,
            assetsDir,
            objectCount.toString(),
            outputBlendPath,
            previewPath
        ], {
            windowsHide: true
        });
        let lastReadPosition = 0;
        let lastPlacedCount = 0;
        // 로그 파일을 주기적으로 읽기
        const logCheckInterval = setInterval(() => {
            if (fs.existsSync(logPath)) {
                try {
                    const stats = fs.statSync(logPath);
                    if (stats.size > lastReadPosition) {
                        const stream = fs.createReadStream(logPath, {
                            start: lastReadPosition,
                            encoding: 'utf8'
                        });
                        let buffer = '';
                        stream.on('data', (chunk) => {
                            buffer += chunk;
                            const lines = buffer.split('\n');
                            buffer = lines.pop() || ''; // 마지막 불완전한 줄 보관
                            for (const line of lines) {
                                // [PROGRESS] 파싱: 50/100 | elapsed=25.3s | eta=25.7s
                                const match = line.match(/\[PROGRESS\] (\d+)\/(\d+) \| elapsed=([\d.]+)s \| eta=([\d.]+)s/);
                                if (match) {
                                    const current = parseInt(match[1]);
                                    const total = parseInt(match[2]);
                                    const eta = parseFloat(match[4]);
                                    if (current > lastPlacedCount) {
                                        lastPlacedCount = current;
                                        if (onProgress) {
                                            onProgress(current, total, eta);
                                        }
                                        console.log(`[Object Placer] Progress: ${current}/${total} (ETA: ${eta.toFixed(1)}s)`);
                                    }
                                }
                            }
                        });
                        stream.on('end', () => {
                            lastReadPosition = stats.size;
                        });
                    }
                }
                catch (err) {
                    // 로그 파일 읽기 실패 무시
                }
            }
        }, 1000); // 1초마다 체크
        let stdout = '';
        let stderr = '';
        blenderProcess.stdout.on('data', (data) => {
            stdout += data.toString();
        });
        blenderProcess.stderr.on('data', (data) => {
            stderr += data.toString();
        });
        blenderProcess.on('close', (code) => {
            clearInterval(logCheckInterval);
            if (code === 0) {
                console.log('Object Placer Output:', stdout);
                if (stderr)
                    console.error('Object Placer Errors:', stderr);
                // stdout에서 배치된 오브젝트 개수 추출
                const match = stdout.match(/Placement complete: (\d+)\/\d+ objects placed/);
                const placedCount = match ? parseInt(match[1]) : lastPlacedCount;
                resolve({ success: true, placedCount });
            }
            else {
                reject(new Error(`Object placement failed with code ${code}: ${stderr}`));
            }
        });
        blenderProcess.on('error', (err) => {
            clearInterval(logCheckInterval);
            reject(new Error(`Failed to start Blender: ${err.message}`));
        });
    });
}
