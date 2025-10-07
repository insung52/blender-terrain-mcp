import { useState } from 'react';
import './App.css';

interface Job {
  id: string;
  type: string;
  status: string;
  createdAt: string;
  completedAt?: string;
  outputPath?: string;
  previewPath?: string;
  terrain?: {
    id: string;
    scale: number;
    roughness: number;
    description: string;
  };
  road?: {
    id: string;
    controlPoints: any[];
  };
}

function App() {
  const [terrainDescription, setTerrainDescription] = useState('');
  const [terrainScale, setTerrainScale] = useState(20);
  const [terrainRoughness, setTerrainRoughness] = useState(0.7);
  const [useAI, setUseAI] = useState(true);

  const [roadTerrainId, setRoadTerrainId] = useState('');
  const [roadPoints, setRoadPoints] = useState('[[10,10],[50,30],[90,80]]');

  const [jobId, setJobId] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);

  const API_URL = 'http://localhost:3000';

  const createTerrain = async () => {
    if (!terrainDescription && useAI) {
      alert('Please enter a terrain description');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/terrain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: terrainDescription,
          scale: terrainScale,
          roughness: terrainRoughness,
          useAI
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create terrain');
      }

      const data = await response.json();

      if (data.success && data.jobId) {
        setJobId(data.jobId);
        alert(`Terrain job created!\nJob ID: ${data.jobId}\n\nProcessing... Click "Check Job" to see progress.`);
      } else {
        alert('Terrain creation failed: ' + (data.error || 'Unknown error'));
      }
    } catch (error: any) {
      alert('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const createRoad = async () => {
    if (!roadTerrainId) {
      alert('Please enter Terrain ID');
      return;
    }

    setLoading(true);
    try {
      const points = JSON.parse(roadPoints);
      const response = await fetch(`${API_URL}/api/road`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          terrainId: roadTerrainId,
          controlPoints: points
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create road');
      }

      const data = await response.json();

      if (data.success && data.jobId) {
        setJobId(data.jobId);
        alert(`Road job created!\nJob ID: ${data.jobId}\n\nClick "Check Job" to see progress.`);
      } else {
        alert('Road creation failed: ' + (data.error || 'Unknown error'));
      }
    } catch (error: any) {
      alert('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const checkJob = async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/job/${jobId}`);
      const data = await response.json();
      setJob(data.job);
    } catch (error) {
      alert('Error: ' + error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <h1>🏔️ Blender Terrain Generator</h1>

      {/* Terrain Section */}
      <div className="section">
        <h2>1. Create Terrain</h2>
        <div className="form">
          <label>
            Description (한글):
            <input
              type="text"
              value={terrainDescription}
              onChange={(e) => setTerrainDescription(e.target.value)}
              placeholder="눈 덮인 높은 산맥"
            />
          </label>

          <label>
            <input
              type="checkbox"
              checked={useAI}
              onChange={(e) => setUseAI(e.target.checked)}
            />
            Use Claude AI to analyze description
          </label>

          {!useAI && (
            <>
              <label>
                Scale (5-50):
                <input
                  type="number"
                  value={terrainScale}
                  onChange={(e) => setTerrainScale(Number(e.target.value))}
                  min="5"
                  max="50"
                />
              </label>

              <label>
                Roughness (0-1):
                <input
                  type="number"
                  value={terrainRoughness}
                  onChange={(e) => setTerrainRoughness(Number(e.target.value))}
                  step="0.1"
                  min="0"
                  max="1"
                />
              </label>
            </>
          )}

          <button onClick={createTerrain} disabled={loading}>
            {loading ? 'Creating...' : 'Create Terrain'}
          </button>
        </div>
      </div>

      {/* Road Section */}
      <div className="section">
        <h2>2. Add Road to Terrain</h2>
        <div className="form">
          <label>
            Terrain ID:
            <input
              type="text"
              value={roadTerrainId}
              onChange={(e) => setRoadTerrainId(e.target.value)}
              placeholder="terrain-id-from-job"
            />
          </label>

          <label>
            Control Points (JSON):
            <input
              type="text"
              value={roadPoints}
              onChange={(e) => setRoadPoints(e.target.value)}
              placeholder="[[10,10],[50,30],[90,80]]"
            />
          </label>

          <button onClick={createRoad} disabled={loading}>
            {loading ? 'Creating...' : 'Create Road'}
          </button>
        </div>
      </div>

      {/* Job Status Section */}
      <div className="section">
        <h2>3. Check Job Status</h2>
        <div className="form">
          <label>
            Job ID:
            <input
              type="text"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              placeholder="job-id"
            />
          </label>

          <button onClick={checkJob} disabled={loading}>
            {loading ? 'Checking...' : 'Check Job'}
          </button>
        </div>

        {job && (
          <div className="job-result">
            <h3>Job Result</h3>
            <p><strong>ID:</strong> {job.id}</p>
            <p><strong>Type:</strong> {job.type}</p>
            <p><strong>Status:</strong> <span className={`status ${job.status}`}>{job.status}</span></p>
            <p><strong>Created:</strong> {new Date(job.createdAt).toLocaleString()}</p>

            {job.terrain && (
              <div className="terrain-info">
                <h4>Terrain Info</h4>
                <p>
                  <strong>Terrain ID:</strong>{' '}
                  <span style={{
                    background: '#2a2a2a',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontFamily: 'monospace',
                    fontSize: '0.9em',
                    cursor: 'pointer'
                  }}
                  onClick={() => {
                    navigator.clipboard.writeText(job.terrain.id);
                    setRoadTerrainId(job.terrain.id);
                    alert('Terrain ID copied! (Road 섹션에 자동 입력됨)');
                  }}>
                    {job.terrain.id}
                  </span>
                </p>
                <p><strong>Description:</strong> {job.terrain.description}</p>
                {job.terrain.metadata?.base_scale && (
                  <>
                    <p><strong>Height:</strong> {job.terrain.metadata.height_multiplier}m</p>
                    <p><strong>Noise Type:</strong> {job.terrain.metadata.noise_type}</p>
                    <p><strong>Climate:</strong> {job.terrain.metadata.climate}</p>
                  </>
                )}
              </div>
            )}

            {job.road && (
              <div className="road-info">
                <h4>Road Info</h4>
                <p><strong>Road ID:</strong> {job.road.id}</p>
                <p><strong>Points:</strong> {job.road.controlPoints.length}</p>
              </div>
            )}

            {job.status === 'completed' && (
              <div className="preview">
                <h4>Preview</h4>
                {(job.terrain?.topViewPath || job.road?.previewPath || job.result?.preview) && (
                  <img
                    src={`${API_URL}/output/${(job.terrain?.topViewPath || job.road?.previewPath || job.result?.preview || '').split('\\').pop()}`}
                    alt="Preview"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                    style={{ maxWidth: '100%', border: '1px solid #ccc', marginBottom: '1rem' }}
                  />
                )}
                {(job.terrain?.blendFilePath || job.road?.blendFilePath || job.result?.blendFile) && (
                  <p>
                    <strong>Download .blend:</strong>{' '}
                    <a
                      href={`${API_URL}/output/${(job.terrain?.blendFilePath || job.road?.blendFilePath || job.result?.blendFile || '').split('\\').pop()}`}
                      download
                    >
                      {(job.terrain?.blendFilePath || job.road?.blendFilePath || job.result?.blendFile || '').split('\\').pop()}
                    </a>
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
