# GLTF Export 기능 추가 계획

## 목표
웹페이지에서 지형을 `.glb` (GLTF Binary) 형식으로 다운로드 가능하게 하여, Three.js 등 웹 3D 라이브러리에서 바로 사용 가능하도록 함.

---

## 1. 기본 요구사항

### 1.1 Export 대상
- ✅ **지형 메시** (Terrain Mesh)
  - Geometry Nodes **Apply 완료** 상태
  - Material Shader Nodes → Texture Baking 필요
- ✅ **물 메시** (Water Mesh)
  - 단순한 평면 메시 (깊이감/Fresnel 등 고급 셰이더 제외)
  - 기본 투명 파란색 Material
  - Export 시점에 없으면 자동 생성
- ✅ **도로 메시** (Road Mesh, 있는 경우)
  - 이미 단순한 Geometry + 단색 Material
  - **Baking 불필요** - 그냥 포함만 하면 됨

### 1.2 제외 사항
- ❌ Blender 전용 고급 셰이더 (Fresnel, Shader Nodes 복잡한 연산)
- ❌ 깊이감(Depth) 기반 색상 변화
- ❌ 애니메이션 (현재 단계에서는)

---

## 2. 구현 계획

### Phase 1: Blender Python 스크립트 수정

#### 2.1 Texture Baking 기능 추가
**목적:** Material Shader Nodes (Procedural)를 실제 이미지로 변환

**구현 위치:** `src/blender-scripts/export_gltf.py` (새 파일)
- **왜 새 파일?**
  - 기존 `.blend` 파일을 읽어서 GLTF로 변환하는 독립 스크립트
  - 지형 생성 후 언제든 실행 가능 (도로 생성 전/후 모두)
  - 재사용 가능: `blender terrain.blend --background --python export_gltf.py -- output.glb`

**Baking 절차:**
```python
import bpy

def bake_terrain_textures(terrain_obj, output_dir):
    """
    지형 메시의 Material을 이미지 텍스처로 Baking

    Args:
        terrain_obj: 지형 메시 객체
        output_dir: 텍스처 출력 디렉토리

    Returns:
        baked_texture_path: Baking된 텍스처 파일 경로
    """
    # 1. UV Unwrap (Smart UV Project)
    bpy.context.view_layer.objects.active = terrain_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')

    # 2. Bake용 이미지 생성 (2048x2048)
    bake_image = bpy.data.images.new(
        name="TerrainBake",
        width=2048,
        height=2048,
        alpha=False
    )

    # 3. Material에 Image Texture 노드 추가
    material = terrain_obj.data.materials[0]
    nodes = material.node_tree.nodes

    # Image Texture 노드 생성 (Baking 타겟)
    bake_node = nodes.new('ShaderNodeTexImage')
    bake_node.image = bake_image
    bake_node.select = True
    nodes.active = bake_node

    # 4. Bake 실행
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.bake_type = 'DIFFUSE'
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False

    bpy.ops.object.bake(type='DIFFUSE')

    # 5. 이미지 저장
    texture_path = os.path.join(output_dir, 'terrain_diffuse.png')
    bake_image.filepath_raw = texture_path
    bake_image.file_format = 'PNG'
    bake_image.save()

    # 6. Baked 텍스처를 실제 Material에 연결
    # Material의 Shader Nodes를 단순화 (Geometry는 이미 Apply됨)
    # 기존: ColorRamp, Noise Texture, Math Nodes 등 복잡한 Shader Graph
    # → GLTF는 복잡한 노드 지원 안함
    # 변환: Image Texture → Principled BSDF (단순)
    for node in nodes:
        if node != bake_node and node.type != 'OUTPUT_MATERIAL':
            nodes.remove(node)

    # Principled BSDF 추가
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    output = nodes.get('Material Output')

    links = material.node_tree.links
    links.new(bake_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    print(f"✅ Texture baked: {texture_path}")
    return texture_path
```

#### 2.2 물 메시 Material 단순화
**목적:** 기존 복잡한 물 Material을 GLTF 호환 Material로 변경

**현재 상황:**
- `biome_terrain_blender.py`에서 물 메시 생성됨 (Water Cube)
- Material: Fresnel + Volume Absorption + Glass BSDF (고급 셰이더)
- **GLTF 변환 불가** - 복잡한 노드 지원 안함

