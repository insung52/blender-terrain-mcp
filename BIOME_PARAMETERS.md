# 확장 바이옴 파라미터 시스템

## 철학
**AI 기반 지형 생성**: 파라미터 조합을 극대화하여 현실적이고 환상적인 지형을 모두 생성 가능하게 함

---

## 1. 핵심 파라미터 (마인크래프트 기반)

### 1.1 기본 지형 파라미터
```typescript
interface CoreBiomeParams {
  temperature: number;      // -1.0 ~ 1.0 (극한 추위 ~ 작열)
  humidity: number;         // 0.0 ~ 1.0 (건조 ~ 열대)
  erosion: number;          // 0.0 ~ 1.0 (부드러움 ~ 험준함)
  continentalness: number;  // -1.0 ~ 1.0 (바다 ~ 고원)
  weirdness: number;        // 0.0 ~ 1.0 (일반 ~ 특이함)
}
```

---

## 2. 확장 파라미터 (신규)

### 2.1 시각/재질 파라미터
```typescript
interface VisualBiomeParams {
  // 식생
  vegetation_color: [number, number, number];  // RGB (잔디/나뭇잎 색상)
  vegetation_density: number;                   // 0.0 ~ 1.0
  vegetation_type: 'grass' | 'moss' | 'coral' | 'crystal' | 'none';

  // 계절 변화
  season: 'spring' | 'summer' | 'autumn' | 'winter' | 'eternal';
  autumn_leaf_color: [number, number, number];  // RGB (가을 낙엽 색상)

  // 지표면 재질
  ground_color: [number, number, number];       // RGB (흙/모래/바위 기본색)
  ground_roughness: number;                     // 0.0 ~ 1.0 (매끄러움 ~ 거침)
  ground_type: 'soil' | 'sand' | 'rock' | 'ice' | 'lava' | 'crystal' | 'metal';

  // 눈 파라미터
  snow_start_height: number;                    // 눈이 시작되는 높이 (미터)
  snow_coverage: number;                        // 0.0 ~ 1.0 (부분 ~ 전체)
  snow_color: [number, number, number];         // RGB (판타지용으로 흰색 외 가능)
}
```

### 2.2 대기 파라미터
```typescript
interface AtmosphericParams {
  // 날씨 효과
  fog_density: number;                          // 0.0 ~ 1.0 (안개 밀도)
  fog_color: [number, number, number];          // RGB

  // 하늘 영향
  ambient_light_color: [number, number, number]; // RGB (주변광 색상)
  ambient_light_intensity: number;               // 0.0 ~ 2.0

  // 판타지 요소
  magic_particle_density: number;                // 0.0 ~ 1.0 (마법 입자 밀도)
  magic_particle_color: [number, number, number]; // RGB
}
```

### 2.3 지질학 파라미터
```typescript
interface GeologicalParams {
  // 암석 형성
  rock_exposure: number;                        // 0.0 ~ 1.0 (매몰 ~ 노출)
  rock_type: 'granite' | 'basalt' | 'sandstone' | 'obsidian' | 'crystal' | 'coral';
  rock_color: [number, number, number];         // RGB

  // 지층 (층위)
  stratification: number;                       // 0.0 ~ 1.0 (균일 ~ 층상)
  layer_count: number;                          // 2 ~ 10 (보이는 층 개수)
  layer_colors: [number, number, number][];     // RGB 배열 (각 층 색상)

  // 화산/특수
  lava_presence: number;                        // 0.0 ~ 1.0 (용암 존재)
  water_presence: number;                       // 0.0 ~ 1.0 (물 존재)
  crystal_growth: number;                       // 0.0 ~ 1.0 (크리스탈 성장, 판타지)
}
```

### 2.4 Biome Transition Parameters
```typescript
interface TransitionParams {
  blend_mode: 'perlin_smooth' | 'voronoi' | 'sharp' | 'cellular';
  blend_distance: number;                       // 0.1 ~ 50.0 meters
  transition_asymmetry: number;                 // -1.0 ~ 1.0 (favor A vs B)
}
```

---

## 3. Complete Biome Interface

```typescript
interface ExtendedBiome {
  // Identity
  id: string;
  name: string;
  category: 'realistic' | 'fantasy' | 'alien' | 'abstract';

  // Core terrain
  core: CoreBiomeParams;

  // Extended
  visual: VisualBiomeParams;
  atmosphere: AtmosphericParams;
  geology: GeologicalParams;

  // Metadata
  description?: string;
  preset_name?: string;
}
```

---

## 4. Preset Examples

### 4.1 Realistic Biomes

