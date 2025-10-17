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

  // 2. Python 스크립트 실행 (biome_generator.py)
  const biomeGeneratorScript = path.join(config.blenderScriptsDir, 'biome_generator.py');
  const pythonCommand = `python "${biomeGeneratorScript}" "${biomeLayoutPath}" "${tempDir}"`;

  console.log(`🔄 Generating biome maps: ${pythonCommand}`);
  const { stdout: genStdout, stderr: genStderr } = await execAsync(pythonCommand);

  console.log('Biome Generator Output:', genStdout);
  if (genStderr) console.error('Biome Generator Errors:', genStderr);

  // 3. Blender에서 지형 생성 (biome_terrain_blender.py)
  const biomeBlenderScript = path.join(config.blenderScriptsDir, 'biome_terrain_blender.py');
  const imageDir = path.join(tempDir, 'biome_maps');

  const blenderCommand = `"${config.blenderPath}" --background --python "${biomeBlenderScript}" -- "${imageDir}" "${outputBlendPath}"`;

  console.log(`🔄 Generating terrain in Blender: ${blenderCommand}`);
  const { stdout: blenderStdout, stderr: blenderStderr } = await execAsync(blenderCommand);

  console.log('Blender Output:', blenderStdout);
  if (blenderStderr) console.error('Blender Errors:', blenderStderr);

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
