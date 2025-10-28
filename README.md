# 🏔️ Blender Terrain MCP - AI-Powered 3D Terrain Generator

A full-stack web application for generating realistic 3D terrains with AI-powered biome layouts, road systems, and object placement.

![Terrain Gallery](assets/md/1019.png)

## 🌟 Features

### 🎨 AI-Powered Biome Terrain Generation
- **Natural Language Input** → Claude AI analyzes and creates biome layouts
- **16 Biome Parameters**: temperature, humidity, erosion, continentalness, weirdness + RGB colors for vegetation/ground + snow/rock exposure
- **Weighted Voronoi Diagram (WVD)**: Coverage-based biome distribution with randomized boundaries
- **16-bit PNG Maps**: 0.76cm precision (vs 2m steps with 8-bit)
- **Multi-Octave Noise**: 6-layer detail (continent → rock surface)
- **Gaussian Blur Blending**: Natural transitions between biomes

**Example Input:**
```
"위쪽은 높은 산, 왼쪽아래에는 초록색 평지, 오른쪽 아래에는 사막, 중앙에는 작은 호수"
```

**AI Generates:**
- 🏔️ Snowy Mountain (top): continentalness=0.6, erosion=0.8
- 🌾 Plains (bottom-left): continentalness=0.3, erosion=0.2
- 🏜️ Desert (bottom-right): continentalness=0.5, erosion=0.3
- 💧 Lake (center): continentalness=-0.2, erosion=0.0

### 🛣️ Road Generation System
- **Interactive Canvas Drawing**: Click or draw road paths directly on terrain preview
- **Curve Interpolation**: Smooth Catmull-Rom spline curves
- **Terrain Following**: Automatic height adjustment to terrain surface
- **Road Mesh**: 3D road geometry with customizable width
- **Modifiers**: Decimate + Subdivision for smooth appearance

### 🌲 Biome-Based Object Placement
- **Weight-Based Distribution**: Trees, flowers, rocks placed according to biome parameters
- **Density Control**: Temperature, humidity, vegetation density maps
- **Exclusion Zones**: Automatic avoidance of water areas and roads
- **Variety**: Multiple object types per category with random selection
- **Real-time Progress**: Live progress monitoring with ETA during placement

### 📊 Real-Time Progress Monitoring (SSE)
- **Server-Sent Events**: Live progress updates for long-running operations
- **Multi-Step Tracking**:
  - Terrain: Biome analysis → Biome maps → 3D mesh → Preview render
  - Objects: Placement with current/total count and ETA
- **Auto-Reconnect**: Page refresh support with localStorage persistence
- **Visual Feedback**: Progress bars, step status, estimated time remaining

### 🎮 Three Gallery System

#### 1️⃣ Terrain Gallery
- Create terrains with AI biome generation or manual parameters
- Preview images with processing status indicators
- Download as .blend or .glb (GLB auto-converts with texture baking)
- Add roads to existing terrains
- Delete terrains and associated files

#### 2️⃣ Road Gallery
- View all created roads with terrain associations
- Preview images showing road paths
- Add objects (trees, rocks, flowers) to roads
- Download road files (.blend/.glb)
- Delete roads

#### 3️⃣ Objects Gallery
- View object placement results
- Object count and metadata display
- Download object files (.blend/.glb)
- Processing state with "Show Progress" button
- Auto-refresh on completion

## 🏗️ Architecture

### Technology Stack

**Backend:**
- Node.js + Express
- TypeScript
- Prisma (MySQL)
- Bull Queue (Redis)
- Server-Sent Events (SSE)

**Frontend:**
- React + TypeScript
- Vite
- Canvas API for road drawing

**3D Processing:**
- Blender 4.5 (headless)
- Python scripts for terrain/road/object generation
- GLTF/GLB export with texture baking

**AI:**
- Claude API (Anthropic) for biome layout generation

### System Flow

```
User Input → API → Job Queue → Blender Scripts → Database
                ↓
           SSE Progress Updates
                ↓
           Frontend Live UI
```

## 🚀 Setup & Installation

### Prerequisites

1. **Node.js** (v18+)
2. **MySQL** (v8+)
3. **Redis** (v6+)
4. **Blender** (v4.2+)
5. **Python** (v3.10+, included with Blender)
6. **Claude API Key** (from Anthropic)

### Installation Steps

#### 1. Clone Repository
```bash
git clone <repository-url>
cd blender-terrain-mcp
```

#### 2. Install Dependencies

**Server:**
```bash
npm install
```

**Client:**
```bash
cd client
npm install
cd ..
```

#### 3. Database Setup

**Start MySQL:**
```bash
# Windows (if using XAMPP/WAMP)
# Start MySQL from control panel

# Or install MySQL and start service
```

**Create Database:**
```sql
CREATE DATABASE blender_terrain;
```

**Run Migrations:**
```bash
npx prisma migrate dev
```