#### Snowy Mountain
```typescript
{
  name: "Snowy Alps",
  category: "realistic",
  core: {
    temperature: -0.7,
    humidity: 0.4,
    erosion: 0.8,
    continentalness: 0.6,
    weirdness: 0.0
  },
  visual: {
    vegetation_color: [0.2, 0.3, 0.2],
    vegetation_density: 0.1,
    vegetation_type: 'moss',
    season: 'winter',
    ground_color: [0.4, 0.4, 0.45],
    ground_type: 'rock',
    snow_start_height: 1500,
    snow_coverage: 0.8,
    snow_color: [1.0, 1.0, 1.0]
  },
  geology: {
    rock_exposure: 0.7,
    rock_type: 'granite',
    rock_color: [0.5, 0.5, 0.55]
  }
}
```

#### Autumn Forest
```typescript
{
  name: "Autumn Forest",
  category: "realistic",
  core: {
    temperature: 0.3,
    humidity: 0.7,
    erosion: 0.3
  },
  visual: {
    vegetation_color: [0.3, 0.5, 0.2],
    vegetation_density: 0.8,
    vegetation_type: 'grass',
    season: 'autumn',
    autumn_leaf_color: [0.9, 0.5, 0.2],  // Orange leaves
    ground_color: [0.4, 0.3, 0.2]
  }
}
```

### 4.2 Fantasy Biomes

#### Crystal Caves
```typescript
{
  name: "Crystal Caves",
  category: "fantasy",
  core: {
    temperature: -0.3,
    humidity: 0.2,
    erosion: 0.9,
    weirdness: 0.9
  },
  visual: {
    vegetation_type: 'crystal',
    ground_color: [0.2, 0.2, 0.3],
    ground_type: 'crystal',
    snow_color: [0.7, 0.9, 1.0]  // Blue "snow" (frost)
  },
  atmosphere: {
    ambient_light_color: [0.5, 0.7, 1.0],
    magic_particle_density: 0.6,
    magic_particle_color: [0.3, 0.8, 1.0]
  },
  geology: {
    crystal_growth: 0.9,
    rock_type: 'crystal',
    layer_colors: [
      [0.3, 0.3, 0.5],
      [0.5, 0.7, 0.9],
      [0.7, 0.9, 1.0]
    ]
  }
}
```

#### Volcanic Wasteland
```typescript
{
  name: "Volcanic Wasteland",
  category: "fantasy",
  core: {
    temperature: 0.95,
    humidity: 0.0,
    erosion: 0.7,
    weirdness: 0.8
  },
  visual: {
    vegetation_density: 0.0,
    ground_color: [0.2, 0.1, 0.1],
    ground_type: 'lava'
  },
  atmosphere: {
    fog_density: 0.5,
    fog_color: [0.3, 0.1, 0.0],
    ambient_light_color: [1.0, 0.5, 0.2]
  },
  geology: {
    rock_type: 'obsidian',
    rock_color: [0.1, 0.1, 0.1],
    lava_presence: 0.6
  }
}
```

#### Alien Coral Reef (Land)
```typescript
{
  name: "Terrestrial Coral",
  category: "alien",
  core: {
    temperature: 0.6,
    humidity: 0.9,
    erosion: 0.4,
    weirdness: 1.0
  },
  visual: {
    vegetation_type: 'coral',
    vegetation_color: [1.0, 0.4, 0.6],  // Pink coral
    vegetation_density: 0.9,
    ground_color: [0.8, 0.9, 0.95],
    ground_type: 'coral'
  },
  atmosphere: {
    ambient_light_color: [0.6, 0.9, 1.0],
    magic_particle_density: 0.4,
    magic_particle_color: [0.3, 1.0, 0.8]
  },
  geology: {
    rock_type: 'coral',
    layer_colors: [
      [1.0, 0.6, 0.7],
      [0.6, 0.9, 1.0],
      [0.9, 0.5, 1.0]
    ]
  }
}
```

---

## 5. Parameter Dependencies & Rules

### 5.1 Temperature-dependent Rules
```typescript
function applyTemperatureRules(biome: ExtendedBiome) {
  const temp = biome.core.temperature;

  // Auto-adjust snow
  if (temp < -0.3) {
    biome.visual.snow_start_height = Math.max(0, 2000 + temp * 1000);
    biome.visual.snow_coverage = Math.min(1.0, (-temp - 0.3) / 0.7);
  }

  // Vegetation color based on temperature
  if (temp < 0.0) {
    // Cold: darker, bluish greens
    biome.visual.vegetation_color[1] *= 0.8;  // reduce green
  } else if (temp > 0.7) {
    // Hot: yellower greens
    biome.visual.vegetation_color[0] += 0.1;  // add red
  }
}
```

