import { exec } from 'child_process';
import { promisify } from 'util';
import { writeFile } from 'fs/promises';
import path from 'path';
import { config } from '../config';
import { BiomeLayout } from '../types/biome';

const execAsync = promisify(exec);

export async function executeBlenderScript(
  scriptPath: string,
  outputPath: string
): Promise<{ stdout: string; stderr: string }> {
  const command = `"${config.blenderPath}" --background --python "${scriptPath}" -- "${outputPath}"`;

  try {
    const result = await execAsync(command);
    return result;
  } catch (error: any) {
    throw new Error(`Blender execution failed: ${error.message}`);
  }
}

/**
 * .blend 파일을 .glb (GLTF Binary)로 변환
 */
export async function exportToGLTF(
  blendFilePath: string,
  outputGlbPath: string
): Promise<{ success: boolean; glbPath: string }> {
  const scriptPath = path.join(config.blenderScriptsDir, 'export_gltf.py');

  const command = `"${config.blenderPath}" "${blendFilePath}" --background --python "${scriptPath}" -- "${outputGlbPath}"`;

  console.log(`🔄 Exporting to GLTF: ${command}`);

  try {
    const { stdout, stderr } = await execAsync(command, {
      maxBuffer: 10 * 1024 * 1024,
      timeout: 180000  // 3분 타임아웃 (Baking 시간 고려)
    });

    console.log('GLTF Export Output:', stdout);
    if (stderr) console.error('GLTF Export Errors:', stderr);

    return { success: true, glbPath: outputGlbPath };
  } catch (error: any) {
    throw new Error(`GLTF export failed: ${error.message}`);
  }
}

/**
 * 바이옴 지형 생성
 */
export async function generateBiomeTerrain(
  biomeLayout: BiomeLayout,
  outputBlendPath: string,
  tempDir: string
): Promise<{ stdout: string; stderr: string; imagePaths: string[] }> {
  // 1. 바이옴 레이아웃을 JSON 파일로 저장
  const biomeLayoutPath = path.join(tempDir, 'biome_layout.json');
  await writeFile(biomeLayoutPath, JSON.stringify(biomeLayout, null, 2));

  // 2. Python 스크립트 실행 (biome_generator_wvd.py)
  const biomeGeneratorScript = path.join(config.blenderScriptsDir, 'biome_generator_wvd.py');
  const pythonCommand = `python "${biomeGeneratorScript}" "${biomeLayoutPath}" "${tempDir}"`;

  console.log(`🔄 Generating biome maps: ${pythonCommand}`);
  const { stdout: genStdout, stderr: genStderr } = await execAsync(pythonCommand);

  console.log('Biome Generator Output:', genStdout);
  if (genStderr) console.error('Biome Generator Errors:', genStderr);

  // 3. Blender에서 지형 생성 (biome_terrain_blender.py)
  const biomeBlenderScript = path.join(config.blenderScriptsDir, 'biome_terrain_blender.py');
  const imageDir = path.join(tempDir, 'biome_maps');
  const paramsFile = path.join(tempDir, 'terrain_params.json');
  const previewPath = outputBlendPath.replace('.blend', '_preview.png');

  const blenderCommand = `"${config.blenderPath}" --background --python "${biomeBlenderScript}" -- "${imageDir}" "${paramsFile}" "${outputBlendPath}" "${previewPath}"`;

  console.log(`🔄 Generating terrain in Blender: ${blenderCommand}`);

  // maxBuffer 증가 및 타임아웃 설정
  const { stdout: blenderStdout, stderr: blenderStderr } = await execAsync(blenderCommand, {
    maxBuffer: 10 * 1024 * 1024, // 10MB
    timeout: 5 * 60 * 1000, // 5분
  });

  console.log('Blender Output:', blenderStdout);
  if (blenderStderr) console.error('Blender Errors:', blenderStderr);

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

  const imagePaths = paramNames.map(name => path.join(imageDir, `biome_${name}.png`));

  return {
    stdout: genStdout + '\n' + blenderStdout,
    stderr: genStderr + '\n' + blenderStderr,
    imagePaths
  };
}

/**
 * 지형에 오브젝트 배치 (나무 등)
 */
export async function placeObjectsOnTerrain(
  roadBlendPath: string,
  biomeMapsDir: string,
  assetsDir: string,
  objectCount: number = 1000
): Promise<{ success: boolean; placedCount: number }> {
  const scriptPath = path.join(config.blenderScriptsDir, 'object_placer.py');
  const outputBlendPath = roadBlendPath; // 같은 파일에 덮어쓰기
  const previewPath = roadBlendPath.replace('.blend', '_preview.png');

  const command = `"${config.blenderPath}" "${roadBlendPath}" --background --python "${scriptPath}" -- "${biomeMapsDir}" "${assetsDir}" ${objectCount} "${outputBlendPath}" "${previewPath}"`;

  console.log(`🔄 Placing objects on terrain: ${command}`);

  try {
    const { stdout, stderr } = await execAsync(command, {
      maxBuffer: 20 * 1024 * 1024, // 20MB (많은 오브젝트 로그)
      timeout: 60 * 60 * 1000,     // 60분 타임아웃 (1000개 오브젝트 처리)
    });

    console.log('Object Placer Output:', stdout);
    if (stderr) console.error('Object Placer Errors:', stderr);

    // stdout에서 배치된 오브젝트 개수 추출
    const match = stdout.match(/Placement complete: (\d+)\/\d+ objects placed/);
    const placedCount = match ? parseInt(match[1]) : 0;

    return { success: true, placedCount };
  } catch (error: any) {
    throw new Error(`Object placement failed: ${error.message}`);
  }
}
