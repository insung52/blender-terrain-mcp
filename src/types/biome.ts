/**
 * 바이옴 파라미터 시스템 (V1)
 * terrain_upgrade.md 기반
 */

/**
 * V1 바이옴 파라미터 (16개 - 모두 수치형)
 */
export interface BiomeParametersV1 {
  // === 핵심 지형 파라미터 (5개) ===
  temperature: number;      // -1.0 ~ 1.0 (극한 추위 ~ 작열)
  humidity: number;         // 0.0 ~ 1.0 (건조 ~ 열대)
  erosion: number;          // 0.0 ~ 1.0 (평평 ~ 험준)
  continentalness: number;  // -1.0 ~ 1.0 (바다 ~ 고원)
  weirdness: number;        // 0.0 ~ 1.0 (일반 ~ 특이)

  // === 시각 파라미터 (9개) ===
  vegetation_color_r: number;   // 0.0 ~ 1.0 (식생 R)
  vegetation_color_g: number;   // 0.0 ~ 1.0 (식생 G)
  vegetation_color_b: number;   // 0.0 ~ 1.0 (식생 B)

  ground_color_r: number;       // 0.0 ~ 1.0 (지표 R)
  ground_color_g: number;       // 0.0 ~ 1.0 (지표 G)
  ground_color_b: number;       // 0.0 ~ 1.0 (지표 B)

  rock_color_r: number;         // 0.0 ~ 1.0 (바위 R) - 경사진 곳에 노출
  rock_color_g: number;         // 0.0 ~ 1.0 (바위 G)
  rock_color_b: number;         // 0.0 ~ 1.0 (바위 B)

  // === 추가 파라미터 (2개) ===
  snow_start_height: number;    // 0 ~ 5000 (눈 시작 높이, 미터)
  rock_exposure: number;        // 0.0 ~ 1.0 (바위 노출도)
}

/**
 * 바이옴 포인트 (Claude AI가 생성)
 */
export interface BiomePoint {
  position: [number, number];  // 100x100 좌표계 상의 위치 [x, y]
  biome_params: BiomeParametersV1;
  coverage: number;            // 0.1 ~ 1.0 (영향력 반경)
  description: string;         // 설명 (예: "snowy_mountain")
}

/**
 * Claude AI 출력 형식
 */
export interface BiomeLayout {
  biome_points: BiomePoint[];
  blend_distance: number;      // 블렌딩 거리 (미터)
}

/**
 * 100x100 바이옴 파라미터 맵
 */
export type BiomeParameterMap = BiomeParametersV1[][];  // [y][x]

/**
 * 바이옴 프리셋
 */
export interface BiomePreset {
  id: string;
  name: string;
  params: BiomeParametersV1;
  description?: string;
}

/**
 * 사전 정의된 바이옴 프리셋 (V1)
 */
export const PRESET_BIOMES_V1: Record<string, BiomePreset> = {
  snowy_mountain: {
    id: 'snowy_mountain',
    name: 'Snowy Mountain',
    params: {
      // 핵심 지형
      temperature: -0.7,
      humidity: 0.4,
      erosion: 0.8,
      continentalness: 0.6,
      weirdness: 0.3,
      // 시각
      vegetation_color_r: 0.2,
      vegetation_color_g: 0.3,
      vegetation_color_b: 0.2,
      ground_color_r: 0.4,
      ground_color_g: 0.4,
      ground_color_b: 0.45,
      rock_color_r: 0.5,      // 🪨 회색-갈색 바위 (차가운 산)
      rock_color_g: 0.48,
      rock_color_b: 0.45,
      // 추가
      snow_start_height: 750,  // 50% 낮춤 (1500 → 750)
      rock_exposure: 0.7
    },
    description: '눈 덮인 험준한 산맥'
  },

  desert: {
    id: 'desert',
    name: 'Desert',
    params: {
      temperature: 0.9,
      humidity: 0.1,
      erosion: 0.3,
      continentalness: 0.5,
      weirdness: 0.1,
      vegetation_color_r: 0.4,
      vegetation_color_g: 0.4,
      vegetation_color_b: 0.2,
      ground_color_r: 0.9,
      ground_color_g: 0.8,
      ground_color_b: 0.6,
      rock_color_r: 0.7,      // 🪨 붉은-갈색 사암 (따뜻한 사막)
      rock_color_g: 0.55,
      rock_color_b: 0.4,
      snow_start_height: 9999,  // 눈 없음
      rock_exposure: 0.3
    },
    description: '뜨겁고 건조한 사막'
  },

  plains: {
    id: 'plains',
    name: 'Plains',
    params: {
      temperature: 0.5,
      humidity: 0.6,
      erosion: 0.2,
      continentalness: 0.3,
      weirdness: 0.0,
      vegetation_color_r: 0.3,
      vegetation_color_g: 0.6,
      vegetation_color_b: 0.2,
      ground_color_r: 0.3,      // 🟢 초록색 잔디밭 (vegetation_color와 동일)
      ground_color_g: 0.6,      // 🟢 잔디가 덮인 평원
      ground_color_b: 0.2,      // 🟢 GREEN
      rock_color_r: 0.45,     // 🪨 갈색 암석 (평원)
      rock_color_g: 0.4,
      rock_color_b: 0.35,
      snow_start_height: 9999,
      rock_exposure: 0.1
    },
    description: '평화로운 평원'
  },

  lake: {
    id: 'lake',
    name: 'Lake',
    params: {
      temperature: 0.3,
      humidity: 1.0,
      erosion: 0.0,
      continentalness: -0.8,
      weirdness: 0.0,
      vegetation_color_r: 0.2,
      vegetation_color_g: 0.4,
      vegetation_color_b: 0.3,
      ground_color_r: 0.4,      // 🟫 호수 바닥 흙색 (갈색) - 물은 별도 메시
      ground_color_g: 0.35,     // 🟫 BROWN SOIL
      ground_color_b: 0.25,     // 🟫 투명한 물 메시 아래 보임
      rock_color_r: 0.3,        // 🪨 어두운 회색 암석 (물가)
      rock_color_g: 0.3,
      rock_color_b: 0.35,
      snow_start_height: 9999,
      rock_exposure: 0.0
    },
    description: '차가운 호수'
  },

  forest: {
    id: 'forest',
    name: 'Forest',
    params: {
      temperature: 0.4,
      humidity: 0.8,
      erosion: 0.4,
      continentalness: 0.2,
      weirdness: 0.2,
      vegetation_color_r: 0.2,
      vegetation_color_g: 0.5,
      vegetation_color_b: 0.2,
      ground_color_r: 0.25,     // 🟢 어두운 초록 (숲 바닥의 풀/이끼)
      ground_color_g: 0.4,      // 🟢 약간 어두운 초록색
      ground_color_b: 0.2,      // 🟢 DARK GREEN
      rock_color_r: 0.4,      // 🪨 이끼 낀 어두운 바위 (숲)
      rock_color_g: 0.38,
      rock_color_b: 0.3,
      snow_start_height: 9999,
      rock_exposure: 0.2
    },
    description: '울창한 숲'
  }
};