### 5.2 Humidity-dependent Rules
```typescript
function applyHumidityRules(biome: ExtendedBiome) {
  const humidity = biome.core.humidity;

  // Vegetation density
  biome.visual.vegetation_density *= (0.2 + humidity * 0.8);

  // Water presence
  biome.geology.water_presence = Math.max(0, humidity - 0.3);

  // Ground type
  if (humidity > 0.7) {
    biome.visual.ground_type = 'soil';
  } else if (humidity < 0.2) {
    biome.visual.ground_type = 'sand';
  }
}
```

---

## 6. Claude AI Prompt Enhancement

```typescript
const EXTENDED_BIOME_PROMPT = `
You are an advanced terrain generation AI. Create biomes for both realistic and fantastical worlds.

Available parameters:
1. Core: temperature, humidity, erosion, continentalness, weirdness
2. Visual: vegetation_color, season, ground_color, snow_start_height, etc.
3. Atmosphere: fog, ambient_light, magic_particles
4. Geology: rock_type, layers, lava/water/crystal presence

Preset biomes (can be modified):
${JSON.stringify(PRESET_BIOMES, null, 2)}

User description: "${userDescription}"

Generate creative biomes. For fantasy requests:
- Use unusual colors (purple grass, red snow, etc.)
- Add magic particles or special effects
- Create unique geology (crystal layers, floating rocks)
- Combine unexpected elements

Return JSON with full ExtendedBiome structure.
`;
```

---

## 7. Implementation Complexity

### Easy to Implement ✅
- Basic colors (vegetation, ground, snow)
- Season parameter (affects leaf color)
- Snow start height
- Rock exposure

### Medium Difficulty 🟡
- Stratification/layers (multiple ColorRamp nodes)
- Fog density (World settings)
- Vegetation types (different Instance collections)

### Advanced 🔴
- Magic particles (Particle System)
- Lava flows (Fluid simulation)
- Crystal growth (Geometry Nodes procedural)
- Ambient light per-biome (World nodes per region)

---

## 8. Recommended Parameter Set for V1

**Start simple, expand later:**

```typescript
// Phase 1: Core + Basic Visual
interface BiomeV1 {
  // Core (5 params)
  temperature: number;
  humidity: number;
  erosion: number;
  continentalness: number;
  weirdness: number;

  // Visual (8 params)
  vegetation_color: [number, number, number];
  ground_color: [number, number, number];
  snow_start_height: number;
  snow_coverage: number;
  season: 'spring' | 'summer' | 'autumn' | 'winter';
  rock_exposure: number;
  vegetation_density: number;
  ground_roughness: number;
}
```

**Total: 13 parameters → Enough for diverse results without overwhelming complexity**

---

## 9. Future Expansion (Phase 2+)

- Atmospheric effects (fog, lighting)
- Geological layers
- Fantasy elements (particles, crystals)
- Vegetation types beyond grass
- Lava/water presence
- Custom rock types

---

## 10. 질문에 대한 답변

### Q1: 눈 시작 높이 vs 온도?
**답변:** 둘 다 유지!
- `temperature`: 바이옴의 전체 기후
- `snow_start_height`: 정밀한 제어 (저지대는 뜨거운데 봉우리만 눈 덮인 경우 유용)
- 함께 작동: `effective_snow_height = base_height - (temperature * 1000)`

### Q2: 계절 파라미터 (낙엽 색)?
**답변:** 네! `season` + `autumn_leaf_color` 추가
- 같은 지형을 다른 계절로 표현 가능
- 사용자가 "가을 숲" vs "여름 숲" 요청 가능

### Q3: AI 창의성을 위한 파라미터 확장?
**답변:** 강력 추천!
- **현실 모드:** 13개 핵심 파라미터 사용
- **판타지 모드:** 색상, 입자, 마법 요소 추가
- Claude AI가 야생적인 조합 생성 가능:
  - "보라색 크리스탈 사막과 떠다니는 바위"
  - "생물발광 산호 숲"
  - "푸른 불꽃이 있는 얼어붙은 용암 지대"

**전략:**
1. **Phase 1:** 13 파라미터 (핵심 + 기본 시각)
2. **Phase 2:** 10개 추가 (대기, 지질학)
3. **Phase 3:** 판타지 요소 (입자, 크리스탈 등)

이 점진적 접근법으로 구현 가능성을 유지하면서 창의적 잠재력을 극대화합니다.

---

## 결론

**권장 파라미터 개수:**
- **V1 (MVP):** 13 파라미터 ✅
- **V2 (완전판):** 23 파라미터
- **V3 (판타지):** 30+ 파라미터

V1로 시스템을 검증한 후, 사용자 피드백에 따라 확장.

동의하시나요?