**해결 방법:**
Export 시점에 물 Material을 단순화
```python
def simplify_water_material(water_obj):
    """
    물 메시의 Material을 GLTF 호환 단순 Material로 교체

    Args:
        water_obj: 물 메시 객체

    Returns:
        water_obj: Material이 교체된 물 메시
    """
    # 기존 Material 제거
    water_obj.data.materials.clear()

    # 새 Material 생성 (GLTF 호환)
    water_mat = bpy.data.materials.new(name="WaterMaterial_Simple")
    water_mat.use_nodes = True

    nodes = water_mat.node_tree.nodes
    nodes.clear()

    # Principled BSDF (단순 설정만)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.1, 0.3, 0.6, 1.0)  # 파란색
    bsdf.inputs['Transmission Weight'].default_value = 0.8  # 80% 투명
    bsdf.inputs['Roughness'].default_value = 0.1  # 약간 반짝임
    bsdf.inputs['IOR'].default_value = 1.333  # 물의 굴절률 (기본값)

    # Output
    output = nodes.new('ShaderNodeOutputMaterial')
    water_mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Blend Mode 설정
    water_mat.blend_method = 'BLEND'

    # Material 할당
    water_obj.data.materials.append(water_mat)

    print("✅ Water material simplified for GLTF")
    print("   Removed: Fresnel, Volume Absorption")
    print("   Kept: Basic transparency and color")

    return water_obj
```

#### 2.3 도로 메시 포함 (있으면)
```python
# 도로 메시 찾기 (있으면 Export에 포함)
road_obj = bpy.data.objects.get("Road")

objects_to_export = [terrain_obj, water_obj]
if road_obj:
    objects_to_export.append(road_obj)
    print("✅ Road mesh found, will be included in export")
```

#### 2.4 GLTF Export
```python
def export_to_gltf(objects_list, output_path):
    """
    지형 + 물 + (도로) 메시를 GLB 포맷으로 Export

    Args:
        objects_list: Export할 객체 리스트 [terrain, water, road(optional)]
        output_path: 출력 .glb 파일 경로
    """
    # 1. 모든 객체 선택 해제
    bpy.ops.object.select_all(action='DESELECT')

    # 2. Export할 객체들 선택
    for obj in objects_list:
        obj.select_set(True)

    # 3. GLB Export
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format='GLB',  # Binary 포맷 (단일 파일)
        use_selection=True,   # 선택된 객체만

        # Geometry
        export_apply=True,    # Modifiers Apply

        # Materials & Textures
        export_materials='EXPORT',
        export_colors=True,
        export_textures=True,
        export_image_format='AUTO',  # PNG/JPEG 자동

        # Optimization
        export_draco_mesh_compression_enable=True,  # 압축
        export_draco_mesh_compression_level=6,

        # Extras
        export_extras=False,
        export_cameras=False,
        export_lights=False
    )

    print(f"✅ GLTF exported: {output_path}")
```

#### 2.5 통합 스크립트
**새 파일:** `src/blender-scripts/export_gltf.py`

```python
"""
GLTF Export 전용 스크립트
기존 .blend 파일을 읽어서 .glb로 변환 (도로 생성 전/후 모두 사용 가능)

Usage:
    blender <terrain.blend> --background --python export_gltf.py -- <output.glb>

처리 순서:
    1. .blend 파일 로드 (자동, Blender가 처리)
    2. Terrain 객체 찾기
    3. Texture Baking (Shader Nodes → PNG)
    4. Water 메시 생성 (없으면)
    5. Road 메시 찾기 (있으면 포함)
    6. GLTF Export (Terrain + Water + Road(optional))
"""

import bpy
import sys
import os

# 커맨드라인 인자
argv = sys.argv[argv.index("--") + 1:]
output_glb_path = argv[0]

# 현재 Scene의 지형 객체 찾기
terrain_obj = bpy.data.objects.get("BiomeTerrain")
if not terrain_obj:
    print("❌ Terrain object not found")
    sys.exit(1)

# 1. Texture Baking
output_dir = os.path.dirname(output_glb_path)
bake_terrain_textures(terrain_obj, output_dir)

# 2. 물 메시 Material 단순화
water_obj = bpy.data.objects.get("Water")
if not water_obj:
    print("⚠️ Water mesh not found")
    # 물 없이 진행 (Optional)
else:
    print("✅ Water mesh found")
    # Material 단순화 (Fresnel, Volume 제거)
    simplify_water_material(water_obj)

# 3. 도로 메시 찾기 (있으면 포함)
road_obj = bpy.data.objects.get("Road")
objects_to_export = [terrain_obj]
if water_obj:
    objects_to_export.append(water_obj)
if road_obj:
    objects_to_export.append(road_obj)
    print("✅ Road mesh found, will be included")

# 4. GLTF Export
export_to_gltf(objects_to_export, output_glb_path)

print("🎉 GLTF Export Complete!")
print(f"   Objects: {len(objects_to_export)} (Terrain + Water{' + Road' if road_obj else ''})")
```