#### 4. Redis Setup

**Install Redis:**
```bash
# Windows: Download from https://github.com/microsoftarchive/redis/releases
# Or use WSL/Docker

# Start Redis
redis-server
```

#### 5. Environment Configuration

Create `.env` file in project root:
```env
DATABASE_URL="mysql://root:password@localhost:3306/blender_terrain"
ANTHROPIC_API_KEY="your-claude-api-key-here"
```

#### 6. Blender Path Configuration

Edit `src/config.ts`:
```typescript
export const config = {
  blenderPath: 'C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe',
  blenderScriptsDir: path.join(__dirname, 'blender-scripts'),
  outputDir: path.join(process.cwd(), 'output')
};
```

#### 7. Assets Setup

Place 3D assets (.blend files) in `assets/` directory:
```
assets/
├── trees/
│   ├── tree1.blend
│   ├── tree2.blend
│   └── ...
├── flowers/
│   ├── flower1.blend
│   └── ...
└── rocks/
    ├── rock1.blend
    └── ...
```

Edit object spawn configuration:
```bash
# Edit src/blender-scripts/object_spawn_config.json
```

## 🎯 Running the Application

### Development Mode

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - Backend:**
```bash
npm run dev
```

**Terminal 3 - Frontend:**
```bash
cd client
npm run dev
```

**Terminal 4 - Queue Worker:**
```bash
npm run worker
```

Access application at: `http://localhost:5173`

### Production Mode

**Build:**
```bash
# Build server
npm run build

# Build client
cd client
npm run build
cd ..
```

**Run:**
```bash
# Start Redis
redis-server

# Start server (serves both API and static frontend)
npm start
```

Access application at: `http://localhost:3000`

## 📖 Usage Guide

### Creating a Terrain

1. Navigate to **Terrain Gallery** tab
2. Enter description in Korean (e.g., "눈 덮인 높은 산맥")
3. Check **"Use Claude AI to analyze description"**
4. Click **"Generate Terrain"**
5. Progress modal opens automatically
6. Wait for completion (2-5 minutes)
7. View terrain in gallery

### Adding Roads

1. In **Terrain Gallery**, click **"🛣️ Add Road"** on a completed terrain
2. **Option A - Manual Input:**
   - Enter control points as JSON array: `[[10,10],[50,80],[90,30]]`
   - Click **"Create Road"**

3. **Option B - Canvas Drawing:**
   - Click **"🎨 Draw on Canvas"**
   - Click points on terrain preview to draw road path
   - Click **"Create Road"**

4. Monitor progress in modal
5. View road in **Road Gallery**

### Adding Objects

1. In **Road Gallery**, click **"🌲 오브젝트 생성"** on a road
2. Enter object count (recommended: 50-200)
3. Automatically switches to **Objects Gallery**
4. Progress modal shows live placement updates
5. View completed objects in gallery

### Downloading

- **Terrain/Road/Objects**: Click **"📦 Blend"** for Blender file
- **GLB Export**: Click **"📥 GLB"**
  - First click: Converts .blend → .glb (may take 1-2 minutes)
  - Subsequent clicks: Instant download (cached)
  - Includes baked diffuse textures
  - Removes hidden cache objects

## 🔧 Technical Details

### Terrain Generation Pipeline

1. **Biome Analysis** (Claude AI)
   - Parse natural language description
   - Identify biome types and locations
   - Assign parameters (temperature, humidity, erosion, etc.)

2. **Biome Map Generation** (Python/NumPy)
   - Weighted Voronoi Diagram for coverage-based distribution
   - Gaussian blur for smooth transitions
   - 16 parameter maps saved as 16-bit PNG

3. **3D Mesh Creation** (Blender)
   - Load biome maps as textures
   - Multi-octave noise displacement (6 layers)
   - Erosion squaring for mountain-valley definition
   - Slope-based rock exposure
   - Vertex color painting for biomes

4. **Preview Render** (Blender)
   - Top-down orthographic camera
   - Rendered to PNG for gallery display

### Object Placement Algorithm

1. **Biome Analysis**
   - Read temperature, humidity, vegetation density maps
   - Identify water areas (blue pixels)
   - Calculate placement probabilities

2. **Weighted Selection**
   - Trees: High vegetation density + moderate temperature
   - Flowers: High humidity + low rock exposure
   - Rocks: High rock exposure + low vegetation

3. **Position Sampling**
   - Random UV coordinates within terrain bounds
   - Check biome suitability at position
   - Raycast to terrain surface for Z-height

4. **Object Instantiation**
   - Load .blend asset via library linking
   - Apply random rotation/scale
   - Snap to terrain surface

5. **Progress Logging**
   - Write `[PROGRESS]` lines to log file
   - Server tail-reads log every 1 second
   - Broadcasts progress via SSE to client

### GLB Export Process

