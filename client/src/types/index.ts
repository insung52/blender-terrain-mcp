export interface Terrain {
  id: string;
  scale: number;
  roughness: number;
  description: string;
  createdAt: string;
  blendFilePath: string;
  topViewPath?: string;
  metadata?: any;
}

export interface Road {
  id: string;
  terrainId: string;
  controlPoints: any[];
  blendFilePath: string;
  previewPath?: string;
  widthMeters: number;
  metadata?: any;
  createdAt: string;
  terrain?: {
    id: string;
    description: string;
  };
}

export interface Objects {
  id: string;
  terrainId: string;
  roadId?: string;
  objectCount: number;
  blendFilePath: string;
  previewPath: string;
  createdAt: string;
  metadata?: {
    status?: string;
    requestedCount?: number;
    actualCount?: number;
    jobId?: string;
    error?: string;
  };
  terrain?: {
    id: string;
    description: string;
  };
  road?: {
    id: string;
  };
}

export interface Job {
  id: string;
  type: string;
  status: string;
  createdAt: string;
  completedAt?: string;
  outputPath?: string;
  previewPath?: string;
  terrain?: Terrain;
  road?: Road;
  result?: {
    preview?: string;
    blendFile?: string;
  };
}