---

### Phase 2: Backend 서비스 추가

#### 2.1 GLTF Export 서비스
**파일:** `src/services/blenderService.ts`

```typescript
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
      timeout: 120000  // 2분 타임아웃
    });

    console.log('GLTF Export Output:', stdout);
    if (stderr) console.error('GLTF Export Errors:', stderr);

    return { success: true, glbPath: outputGlbPath };
  } catch (error: any) {
    throw new Error(`GLTF export failed: ${error.message}`);
  }
}
```

#### 2.2 API 엔드포인트 추가
**파일:** `src/server.ts`

```typescript
// GLTF Export API
app.post('/api/terrain/:terrainId/export-gltf', async (req, res) => {
  try {
    const { terrainId } = req.params;

    // 1. Terrain 조회
    const terrain = await prisma.terrain.findUnique({
      where: { id: terrainId }
    });

    if (!terrain || !terrain.blendFilePath) {
      return res.status(404).json({
        success: false,
        error: 'Terrain not found'
      });
    }

    // 2. 이미 GLTF 파일이 있는지 확인
    const glbPath = terrain.blendFilePath.replace('.blend', '.glb');

    if (fs.existsSync(glbPath)) {
      console.log(`[API] GLTF already exists: ${glbPath}`);
      return res.json({
        success: true,
        glbPath: glbPath,
        cached: true
      });
    }

    // 3. GLTF Export 실행
    console.log(`[API] Exporting to GLTF: ${terrain.blendFilePath}`);
    const result = await exportToGLTF(terrain.blendFilePath, glbPath);

    // 4. DB 업데이트 (gltfPath 추가)
    await prisma.terrain.update({
      where: { id: terrainId },
      data: {
        metadata: {
          ...(terrain.metadata as any),
          gltfPath: glbPath
        }
      }
    });

    res.json({
      success: true,
      glbPath: glbPath,
      cached: false
    });

  } catch (error: any) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// GLTF 파일 다운로드
app.get('/api/terrain/:terrainId/download-gltf', async (req, res) => {
  try {
    const { terrainId } = req.params;

    const terrain = await prisma.terrain.findUnique({
      where: { id: terrainId }
    });

    if (!terrain) {
      return res.status(404).json({ error: 'Terrain not found' });
    }

    const glbPath = terrain.blendFilePath!.replace('.blend', '.glb');

    if (!fs.existsSync(glbPath)) {
      return res.status(404).json({
        error: 'GLTF file not found. Please export first.'
      });
    }

    res.download(glbPath, `terrain_${terrainId}.glb`);

  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});
```

---

### Phase 3: Frontend UI 추가

#### 3.1 GLTF 다운로드 버튼
**파일:** `client/src/App.tsx`

**위치:** 기존 `.blend` 다운로드 버튼 옆

```tsx
// Terrain 카드에 GLTF 버튼 추가
<div className="terrain-actions">
  {/* 기존 .blend 다운로드 */}
  <button onClick={() => downloadBlend(terrain.id)}>
    📦 Download .blend
  </button>

  {/* 새로운 GLTF 다운로드 */}
  <button
    onClick={() => downloadGLTF(terrain.id)}
    disabled={gltfExporting === terrain.id}
  >
    {gltfExporting === terrain.id ? (
      '⏳ Exporting...'
    ) : (
      '🌐 Download .glb'
    )}
  </button>
</div>
```

#### 3.2 GLTF Export 함수
```tsx
const [gltfExporting, setGltfExporting] = useState<string | null>(null);

const downloadGLTF = async (terrainId: string) => {
  try {
    setGltfExporting(terrainId);

    // 1. GLTF Export 요청 (캐시 있으면 바로 반환)
    const exportRes = await fetch(`${API_URL}/api/terrain/${terrainId}/export-gltf`, {
      method: 'POST'
    });

    const exportData = await exportRes.json();

    if (!exportData.success) {
      throw new Error(exportData.error);
    }

    if (exportData.cached) {
      console.log('GLTF file already cached');
    } else {
      console.log('GLTF exported successfully');
    }

    // 2. 다운로드
    window.location.href = `${API_URL}/api/terrain/${terrainId}/download-gltf`;

  } catch (error) {
    console.error('GLTF download failed:', error);
    alert('Failed to export GLTF');
  } finally {
    setGltfExporting(null);
  }
};
```

---

## 3. 구현 우선순위

