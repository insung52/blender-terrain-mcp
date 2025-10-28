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
  const fs = require('fs');
  const scriptPath = path.join(config.blenderScriptsDir, 'export_gltf_simple.py');

  const command = `"${config.blenderPath}" "${blendFilePath}" --background --python "${scriptPath}" -- "${outputGlbPath}"`;

  console.log(`🔄 Exporting to GLTF (simple): ${command}`);

  try {
    const { stdout, stderr } = await execAsync(command, {
      maxBuffer: 10 * 1024 * 1024,
      timeout: 180000  // 3분 타임아웃 (Baking 시간 고려)
    });

    console.log('GLTF Export Output:', stdout);
    if (stderr) console.error('GLTF Export Errors:', stderr);

    return { success: true, glbPath: outputGlbPath };
  } catch (error: any) {
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
export async function generateBiomeTerrain(
  biomeLayout: BiomeLayout,
  outputBlendPath: string,
  tempDir: string,
  onProgress?: (message: string) => void
): Promise<{ stdout: string; stderr: string; imagePaths: string[] }> {
  // 1. 바이옴 레이아웃을 JSON 파일로 저장
  const biomeLayoutPath = path.join(tempDir, 'biome_layout.json');
  await writeFile(biomeLayoutPath, JSON.stringify(biomeLayout, null, 2));

  // 2. Python 스크립트 실행 (biome_generator_wvd.py)
  if (onProgress) onProgress('Generating biome maps...');
  const biomeGeneratorScript = path.join(config.blenderScriptsDir, 'biome_generator_wvd.py');
  const pythonCommand = `python "${biomeGeneratorScript}" "${biomeLayoutPath}" "${tempDir}"`;

  console.log(`🔄 Generating biome maps: ${pythonCommand}`);
  const { stdout: genStdout, stderr: genStderr } = await execAsync(pythonCommand);

  console.log('Biome Generator Output:', genStdout);
  if (genStderr) console.error('Biome Generator Errors:', genStderr);

  if (onProgress) onProgress('Biome maps generated');

  // 3. Blender에서 지형 생성 (biome_terrain_blender.py)
  if (onProgress) onProgress('Creating 3D terrain mesh...');
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

  if (onProgress) onProgress('Terrain mesh created');

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
 * 지형에 오브젝트 배치 (나무 등) - 독립 blend 파일 생성
 */
export async function placeObjectsOnTerrain(
  baseBlendPath: string,      // terrain 또는 road blend 파일
  biomeMapsDir: string,
  assetsDir: string,
  objectCount: number,
  outputBlendPath: string,    // 새로운 독립 blend 파일
  previewPath: string,
  onProgress?: (current: number, total: number, eta: number) => void
): Promise<{ success: boolean; placedCount: number }> {
  const scriptPath = path.join(config.blenderScriptsDir, 'object_placer.py');
  const logPath = outputBlendPath.replace('.blend', '_log.txt');

  const command = `"${config.blenderPath}" "${baseBlendPath}" --background --python "${scriptPath}" -- "${biomeMapsDir}" "${assetsDir}" ${objectCount} "${outputBlendPath}" "${previewPath}"`;

  console.log(`🔄 Placing objects on terrain: ${command}`);

  const fs = require('fs');
  const { spawn } = require('child_process');

  return new Promise((resolve, reject) => {
    // Blender 프로세스를 spawn으로 실행
    const blenderProcess = spawn(config.blenderPath, [
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
            stream.on('data', (chunk: string) => {
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
        } catch (err) {
          // 로그 파일 읽기 실패 무시
        }
      }
    }, 1000); // 1초마다 체크

    let stdout = '';
    let stderr = '';

    blenderProcess.stdout.on('data', (data: Buffer) => {
      stdout += data.toString();
    });

    blenderProcess.stderr.on('data', (data: Buffer) => {
      stderr += data.toString();
    });

    blenderProcess.on('close', (code: number) => {
      clearInterval(logCheckInterval);

      if (code === 0) {
        console.log('Object Placer Output:', stdout);
        if (stderr) console.error('Object Placer Errors:', stderr);

        // stdout에서 배치된 오브젝트 개수 추출
        const match = stdout.match(/Placement complete: (\d+)\/\d+ objects placed/);
        const placedCount = match ? parseInt(match[1]) : lastPlacedCount;

        resolve({ success: true, placedCount });
      } else {
        reject(new Error(`Object placement failed with code ${code}: ${stderr}`));
      }
    });

    blenderProcess.on('error', (err: Error) => {
      clearInterval(logCheckInterval);
      reject(new Error(`Failed to start Blender: ${err.message}`));
    });
  });
}
