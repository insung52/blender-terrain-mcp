import { useState, useEffect } from 'react';
import './App.css';

interface Terrain {
  id: string;
  scale: number;
  roughness: number;
  description: string;
  createdAt: string;
  blendFilePath: string;
  topViewPath?: string;
  metadata?: any;
}

interface Job {
  id: string;
  type: string;
  status: string;
  createdAt: string;
  completedAt?: string;
  outputPath?: string;
  previewPath?: string;
  terrain?: Terrain;
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

  const [terrains, setTerrains] = useState<Terrain[]>([]);
  const [roads, setRoads] = useState<any[]>([]);
  const [selectedTerrain, setSelectedTerrain] = useState<Terrain | null>(null);
  const [roadTerrainId, setRoadTerrainId] = useState('');
  const [roadPoints, setRoadPoints] = useState('[[10,10],[80,50],[50,30],[90,80],[70,50]]');

  const [showRoadModal, setShowRoadModal] = useState(false);
  const [showJobModal, setShowJobModal] = useState(false);
  const [modalTerrain, setModalTerrain] = useState<Terrain | null>(null);

  const [jobId, setJobId] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);

  const API_URL = 'http://localhost:3000';

  // Load terrains on component mount
  useEffect(() => {
    loadTerrains();
    loadRoads();
  }, []);

  const loadTerrains = async () => {
    try {
      const response = await fetch(`${API_URL}/api/terrains`);
      const data = await response.json();
      if (data.success) {
        setTerrains(data.terrains);
      }
    } catch (error) {
      console.error('Failed to load terrains:', error);
    }
  };

  const loadRoads = async () => {
    try {
      console.log('Loading roads from:', `${API_URL}/api/roads`);
      const response = await fetch(`${API_URL}/api/roads`);
      const data = await response.json();
      console.log('Roads response:', data);
      if (data.success) {
        console.log('Setting roads:', data.roads);
        setRoads(data.roads);
      }
    } catch (error) {
      console.error('Failed to load roads:', error);
    }
  };

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
        // Reload terrains list after a delay
        setTimeout(() => loadTerrains(), 2000);
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
        alert(`Road job created!\nJob ID: ${data.jobId}\n\nProcessing... Roads will appear in gallery when complete.`);
        // Reload roads list after a delay
        setTimeout(() => loadRoads(), 2000);
        setTimeout(() => loadRoads(), 5000);
        setTimeout(() => loadRoads(), 10000);
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

  const deleteTerrain = async (terrainId: string) => {
    if (!confirm('Are you sure you want to delete this terrain? All roads on this terrain will also be deleted.')) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/terrain/${terrainId}`, {
        method: 'DELETE'
      });
      const data = await response.json();

      if (data.success) {
        alert('Terrain deleted successfully');
        loadTerrains();
        loadRoads();
        if (selectedTerrain?.id === terrainId) {
          setSelectedTerrain(null);
        }
      } else {
        alert('Failed to delete terrain: ' + data.error);
      }
    } catch (error: any) {
      alert('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const deleteRoad = async (roadId: string) => {
    if (!confirm('Are you sure you want to delete this road?')) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/road/${roadId}`, {
        method: 'DELETE'
      });
      const data = await response.json();

      if (data.success) {
        alert('Road deleted successfully');
        loadRoads();
      } else {
        alert('Failed to delete road: ' + data.error);
      }
    } catch (error: any) {
      alert('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const createRoadForTerrain = (terrain: Terrain) => {
    setModalTerrain(terrain);
    setRoadTerrainId(terrain.id);
    setRoadPoints('[[10,10],[80,50],[50,30],[90,80],[70,50]]');
    setShowRoadModal(true);
  };

  const handleRoadModalSubmit = async () => {
    await createRoad();
    setShowRoadModal(false);
    loadRoads();
  };

  const showJobDetails = async (terrain: Terrain) => {
    setLoading(true);
    try {
      // Find the job for this terrain
      const response = await fetch(`${API_URL}/api/job/terrain/${terrain.id}`);
      const data = await response.json();
      if (data.success) {
        setJob(data.job);
        setShowJobModal(true);
      } else {
        alert('Job not found for this terrain');
      }
    } catch (error) {
      console.error('Failed to load job:', error);
      alert('Failed to load job details');
    } finally {
      setLoading(false);
    }
  };

  const showRoadJobDetails = async (road: any) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/job/road/${road.id}`);
      const data = await response.json();
      if (data.success) {
        setJob(data.job);
        setShowJobModal(true);
      } else {
        alert('Job not found for this road');
      }
    } catch (error) {
      console.error('Failed to load job:', error);
      alert('Failed to load job details');
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

      {/* Terrain Gallery */}
      <div className="section">
        <h2>2. Terrain Gallery</h2>
        {terrains.length === 0 ? (
          <p style={{ color: '#666', textAlign: 'center', padding: '2rem' }}>
            No terrains available. Create a terrain first.
          </p>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: '1rem',
            marginTop: '1rem'
          }}>
            {terrains.map((terrain) => (
              <div
                key={terrain.id}
                style={{
                  border: selectedTerrain?.id === terrain.id ? '2px solid #4CAF50' : '1px solid #ddd',
                  borderRadius: '8px',
                  padding: '1rem',
                  backgroundColor: '#f9f9f9',
                  transition: 'all 0.2s'
                }}
              >
                {terrain.topViewPath && (
                  <img
                    src={`${API_URL}/output/${terrain.topViewPath.split('\\').pop()}`}
                    alt="Terrain preview"
                    style={{
                      width: '100%',
                      height: '200px',
                      objectFit: 'cover',
                      borderRadius: '4px',
                      marginBottom: '0.5rem',
                      cursor: 'pointer'
                    }}
                    onClick={() => showJobDetails(terrain)}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                )}

                <h4 style={{ margin: '0.5rem 0', fontSize: '1em', color: '#333' }}>
                  {terrain.description || 'Untitled Terrain'}
                </h4>

                <p style={{ fontSize: '0.85em', color: '#666', margin: '0.25rem 0' }}>
                  Created: {new Date(terrain.createdAt).toLocaleString()}
                </p>

                {terrain.metadata && (
                  <div style={{ fontSize: '0.8em', color: '#555', marginTop: '0.5rem' }}>
                    {terrain.metadata.height_multiplier && (
                      <p style={{ margin: '0.2rem 0' }}>Height: {terrain.metadata.height_multiplier}m</p>
                    )}
                    {terrain.metadata.noise_type && (
                      <p style={{ margin: '0.2rem 0' }}>Noise: {terrain.metadata.noise_type}</p>
                    )}
                    {terrain.metadata.climate && (
                      <p style={{ margin: '0.2rem 0' }}>Climate: {terrain.metadata.climate}</p>
                    )}
                  </div>
                )}

                <div style={{
                  marginTop: '1rem',
                  display: 'flex',
                  gap: '0.5rem',
                  flexWrap: 'wrap'
                }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      createRoadForTerrain(terrain);
                    }}
                    style={{
                      flex: 1,
                      padding: '0.5rem',
                      backgroundColor: '#4CAF50',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.9em'
                    }}
                  >
                    🛣️ Add Road
                  </button>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteTerrain(terrain.id);
                    }}
                    style={{
                      padding: '0.5rem',
                      backgroundColor: '#f44336',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.9em'
                    }}
                    disabled={loading}
                  >
                    🗑️ Delete
                  </button>
                </div>

                <p style={{
                  fontSize: '0.7em',
                  color: '#999',
                  marginTop: '0.5rem',
                  fontFamily: 'monospace',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  ID: {terrain.id}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Road Gallery */}
      <div className="section">
        <h2>3. Road Gallery</h2>
        {roads.length === 0 ? (
          <p style={{ color: '#666', textAlign: 'center', padding: '2rem' }}>
            No roads available. Add a road to a terrain first.
          </p>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: '1rem',
            marginTop: '1rem'
          }}>
            {roads.map((road) => (
              <div
                key={road.id}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '8px',
                  padding: '1rem',
                  backgroundColor: '#f9f9f9'
                }}
              >
                {road.previewPath && (
                  <img
                    src={`${API_URL}/output/${road.previewPath.split('\\').pop()}`}
                    alt="Road preview"
                    style={{
                      width: '100%',
                      height: '200px',
                      objectFit: 'cover',
                      borderRadius: '4px',
                      marginBottom: '0.5rem',
                      cursor: 'pointer'
                    }}
                    onClick={() => showRoadJobDetails(road)}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                )}

                <h4 style={{ margin: '0.5rem 0', fontSize: '1em', color: '#333' }}>
                  Road on {road.terrain?.description || 'Unknown Terrain'}
                </h4>

                <p style={{ fontSize: '0.85em', color: '#666', margin: '0.25rem 0' }}>
                  Created: {new Date(road.createdAt).toLocaleString()}
                </p>

                <p style={{ fontSize: '0.8em', color: '#555', marginTop: '0.5rem' }}>
                  Control Points: {road.controlPoints?.length || 0}
                </p>

                <div style={{
                  marginTop: '1rem',
                  display: 'flex',
                  gap: '0.5rem'
                }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteRoad(road.id);
                    }}
                    style={{
                      flex: 1,
                      padding: '0.5rem',
                      backgroundColor: '#f44336',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.9em'
                    }}
                    disabled={loading}
                  >
                    🗑️ Delete
                  </button>
                </div>

                <p style={{
                  fontSize: '0.7em',
                  color: '#999',
                  marginTop: '0.5rem',
                  fontFamily: 'monospace',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  ID: {road.id}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Road Modal */}
      {showRoadModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
          onClick={() => setShowRoadModal(false)}
        >
          <div
            style={{
              backgroundColor: 'white',
              padding: '2rem',
              borderRadius: '8px',
              maxWidth: '500px',
              width: '90%',
              maxHeight: '80vh',
              overflow: 'auto',
              position: 'relative'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0 }}>Add Road to Terrain</h2>
              <button
                onClick={() => setShowRoadModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '1.5rem',
                  cursor: 'pointer',
                  padding: '0',
                  width: '30px',
                  height: '30px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#666'
                }}
              >
                ✕
              </button>
            </div>

            {modalTerrain && (
              <div style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#e8f5e9',
                borderRadius: '4px',
                marginBottom: '1rem'
              }}>
                <p style={{ margin: '0.5rem 0', fontSize: '0.9em' }}>
                  Terrain: <strong>{modalTerrain.description || 'Untitled'}</strong>
                </p>
              </div>
            )}

            <div className="form">
              <label>
                Control Points (JSON):
                <textarea
                  value={roadPoints}
                  onChange={(e) => setRoadPoints(e.target.value)}
                  placeholder="[[10,10],[50,30],[90,80]]"
                  style={{
                    width: '100%',
                    minHeight: '100px',
                    padding: '8px',
                    fontFamily: 'monospace',
                    fontSize: '0.9em'
                  }}
                />
              </label>

              <button
                onClick={handleRoadModalSubmit}
                disabled={loading}
                style={{
                  width: '100%',
                  marginTop: '1rem',
                  padding: '0.75rem',
                  backgroundColor: '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '1rem'
                }}
              >
                {loading ? 'Creating...' : 'Create Road'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Job Status Modal */}
      {showJobModal && job && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
          onClick={() => setShowJobModal(false)}
        >
          <div
            style={{
              backgroundColor: 'white',
              padding: '2rem',
              borderRadius: '8px',
              maxWidth: '600px',
              width: '90%',
              maxHeight: '80vh',
              overflow: 'auto',
              position: 'relative'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0, color: '#000' }}>Job Details</h2>
              <button
                onClick={() => setShowJobModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '1.5rem',
                  cursor: 'pointer',
                  padding: '0',
                  width: '30px',
                  height: '30px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#666'
                }}
              >
                ✕
              </button>
            </div>

            <div className="job-result">
              <p><strong>ID:</strong> {job.id}</p>
              <p><strong>Type:</strong> {job.type}</p>
              <p><strong>Status:</strong> <span className={`status ${job.status}`}>{job.status}</span></p>
              <p><strong>Created:</strong> {new Date(job.createdAt).toLocaleString()}</p>

              {job.terrain && (
                <div className="terrain-info">
                  <h4>Terrain Info</h4>
                  <p><strong>Terrain ID:</strong> {job.terrain.id}</p>
                  <p><strong>Description:</strong> {job.terrain.description}</p>
                  {job.terrain.metadata?.height_multiplier && (
                    <p><strong>Height:</strong> {job.terrain.metadata.height_multiplier}m</p>
                  )}
                  {job.terrain.metadata?.noise_type && (
                    <p><strong>Noise Type:</strong> {job.terrain.metadata.noise_type}</p>
                  )}
                  {job.terrain.metadata?.climate && (
                    <p><strong>Climate:</strong> {job.terrain.metadata.climate}</p>
                  )}
                </div>
              )}

              {job.road && (
                <div className="road-info">
                  <h4>Road Info</h4>
                  <p><strong>Road ID:</strong> {job.road.id}</p>
                  <p><strong>Points:</strong> {job.road.controlPoints?.length || 0}</p>
                </div>
              )}

              {job.status === 'completed' && (job.terrain?.topViewPath || job.road?.previewPath) && (
                <div className="preview">
                  <h4>Preview</h4>
                  <img
                    src={`${API_URL}/output/${(job.terrain?.topViewPath || job.road?.previewPath || '').split('\\').pop()}`}
                    alt="Preview"
                    style={{ maxWidth: '100%', border: '1px solid #ccc', marginTop: '1rem' }}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
              )}

              {job.terrain?.blendFilePath && (
                <div style={{ marginTop: '1rem' }}>
                  <p>
                    <strong>Download .blend:</strong>{' '}
                    <a
                      href={`${API_URL}/output/${job.terrain.blendFilePath.split('\\').pop()}`}
                      download
                      style={{ color: '#4CAF50' }}
                    >
                      {job.terrain.blendFilePath.split('\\').pop()}
                    </a>
                  </p>
                </div>
              )}

              {job.road?.blendFilePath && (
                <div style={{ marginTop: '1rem' }}>
                  <p>
                    <strong>Download .blend:</strong>{' '}
                    <a
                      href={`${API_URL}/output/${job.road.blendFilePath.split('\\').pop()}`}
                      download
                      style={{ color: '#4CAF50' }}
                    >
                      {job.road.blendFilePath.split('\\').pop()}
                    </a>
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Hidden old sections - keeping for backwards compatibility */}
      <div className="section" style={{ display: 'none' }}>
        <h2>4. Check Job Status</h2>
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