### ✅ Phase 1 (핵심 기능)
1. **Texture Baking** - 가장 중요 (Procedural → Image)
2. **물 메시 생성** - 간단한 평면 + 투명 Material
3. **GLTF Export** - 지형 + 물 메시 Export

### ✅ Phase 2 (Backend)
4. **Export 서비스** - Blender 실행 및 GLTF 변환
5. **API 엔드포인트** - Export 요청/다운로드

### ✅ Phase 3 (Frontend)
6. **UI 버튼 추가** - `.glb` 다운로드 버튼
7. **Loading 상태 표시** - Export 진행 중 표시

---

## 4. 예상 결과물

### 4.1 파일 구조
```
output/
├── abc123.blend           (원본 Blender 파일)
├── abc123_preview.png     (미리보기)
├── abc123.glb             (GLTF Binary - 지형+물)
└── abc123_diffuse.png     (Baked Texture, .glb에 임베드됨)
```

### 4.2 GLB 파일 내용
```
terrain.glb
├── Scene
│   ├── BiomeTerrain (Mesh)
│   │   ├── Vertices: 10,201
│   │   ├── Material: PBR with baked texture
│   │   └── Texture: terrain_diffuse.png (embedded)
│   └── Water (Mesh)
│       ├── Vertices: ~400 (Subdivided plane)
│       ├── Material: Transparent blue
│       └── Properties:
│           - Base Color: (0.1, 0.3, 0.6)
│           - Transmission: 0.8
│           - Roughness: 0.1
```

### 4.3 웹에서 사용 예시 (Three.js)
```javascript
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';

const loader = new GLTFLoader();
loader.load('terrain.glb', (gltf) => {
  scene.add(gltf.scene);

  // 지형 + 물 메시 모두 자동 로드됨
  console.log('Loaded objects:', gltf.scene.children);
  // → [BiomeTerrain, Water]
});
```

---

## 5. 추가 고려사항

### 5.1 파일 크기 최적화
- **Draco 압축** 활성화 (Geometry 압축)
- **Texture 해상도** 조정 가능 (2048x2048 기본, 옵션으로 1024/4096 선택)
- **Normal Map** Baking 추가 (선택 사항)

### 5.2 물 Material 개선 (Future)
- 간단한 Wave Animation (Vertex Displacement)
- Normal Map으로 파도 표현
- Opacity Mask로 해안선 처리

### 5.3 에러 처리
- Baking 실패 시 Fallback (단색 Material)
- GLTF Export 실패 시 재시도
- 파일 크기 체크 (너무 크면 경고)

---

## 6. 테스트 계획

### 6.1 단위 테스트
```bash
# Blender Script 단독 테스트
blender terrain.blend --background --python export_gltf.py -- output.glb

# 결과 확인
ls -lh output.glb
# → 파일 크기, 생성 시간 확인
```

### 6.2 통합 테스트
```bash
# 1. 지형 생성
curl -X POST http://localhost:3000/api/terrain -d '{"useAI": true, "description": "왼쪽은 산, 오른쪽은 바다"}'

# 2. GLTF Export
curl -X POST http://localhost:3000/api/terrain/<id>/export-gltf

# 3. 다운로드
curl http://localhost:3000/api/terrain/<id>/download-gltf -o test.glb

# 4. 웹에서 확인 (Three.js Viewer)
```

### 6.3 검증 항목
- [ ] GLB 파일 크기 < 10MB
- [ ] 지형 메시 정점 수 = 10,201
- [ ] 물 메시 존재 확인
- [ ] Texture 임베드 확인
- [ ] Three.js에서 로드 가능
- [ ] Material이 올바르게 표시됨

---

## 7. 타임라인

| Phase | 작업 내용 | 예상 시간 |
|-------|----------|----------|
| 1 | Texture Baking 스크립트 작성 | 1시간 |
| 2 | 물 메시 생성 함수 | 30분 |
| 3 | GLTF Export 통합 | 30분 |
| 4 | Backend 서비스 추가 | 1시간 |
| 5 | API 엔드포인트 | 30분 |
| 6 | Frontend UI 추가 | 1시간 |
| 7 | 테스트 및 디버깅 | 1시간 |
| **합계** | | **5.5시간** |

---

## 8. 결론

GLTF Export 기능 추가로:
- ✅ 웹 3D 라이브러리에서 바로 사용 가능
- ✅ 파일 크기 작음 (압축)
- ✅ 지형 + 물 메시 동시 Export
- ✅ Texture Baking으로 호환성 보장
- ✅ 사용자 편의성 향상 (.blend와 .glb 선택 가능)

**다음 단계:**
이 계획서를 바탕으로 Phase 1부터 순차적으로 구현 시작!
