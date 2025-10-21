"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.executeBlenderScript = executeBlenderScript;
exports.exportToGLTF = exportToGLTF;
exports.generateBiomeTerrain = generateBiomeTerrain;
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
    const scriptPath = path_1.default.join(config_1.config.blenderScriptsDir, 'export_gltf.py');
    const command = `"${config_1.config.blenderPath}" "${blendFilePath}" --background --python "${scriptPath}" -- "${outputGlbPath}"`;
    console.log(`🔄 Exporting to GLTF: ${command}`);
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
        throw new Error(`GLTF export failed: ${error.message}`);
    }
}
/**
 * 바이옴 지형 생성
 */
async function generateBiomeTerrain(biomeLayout, outputBlendPath, tempDir) {
    // 1. 바이옴 레이아웃을 JSON 파일로 저장
    const biomeLayoutPath = path_1.default.join(tempDir, 'biome_layout.json');
    await (0, promises_1.writeFile)(biomeLayoutPath, JSON.stringify(biomeLayout, null, 2));
    // 2. Python 스크립트 실행 (biome_generator_wvd.py)
    const biomeGeneratorScript = path_1.default.join(config_1.config.blenderScriptsDir, 'biome_generator_wvd.py');
    const pythonCommand = `python "${biomeGeneratorScript}" "${biomeLayoutPath}" "${tempDir}"`;
    console.log(`🔄 Generating biome maps: ${pythonCommand}`);
    const { stdout: genStdout, stderr: genStderr } = await execAsync(pythonCommand);
    console.log('Biome Generator Output:', genStdout);
    if (genStderr)
        console.error('Biome Generator Errors:', genStderr);
    // 3. Blender에서 지형 생성 (biome_terrain_blender.py)
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