1. **Texture Baking**
   - Bake diffuse color to 2048x2048 image texture
   - Create/verify UV maps (Smart UV Project if missing)
   - Cycles renderer, 16 samples for speed

2. **Material Simplification**
   - Replace complex node tree
   - Simple setup: Image Texture → Principled BSDF → Output

3. **Cache Cleanup**
   - Remove hidden objects at (0, 0, -1000)
   - Delete original meshes used for linked asset instances

4. **GLTF Export**
   - Format: GLB (binary)
   - Include: Textures, Normals, UVs
   - Exclude: Cameras, Lights

## 📁 Project Structure

```
blender-terrain-mcp/
├── src/
│   ├── blender-scripts/
│   │   ├── biome_generator_wvd.py          # Biome map generation
│   │   ├── biome_terrain_blender.py        # 3D terrain from biome maps
│   │   ├── road_generator_logged.py        # Road mesh generation
│   │   ├── object_placer.py                # Object placement
│   │   ├── object_spawn_config.json        # Object weights/settings
│   │   ├── export_gltf_simple.py           # GLB export with baking
│   │   └── ...
│   ├── services/
│   │   ├── blenderService.ts               # Blender execution
│   │   ├── biomeService.ts                 # Biome helpers
│   │   ├── claudeService.ts                # AI integration
│   │   └── progressService.ts              # SSE progress tracking
│   ├── queue/
│   │   └── blenderQueue.ts                 # Bull job queue
│   ├── db/
│   │   └── client.ts                       # Prisma client
│   ├── server.ts                           # Express API
│   └── config.ts                           # Configuration
├── client/
│   └── src/
│       ├── components/
│       │   ├── ProgressMonitor.tsx         # SSE progress display
│       │   └── ObjectsGallery.tsx          # Objects gallery
│       ├── App.tsx                         # Main UI
│       └── types/
│           └── index.ts                    # TypeScript types
├── prisma/
│   └── schema.prisma                       # Database schema
├── assets/                                 # 3D object assets
├── output/                                 # Generated files
└── package.json
```

## 🗄️ Database Schema

**Job**: Queue job tracking
**Terrain**: Generated terrains
**Road**: Roads on terrains
**Objects**: Object placements

Relationships:
- Terrain 1:N Roads
- Terrain 1:N Objects
- Road 1:N Objects
- Job 1:1 Terrain/Road

## 🔄 Progress System (SSE)

**Server:**
```typescript
progressService.registerJob(jobId, ['step1', 'step2']);
progressService.startStep(jobId, 'step1', 'Starting...');
progressService.updateStepProgress(jobId, 'step1', 50, 'Half done');
progressService.completeStep(jobId, 'step1', 'Done');
progressService.completeJob(jobId, { result: 'data' });
```

**Client:**
```typescript
const eventSource = new EventSource(`/api/job/${jobId}/progress`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Update UI based on data.type
};
```

## 🎨 Object Spawn Configuration

Edit `src/blender-scripts/object_spawn_config.json`:

```json
{
  "objects": [
    {
      "name": "tree1.blend",
      "type": "tree",
      "weight": 10,
      "scale_range": [0.8, 1.2],
      "conditions": {
        "min_temperature": 0.3,
        "max_rock_exposure": 0.5
      }
    }
  ]
}
```

## 🐛 Troubleshooting

### Blender Path Issues
- Verify Blender installation path in `src/config.ts`
- Test Blender command line: `blender --version`

### Redis Connection Failed
- Ensure Redis is running: `redis-cli ping` → PONG
- Check port 6379 is not blocked

### Database Errors
- Run migrations: `npx prisma migrate dev`
- Reset database: `npx prisma migrate reset`

### Queue Not Processing
- Check worker is running
- View Redis keys: `redis-cli keys "*"`
- Monitor queue: `npm run worker`

### GLB Export Fails
- Check Blender has GPU access (for Cycles baking)
- Increase timeout in `blenderService.ts`
- Check output/ directory permissions

## 📝 API Endpoints

**Terrains:**
- `POST /api/terrain` - Create terrain
- `GET /api/terrains` - List terrains
- `DELETE /api/terrain/:id` - Delete terrain
- `POST /api/terrain/:id/export-gltf` - Export to GLB

**Roads:**
- `POST /api/road` - Create road
- `GET /api/roads` - List roads
- `DELETE /api/road/:id` - Delete road
- `POST /api/road/:id/export-gltf` - Export to GLB

**Objects:**
- `POST /api/objects` - Create objects
- `GET /api/objects` - List objects
- `DELETE /api/objects/:id` - Delete objects
- `POST /api/objects/:id/export-gltf` - Export to GLB

**Progress:**
- `GET /api/job/:id/progress` - SSE stream
- `GET /api/job/:id/status` - Job status

## 📜 License

MIT

## 🤝 Contributing

Contributions welcome! Please open issues or pull requests.

## 📧 Contact

For questions or support, please open an issue on GitHub.
