"use strict";
/**
 * 바이옴 지형 생성 서비스
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateBiomeLayout = generateBiomeLayout;
exports.createSimpleBiomeLayout = createSimpleBiomeLayout;
exports.biomeLayoutToJSON = biomeLayoutToJSON;
const sdk_1 = __importDefault(require("@anthropic-ai/sdk"));
const biome_1 = require("../types/biome");
const anthropic = new sdk_1.default({
    apiKey: process.env.ANTHROPIC_API_KEY || '',
});
/**
 * Claude AI 프롬프트: 자연어 → 바이옴 레이아웃 변환
 */
const BIOME_GENERATION_PROMPT = `You are an advanced terrain generation AI. You create biome layouts for realistic terrain generation.

**Available Biome Presets:**
${JSON.stringify(biome_1.PRESET_BIOMES_V1, null, 2)}

**Task:**
Generate a biome layout based on the user's description.

**Output Format (JSON only, no other text):**
{
  "biome_points": [
    {
      "position": [x, y],  // 100x100 coordinate system (0~100)
      "biome_params": {
        // All 13 parameters (copy from preset or customize)
        "temperature": number,      // -1.0 ~ 1.0
        "humidity": number,         // 0.0 ~ 1.0
        "erosion": number,          // 0.0 ~ 1.0
        "continentalness": number,  // -1.0 ~ 1.0
        "weirdness": number,        // 0.0 ~ 1.0

        // 🌿 vegetation_color: Color for vegetation objects (trees, grass objects) - will be used later for object placement
        "vegetation_color_r": number,  // 0.0 ~ 1.0 (RGB)
        "vegetation_color_g": number,  // 0.0 ~ 1.0
        "vegetation_color_b": number,  // 0.0 ~ 1.0

        // 🟫 ground_color: MAIN terrain color (what you actually see on the ground mesh)
        // ⚠️ IMPORTANT: Water (lakes, rivers, ocean) uses separate water mesh with transparency
        //    So ground_color for water biomes should be SOIL/SAND color (what's under the water)
        // Examples:
        //   - Grass plains: GREEN (0.3, 0.6, 0.2) - covered with grass
        //   - Desert: SANDY YELLOW (0.8, 0.7, 0.4) - sand color
        //   - Swamp: DARK GREEN/GRAY (0.25, 0.3, 0.2) - murky water/mud
        //   - Snow: WHITE (0.9, 0.9, 0.95) - snow covered
        //   - Rocky mountain: GRAY/BROWN (0.4, 0.4, 0.45) - exposed rock
        //   - 🌊 Lake/River: BROWN SOIL (0.4, 0.35, 0.25) - lake bed soil color
        //   - 🌊 Ocean: DARK GRAY SAND (0.3, 0.3, 0.3) - ocean floor sand
        "ground_color_r": number,  // 0.0 ~ 1.0 (RGB)
        "ground_color_g": number,  // 0.0 ~ 1.0
        "ground_color_b": number,  // 0.0 ~ 1.0

        // 🪨 rock_color: Rock/cliff color (exposed on steep slopes)
        // Examples:
        //   - Snowy mountain: GRAY-BROWN (0.5, 0.48, 0.45) - cold rock
        //   - Desert: RED-BROWN SANDSTONE (0.7, 0.55, 0.4) - warm desert rock
        //   - Forest: DARK MOSSY ROCK (0.4, 0.38, 0.3) - moss-covered
        //   - Plains: BROWN ROCK (0.45, 0.4, 0.35) - regular stone
        "rock_color_r": number,  // 0.0 ~ 1.0 (RGB)
        "rock_color_g": number,  // 0.0 ~ 1.0
        "rock_color_b": number,  // 0.0 ~ 1.0

        "snow_start_height": number,
        "rock_exposure": number
      },
      "coverage": number,  // 0.01 ~ 1.0 (influence radius)
      "description": string
    }
  ],
  "blend_distance": number  // 10 ~ 30 meters
}

**Guidelines:**
1. Position coordinates: [0, 0] is bottom-left, [100, 100] is top-right, [50, 50] is center
2. For "left, center, right" descriptions:
   - Left: x ≈ 15~25
   - Center: x ≈ 40~60
   - Right: x ≈ 75~85
3. For "top, middle, bottom" descriptions:
   - Top: y ≈ 75~85
   - Middle: y ≈ 40~60
   - Bottom: y ≈ 15~25
4. Coverage rules:
   - 🏔️ **Mountains/Hills (continentalness > 0.5)**: ALWAYS use small coverage = 0.05~0.15
     - Mountains should be sharp peaks, not wide plateaus
     - Exception: User explicitly says "very large mountain range" → 0.15~0.3
   - Plains/Deserts/Forests: Normal coverage = 0.25~0.35
   - Lakes/Swamps: Small to medium = 0.15~0.25
5. Erosion guidelines:
   - 🏔️ **Mountains**: High erosion (0.7~0.9) for rugged, rocky appearance
   - 🌾 **Plains/Grasslands/Deserts**: Low erosion (0.1~0.2) for gentle rolling terrain
   - 🌲 **Forests**: Medium erosion (0.3~0.5) for hilly woodland
   - 🏞️ **Perfect flat terrain**: ONLY when user explicitly requests "완벽한 평지" or "perfectly flat" → erosion = 0.0
6. Continentalness & Water guidelines:
   - 🌊 **Shallow water (lakes, ponds, rivers)**: continentalness = -0.1 ~ -0.3 (slightly below ground level)
     - Use -0.1 for very shallow water, -0.3 for deeper lakes
     - NEVER use -0.8 unless user explicitly says "deep ocean" or "very deep water"
   - 🏞️ **Swamps/Marshlands**: continentalness = 0.0, erosion = 0.3
     - Ground level but with erosion to create natural puddles and uneven terrain
     - Multiple small water pools will form naturally from erosion
   - 🌊 **Deep ocean**: continentalness = -0.8 ~ -1.0 (ONLY if user explicitly requests)
7. Blend distance: Natural transitions = 15~20, Sharp boundaries = 5~10
8. Use preset biomes when possible, but feel free to customize parameters
9. Boundary blending creates automatic transition biomes (plains + lake → beach)

**Examples:**

User: "왼쪽은 눈 덮인 산맥, 중앙은 초원, 오른쪽은 사막"
AI Response:
{
  "biome_points": [
    {
      "position": [15, 50],
      "biome_params": { /* snowy_mountain preset */ },
      "coverage": 0.1,  // 🏔️ Mountain: small coverage for sharp peak
      "description": "snowy_mountain"
    },
    {
      "position": [50, 50],
      "biome_params": { /* plains preset */ },
      "coverage": 0.35,  // Plains: normal coverage
      "description": "plains"
    },
    {
      "position": [85, 50],
      "biome_params": { /* desert preset */ },
      "coverage": 0.3,  // Desert: normal coverage
      "description": "desert"
    }
  ],
  "blend_distance": 15
}

User: "중앙에 호수, 주변은 숲"
AI Response:
{
  "biome_points": [
    {
      "position": [50, 50],
      "biome_params": { /* lake preset */ },
      "coverage": 0.2,
      "description": "lake"
    },
    {
      "position": [30, 70],
      "biome_params": { /* forest preset */ },
      "coverage": 0.3,
      "description": "forest_north"
    },
    {
      "position": [70, 70],
      "biome_params": { /* forest preset */ },
      "coverage": 0.3,
      "description": "forest_northeast"
    },
    {
      "position": [30, 30],
      "biome_params": { /* forest preset */ },
      "coverage": 0.3,
      "description": "forest_south"
    },
    {
      "position": [70, 30],
      "biome_params": { /* forest preset */ },
      "coverage": 0.3,
      "description": "forest_southeast"
    }
  ],
  "blend_distance": 20
}

Now respond ONLY with valid JSON for the following user description:`;
/**
 * Claude AI를 사용하여 자연어 설명에서 바이옴 레이아웃 생성
 */
