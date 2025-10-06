import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || ''
});

export interface TerrainParameters {
  scale: number;
  roughness: number;
  features?: string[];
  description: string;
}

export async function analyzeTerrainDescription(description: string): Promise<TerrainParameters> {
  try {
    const response = await client.messages.create({
      model: 'claude-sonnet-4-5-20250929',
      max_tokens: 1024,
      messages: [{
        role: 'user',
        content: `You are a terrain parameter expert. Analyze the Korean terrain description and convert it to Blender terrain parameters.

User's description: "${description}"

Please respond ONLY with a JSON object (no other text):
{
  "scale": (number 5-50, terrain size. Tall mountains=35-45, Medium mountains=20-30, Small hills=10-15, Flat=5-10),
  "roughness": (number 0-1, surface roughness. Rocky/Jagged=0.8-0.95, Mountainous=0.6-0.8, Rolling hills=0.3-0.5, Smooth/Flat=0.1-0.3),
  "features": (array of strings like "peaks", "valleys", "snow", "rocky", "smooth", "jagged", "ridges"),
  "description": (Korean summary of the terrain in one sentence)
}

Important:
- "눈 덮인", "높은", "산" means snowy, tall mountains → high scale (35-45), high roughness (0.7-0.9)
- "바위산", "험준한" means rocky, rugged → high roughness (0.8-0.95)
- "언덕", "구릉" means hills → medium scale (10-20), medium roughness (0.4-0.6)
- "평지", "평평한" means flat → low scale (5-10), low roughness (0.1-0.3)`
      }]
    });

    const text = response.content[0].type === 'text' ? response.content[0].text : '';

    // JSON 추출 (코드 블록이 있을 수 있음)
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('Failed to parse Claude response');
    }

    const params = JSON.parse(jsonMatch[0]);

    // 값 검증 및 기본값 설정
    return {
      scale: Math.max(5, Math.min(50, params.scale || 15)),
      roughness: Math.max(0, Math.min(1, params.roughness || 0.7)),
      features: params.features || [],
      description: params.description || description
    };

  } catch (error: any) {
    console.error('[Claude] Analysis failed:', error.message);

    // Fallback: 기본 파라미터 반환
    return {
      scale: 15,
      roughness: 0.7,
      features: [],
      description: description
    };
  }
}
