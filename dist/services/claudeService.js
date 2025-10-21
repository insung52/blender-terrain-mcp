"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.analyzeTerrainDescription = analyzeTerrainDescription;
const sdk_1 = __importDefault(require("@anthropic-ai/sdk"));
const client = new sdk_1.default({
    apiKey: process.env.ANTHROPIC_API_KEY || ''
});
async function analyzeTerrainDescription(description) {
    try {
        const response = await client.messages.create({
            model: 'claude-sonnet-4-5-20250929',
            max_tokens: 2048,
            messages: [{
                    role: 'user',
                    content: `You are an expert 3D terrain generation system. Analyze the terrain description (Korean or English) and extract ALL detailed parameters for procedural terrain generation in Blender.

User's terrain description: "${description}"

Respond with ONLY a JSON object containing ALL these parameters (no other text, no markdown):

{
  "base_scale": <number 5-50, overall terrain size. Himalayas=45, Mountains=30-40, Hills=15-25, Flat=5-10>,
  "base_roughness": <number 0-1, surface detail. Very rough=0.9, Rough=0.7, Moderate=0.5, Smooth=0.3>,
  "height_multiplier": <number 5-100, max height in meters. Everest=80-100, Mountains=40-60, Hills=15-30, Flat=5-10>,

  "noise_type": <"MUSGRAVE" | "PERLIN" | "VORONOI". MUSGRAVE=complex mountains, PERLIN=smooth hills, VORONOI=sharp rocks>,
  "noise_layers": <number 1-5, detail layers. Very detailed=5, Detailed=3, Simple=1>,
  "octaves": <number 1-10, noise complexity. Very complex=8-10, Normal=5-7, Simple=2-4>,

  "peak_sharpness": <number 0-1, how sharp are peaks. Sharp needles=0.9, Mountains=0.6, Round hills=0.2>,
  "valley_depth": <number 0-1, how deep are valleys. Deep canyons=0.9, Normal valleys=0.5, Shallow=0.2>,
  "erosion": <number 0-1, weathering effect. Heavily eroded=0.8, Moderate=0.4, Young=0.1>,
  "terrace_levels": <number 0-10, step-like terraces. Rice terraces=5-8, None=0>,

  "snow_height": <number 0-1, DEPRECATED - use snow_absolute_height instead>,
  "rock_height": <number 0-1, DEPRECATED - use rock_absolute_height instead>,
  "grass_height": <number 0-1, DEPRECATED - use grass_absolute_height instead>,

  "snow_absolute_height": <number in meters, snow appears ABOVE this height. Snowy plains=0-10, Mountains=1500-2500, Everest=5000-8000, No snow=9999>,
  "rock_absolute_height": <number in meters, exposed rock appears ABOVE this height. Always rock=0, High mountains=1000-1500, Never=9999>,
  "grass_absolute_height": <number in meters, vegetation appears BELOW this height. Always grass=9999, Mid elevation=500-1000, Barren=0>,

  "snow_color": <[R, G, B] each 0-1. Pure white=[0.95, 0.95, 1.0], Dirty=[0.8, 0.8, 0.85]>,
  "rock_color": <[R, G, B]. Dark gray=[0.3, 0.3, 0.35], Brown=[0.4, 0.35, 0.3], Red=[0.5, 0.3, 0.25]>,
  "grass_color": <[R, G, B]. Lush green=[0.2, 0.5, 0.15], Dry=[0.4, 0.4, 0.2], Desert=[0.6, 0.5, 0.3], Red=[0.8, 0.1, 0.1], Blue=[0.1, 0.3, 0.8], Yellow=[0.8, 0.8, 0.1]>,

  "climate": <"arctic" | "temperate" | "desert" | "volcanic" | "alien">,
  "wetness": <number 0-1, surface reflectivity. Wet/rainy=0.7, Normal=0.3, Dry=0.1>,
  "vegetation_density": <number 0-1, for future use. Dense=0.8, Sparse=0.2, None=0>,

  "noise_seed": <random integer 0-999999, different seed = different terrain shape with same parameters>,

  "description": <Korean one-sentence summary of the terrain>
}

EXAMPLES:

"눈 덮인 매우 높은 산" →
{
  "base_scale": 42, "base_roughness": 0.85, "height_multiplier": 75,
  "noise_type": "MUSGRAVE", "noise_layers": 4, "octaves": 8,
  "peak_sharpness": 0.8, "valley_depth": 0.6, "erosion": 0.3, "terrace_levels": 0,
  "snow_height": 0.5, "rock_height": 0.3, "grass_height": 0.0,
  "snow_absolute_height": 40, "rock_absolute_height": 20, "grass_absolute_height": 15,
  "snow_color": [0.95, 0.95, 1.0], "rock_color": [0.3, 0.3, 0.35], "grass_color": [0.25, 0.45, 0.15],
  "climate": "arctic", "wetness": 0.2, "vegetation_density": 0.1,
  "noise_seed": 42857,
  "description": "눈으로 덮인 험준한 고산 지형"
}

"부드러운 초원 언덕" →
{
  "base_scale": 18, "base_roughness": 0.4, "height_multiplier": 20,
  "noise_type": "PERLIN", "noise_layers": 2, "octaves": 4,
  "peak_sharpness": 0.2, "valley_depth": 0.3, "erosion": 0.5, "terrace_levels": 0,
  "snow_height": 1.0, "rock_height": 1.0, "grass_height": 0.0,
  "snow_absolute_height": 9999, "rock_absolute_height": 9999, "grass_absolute_height": 9999,
  "snow_color": [0.95, 0.95, 1.0], "rock_color": [0.4, 0.35, 0.3], "grass_color": [0.2, 0.5, 0.1],
  "climate": "temperate", "wetness": 0.4, "vegetation_density": 0.7,
  "noise_seed": 12345,
  "description": "완만하고 푸른 초원 구릉지"
}

"화산 지형" →
{
  "base_scale": 35, "base_roughness": 0.75, "height_multiplier": 50,
  "noise_type": "VORONOI", "noise_layers": 3, "octaves": 6,
  "peak_sharpness": 0.9, "valley_depth": 0.7, "erosion": 0.2, "terrace_levels": 0,
  "snow_height": 1.0, "rock_height": 0.0, "grass_height": 0.0,
  "snow_absolute_height": 9999, "rock_absolute_height": 0, "grass_absolute_height": 0,
  "snow_color": [0.95, 0.95, 1.0], "rock_color": [0.15, 0.1, 0.1], "grass_color": [0.3, 0.25, 0.2],
  "climate": "volcanic", "wetness": 0.1, "vegetation_density": 0.0,
  "noise_seed": 78901,
  "description": "날카롭고 어두운 화산암 지형"
}

KEY TRANSLATIONS:
- "눈 덮인/설산" = snowy → snow_absolute_height based on terrain type: Plains=0-10m, Hills=20-30m, Mountains=40-60m, High mountains=30-50m
- "높은/고산" = tall → height_multiplier=60-100, peak_sharpness=0.7-0.9
- "험준한/바위" = rugged/rocky → base_roughness=0.8-0.95, rock_absolute_height=10-30m
- "부드러운/완만한" = smooth → base_roughness=0.3-0.5, peak_sharpness=0.1-0.3
- "계곡/협곡" = valley/canyon → valley_depth=0.7-0.9
- "사막" = desert → climate="desert", grass_absolute_height=0m (no vegetation)
- "화산" = volcanic → climate="volcanic", rock_color=[0.15, 0.1, 0.1], rock_absolute_height=0m (all rock)
- "평지/초원" = plains/grassland → snow_absolute_height=9999 (never snows unless "눈내린" specified), grass_absolute_height=9999 (grass everywhere)

ABSOLUTE HEIGHT LOGIC:
- Snow: If terrain mentions "눈" or "snow", calculate snow_absolute_height based on terrain scale. Flat snowy terrain=0-10m. Mountain peaks=height_multiplier*0.5 to 0.7. No mention of snow=9999.
- Rock: Exposed rock appears above this height. Mountains: 20-40m. Rocky terrain: 0m (rock everywhere). Grassy terrain: 9999m (no exposed rock).
- Grass: Vegetation below this height. Grasslands: 9999m (grass everywhere). Barren/desert: 0m (no vegetation). Mountains: height_multiplier*0.2 to 0.4.

RANDOMNESS:
- ALWAYS generate a different random noise_seed (0-999999) for each request. This ensures identical prompts create different-looking terrains.

COLOR INSTRUCTIONS: If user specifies unusual colors (e.g., "빨간색 잔디", "파란 바위"), ALWAYS apply that exact color to the respective material (grass_color, rock_color, snow_color). Convert Korean color names to RGB: 빨간색=red=[0.8,0.1,0.1], 파란색=blue=[0.1,0.3,0.8], 노란색=yellow=[0.8,0.8,0.1], 보라색=purple=[0.6,0.1,0.6], 분홍색=pink=[0.9,0.4,0.6], 주황색=orange=[0.9,0.5,0.1]

Now analyze: "${description}"`
                }]
        });
        const text = response.content[0].type === 'text' ? response.content[0].text : '';
        // JSON 추출
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            throw new Error('Failed to parse Claude response');
        }
        const params = JSON.parse(jsonMatch[0]);
        // 값 검증 및 기본값 설정 (v3.0)
        return {
            // 기본 파라미터 (하위 호환)
            scale: params.base_scale || params.scale || 20,
            roughness: params.base_roughness || params.roughness || 0.7,
            // v2.0 파라미터
            base_scale: Math.max(5, Math.min(50, params.base_scale || 20)),
            base_roughness: Math.max(0, Math.min(1, params.base_roughness || 0.7)),
            height_multiplier: Math.max(5, Math.min(100, params.height_multiplier || 30)),
            noise_type: params.noise_type || 'MUSGRAVE',
            noise_layers: Math.max(1, Math.min(5, params.noise_layers || 3)),
            octaves: Math.max(1, Math.min(10, params.octaves || 6)),
            peak_sharpness: Math.max(0, Math.min(1, params.peak_sharpness || 0.5)),
            valley_depth: Math.max(0, Math.min(1, params.valley_depth || 0.5)),
            erosion: Math.max(0, Math.min(1, params.erosion || 0.3)),
            terrace_levels: Math.max(0, Math.min(10, params.terrace_levels || 0)),
            // Deprecated relative heights (kept for backward compatibility)
            snow_height: Math.max(0, Math.min(1, params.snow_height || 0.7)),
            rock_height: Math.max(0, Math.min(1, params.rock_height || 0.3)),
            grass_height: Math.max(0, Math.min(1, params.grass_height || 0.0)),
            // v3.0: Absolute height thresholds
            snow_absolute_height: Math.max(0, Math.min(10000, params.snow_absolute_height || 9999)),
            rock_absolute_height: Math.max(0, Math.min(10000, params.rock_absolute_height || 9999)),
            grass_absolute_height: Math.max(0, Math.min(10000, params.grass_absolute_height || 9999)),
            snow_color: params.snow_color || [0.95, 0.95, 1.0],
            rock_color: params.rock_color || [0.3, 0.3, 0.35],
            grass_color: params.grass_color || [0.2, 0.4, 0.1],
            climate: params.climate || 'temperate',
            wetness: Math.max(0, Math.min(1, params.wetness || 0.3)),
            vegetation_density: Math.max(0, Math.min(1, params.vegetation_density || 0.3)),
            noise_seed: Math.floor(Math.random() * 999999),
            description: params.description || description,
            features: params.features || []
        };
    }
    catch (error) {
        console.error('[Claude] Analysis failed:', error.message);
        // Fallback: 기본 파라미터 반환
        return {
            scale: 20,
            roughness: 0.7,
            base_scale: 20,
            base_roughness: 0.7,
            height_multiplier: 30,
            noise_type: 'MUSGRAVE',
            noise_layers: 3,
            octaves: 6,
            peak_sharpness: 0.5,
            valley_depth: 0.5,
            erosion: 0.3,
            terrace_levels: 0,
            snow_height: 0.7,
            rock_height: 0.3,
            grass_height: 0.0,
            snow_absolute_height: 9999,
            rock_absolute_height: 9999,
            grass_absolute_height: 9999,
            snow_color: [0.95, 0.95, 1.0],
            rock_color: [0.3, 0.3, 0.35],
            grass_color: [0.2, 0.4, 0.1],
            climate: 'temperate',
            wetness: 0.3,
            vegetation_density: 0.3,
            noise_seed: Math.floor(Math.random() * 999999),
            description: description,
            features: []
        };
    }
}