async function generateBiomeLayout(description) {
    if (!process.env.ANTHROPIC_API_KEY) {
        throw new Error('ANTHROPIC_API_KEY is not set');
    }
    try {
        const message = await anthropic.messages.create({
            model: 'claude-sonnet-4-5-20250929',
            max_tokens: 4096,
            messages: [
                {
                    role: 'user',
                    content: `${BIOME_GENERATION_PROMPT}\n\n"${description}"`
                }
            ]
        });
        const responseText = message.content[0].type === 'text' ? message.content[0].text : '';
        // JSON 추출 (```json ... ``` 형식 또는 바로 JSON)
        let jsonText = responseText.trim();
        // Markdown 코드 블록 제거
        if (jsonText.startsWith('```json')) {
            jsonText = jsonText.replace(/^```json\s*/, '').replace(/\s*```$/, '');
        }
        else if (jsonText.startsWith('```')) {
            jsonText = jsonText.replace(/^```\s*/, '').replace(/\s*```$/, '');
        }
        const biomeLayout = JSON.parse(jsonText);
        // 유효성 검사
        if (!biomeLayout.biome_points || biomeLayout.biome_points.length === 0) {
            throw new Error('No biome points generated');
        }
        // 각 바이옴 포인트 유효성 검사
        for (const point of biomeLayout.biome_points) {
            if (!point.position || point.position.length !== 2) {
                throw new Error(`Invalid position for biome point: ${JSON.stringify(point)}`);
            }
            const [x, y] = point.position;
            if (x < 0 || x > 100 || y < 0 || y > 100) {
                throw new Error(`Position out of bounds (0~100): [${x}, ${y}]`);
            }
            if (!point.biome_params) {
                throw new Error(`Missing biome_params for point: ${JSON.stringify(point)}`);
            }
            // 모든 필수 파라미터 확인
            const requiredParams = [
                'temperature', 'humidity', 'erosion', 'continentalness', 'weirdness',
                'vegetation_color_r', 'vegetation_color_g', 'vegetation_color_b',
                'ground_color_r', 'ground_color_g', 'ground_color_b',
                'rock_color_r', 'rock_color_g', 'rock_color_b',
                'snow_start_height', 'rock_exposure'
            ];
            for (const param of requiredParams) {
                if (!(param in point.biome_params)) {
                    throw new Error(`Missing parameter '${param}' in biome_params`);
                }
            }
            // Coverage 범위 자동 보정 (에러 대신 clamp)
            if (point.coverage < 0.1) {
                console.warn(`[Biome] Coverage ${point.coverage} too low, clamping to 0.1`);
                point.coverage = 0.1;
            }
            else if (point.coverage > 1.0) {
                console.warn(`[Biome] Coverage ${point.coverage} too high, clamping to 1.0`);
                point.coverage = 1.0;
            }
        }
        // blend_distance 기본값
        if (!biomeLayout.blend_distance) {
            biomeLayout.blend_distance = 15;
        }
        return biomeLayout;
    }
    catch (error) {
        if (error instanceof SyntaxError) {
            throw new Error(`Failed to parse Claude response as JSON: ${error.message}`);
        }
        throw error;
    }
}
/**
 * 프리셋 바이옴을 사용하여 간단한 레이아웃 생성 (Claude AI 없이)
 */
function createSimpleBiomeLayout(biomeIds, positions, coverages) {
    if (biomeIds.length !== positions.length) {
        throw new Error('biomeIds and positions must have the same length');
    }
    const biome_points = biomeIds.map((biomeId, index) => {
        const preset = biome_1.PRESET_BIOMES_V1[biomeId];
        if (!preset) {
            throw new Error(`Unknown biome preset: ${biomeId}`);
        }
        return {
            position: positions[index],
            biome_params: preset.params,
            coverage: coverages?.[index] ?? 0.25,
            description: preset.id
        };
    });
    return {
        biome_points,
        blend_distance: 15
    };
}
/**
 * 바이옴 레이아웃을 JSON 파일로 저장할 형식으로 변환
 */
function biomeLayoutToJSON(layout) {
    return JSON.stringify(layout, null, 2);
}
