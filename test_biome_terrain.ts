/**
 * 바이옴 지형 생성 테스트 스크립트
 *
 * Usage:
 *   npx ts-node test_biome_terrain.ts
 */

import { createSimpleBiomeLayout } from './src/services/biomeService';
import { generateBiomeTerrain } from './src/services/blenderService';
import path from 'path';
import fs from 'fs';

async function main() {
  console.log('🧪 Biome Terrain Generation Test');
  console.log('='.repeat(60));

  // 1. 간단한 2-바이옴 레이아웃 생성 (Claude AI 없이)
  console.log('\n📍 Creating biome layout...');

  const biomeLayout = createSimpleBiomeLayout(
    ['snowy_mountain', 'desert'],  // 왼쪽: 눈산, 오른쪽: 사막
    [
      [25, 50],   // 눈산 위치 (왼쪽)
      [75, 50]    // 사막 위치 (오른쪽)
    ],
    [0.3, 0.3]    // 각각 30% coverage
  );

  console.log('✅ Biome layout created:');
  console.log(JSON.stringify(biomeLayout, null, 2));

  // 2. 임시 디렉토리 생성
  const tempDir = path.join(__dirname, 'temp_biome_test');
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
  }

  const outputBlendPath = path.join(tempDir, 'test_biome_terrain.blend');

  console.log(`\n💾 Output directory: ${tempDir}`);
  console.log(`📦 Output file: ${outputBlendPath}`);

  // 3. 바이옴 지형 생성
  console.log('\n🚀 Generating biome terrain...');

  try {
    const result = await generateBiomeTerrain(biomeLayout, outputBlendPath, tempDir);

    console.log('\n' + '='.repeat(60));
    console.log('✅ TERRAIN GENERATION COMPLETE!');
    console.log('='.repeat(60));

    console.log('\n📊 Generated Files:');
    console.log(`  .blend file: ${outputBlendPath}`);
    console.log(`\n  Biome images (${result.imagePaths.length}):`);
    result.imagePaths.slice(0, 5).forEach((imgPath, i) => {
      console.log(`    ${i + 1}. ${path.basename(imgPath)}`);
    });
    if (result.imagePaths.length > 5) {
      console.log(`    ... and ${result.imagePaths.length - 5} more`);
    }

    console.log('\n📝 Logs:');
    console.log('  STDOUT:');
    console.log(result.stdout.split('\n').slice(0, 10).map(line => `    ${line}`).join('\n'));
    if (result.stdout.split('\n').length > 10) {
      console.log(`    ... (${result.stdout.split('\n').length - 10} more lines)`);
    }

    if (result.stderr) {
      console.log('\n  STDERR:');
      console.log(result.stderr.split('\n').slice(0, 5).map(line => `    ${line}`).join('\n'));
    }

    console.log('\n🎉 Test completed successfully!');
    console.log(`\n💡 Open the result: blender ${outputBlendPath}`);
  } catch (error) {
    console.error('\n❌ ERROR:', error);
    process.exit(1);
  }
}

main();
