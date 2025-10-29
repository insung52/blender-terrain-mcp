import { useState, useEffect, useRef } from 'react';
import './App.css';
import { simplifyDrawnPath } from './utils/simplifyPath';
import { ObjectsGallery } from './components/ObjectsGallery';
import { ProgressMonitor } from './components/ProgressMonitor';

interface Terrain {
  id: string;
  scale: number;
  roughness: number;
  description: string;
  createdAt: string;
  blendFilePath: string;
  topViewPath?: string;
  metadata?: any;
  jobId?: string;
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
    blendFilePath?: string;
    previewPath?: string;
  };
  result?: {
    preview?: string;
    blendFile?: string;
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
  const [isDrawingMode, setIsDrawingMode] = useState(true);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawnPoints, setDrawnPoints] = useState<[number, number][]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [jobId, setJobId] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [progressJobId, setProgressJobId] = useState<string>('');
  const [objectsRefreshTrigger, setObjectsRefreshTrigger] = useState(0);

  const [activeTab, setActiveTab] = useState<'terrain' | 'road' | 'objects'>('terrain');

  const API_URL = '';

  // Load terrains on component mount
  useEffect(() => {
    loadTerrains();
    loadRoads();

    // Check for ongoing job (reconnection)
    const savedJobId = localStorage.getItem('currentJobId');
    const savedJobType = localStorage.getItem('currentJobType');

    if (savedJobId && savedJobType === 'terrain') {
      // Check if job is still in progress
      fetch(`${API_URL}/api/job/${savedJobId}/status`)
        .then(res => res.json())
        .then(data => {
          if (data.success && data.job) {
            const jobStatus = data.job.status;
            if (jobStatus === 'queued' || jobStatus === 'processing') {
              // Job is still in progress, reconnect
              console.log('[App] Reconnecting to job:', savedJobId);
              setProgressJobId(savedJobId);
              setShowProgressModal(true);
            } else if (jobStatus === 'completed') {
              // Job completed while user was away
              console.log('[App] Job completed while offline');
              localStorage.removeItem('currentJobId');
              localStorage.removeItem('currentJobType');
              loadTerrains();
            } else {
              // Job failed or unknown state
              localStorage.removeItem('currentJobId');
              localStorage.removeItem('currentJobType');
            }
          }
        })
        .catch(err => {
          console.error('[App] Failed to check job status:', err);
        });
    }
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
        setProgressJobId(data.jobId);
        setShowProgressModal(true);

        // Store jobId in localStorage for reconnection
        localStorage.setItem('currentJobId', data.jobId);
        localStorage.setItem('currentJobType', 'terrain');

        // Immediately reload terrains to show the processing terrain
        loadTerrains();
      } else {
        alert('Terrain creation failed: ' + (data.error || 'Unknown error'));
      }
    } catch (error: any) {
      alert('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleProgressComplete = (result: any) => {
    console.log('[App] Job completed:', result);
    // Reload terrains list
    loadTerrains();
    // Reload roads list
    loadRoads();
    // Reload objects list immediately (triggers ObjectsGallery refresh)
    setObjectsRefreshTrigger(prev => prev + 1);

    // Reload again after a short delay to ensure DB is updated
    setTimeout(() => {
      setObjectsRefreshTrigger(prev => prev + 1);
      loadRoads();
    }, 500);

    // Close progress modal after a delay
    setTimeout(() => {
      setShowProgressModal(false);
      localStorage.removeItem('currentJobId');
      localStorage.removeItem('currentJobType');
    }, 2000);
  };

  const handleProgressFailed = (error: string) => {
    console.error('[App] Job failed:', error);
    alert(`Job failed: ${error}`);
  };

  const createRoad = async () => {
    if (!roadTerrainId) {
      alert('Please enter Terrain ID');
      return null;
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
        return data; // Return the full response data
      } else {
        alert('Road creation failed: ' + (data.error || 'Unknown error'));
        return null;
      }
    } catch (error: any) {
      alert('Error: ' + error.message);
      return null;
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

  const createObjectsForRoad = async (road: any) => {
    const countStr = prompt('배치할 오브젝트 개수를 입력하세요 (권장: 50-200)', '100');
    if (!countStr) return;

    const objectCount = parseInt(countStr);
    if (isNaN(objectCount) || objectCount < 1) {
      alert('올바른 숫자를 입력하세요!');
      return;
    }

    const estimatedTime = Math.ceil(objectCount / 10);
    if (!confirm(`${objectCount}개의 오브젝트를 배치하시겠습니까?\n예상 소요 시간: ${estimatedTime}분`)) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/objects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          terrainId: road.terrainId,
          roadId: road.id,
          objectCount
        })
      });

      const data = await response.json();
      if (data.success && data.jobId) {
        // Objects gallery로 전환
        setActiveTab('objects');

        // Progress 팝업 표시
        setProgressJobId(data.jobId);
        setShowProgressModal(true);

        // localStorage에 jobId 저장 (페이지 새로고침 대응)
        localStorage.setItem('currentJobId', data.jobId);
      } else {
        alert(`❌ 오류: ${data.error}`);
      }
    } catch (error: any) {
      alert(`❌ 오류: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const createRoadForTerrain = (terrain: Terrain) => {
    setModalTerrain(terrain);
    setRoadTerrainId(terrain.id);
    setRoadPoints('[[10,10],[80,50],[50,30],[90,80],[70,50]]');
    setDrawnPoints([]);
    setIsDrawingMode(true);
    setShowRoadModal(true);
  };

  const handleRoadModalSubmit = async () => {
    const result = await createRoad();
    setShowRoadModal(false);
    setDrawnPoints([]);

    // Check if road creation started successfully
    if (result && result.jobId) {
      // Road gallery로 전환
      setActiveTab('road');

      // Progress 팝업 표시
      setProgressJobId(result.jobId);
      setShowProgressModal(true);

      // localStorage에 jobId 저장 (페이지 새로고침 대응)
      localStorage.setItem('currentJobId', result.jobId);

      // Roads 목록 즉시 갱신 (처리 중인 road 표시)
      loadRoads();
    }
  };

  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawingMode) return;
    setIsDrawing(true);
    const canvas = e.currentTarget;
    const rect = canvas.getBoundingClientRect();
    // Scale from display size to actual canvas size
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    setDrawnPoints([[x, y]]);
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !isDrawingMode) return;
    const canvas = e.currentTarget;
    const rect = canvas.getBoundingClientRect();
    // Scale from display size to actual canvas size
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    setDrawnPoints(prev => [...prev, [x, y]]);
  };

  const handleCanvasMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);

    // Simplify the drawn path and convert to control points
    if (drawnPoints.length > 2) {
      const simplified = simplifyDrawnPath(drawnPoints, {
        minDistance: 5,
        epsilon: 3,
        maxPoints: 20
      });

      // Scale to terrain coordinates (assume 100x100 terrain, 500x500 canvas)
      const scaled = simplified.map(([x, y]) => {
        const scaleX = 100 / 500; // canvas width to terrain
        const scaleY = 100 / 500; // canvas height to terrain
        return [Math.round(x * scaleX), Math.round(y * scaleY)];
      });

      setRoadPoints(JSON.stringify(scaled));
    }
  };

  const clearDrawing = () => {
    setDrawnPoints([]);
    setRoadPoints('[[10,10],[80,50],[50,30],[90,80],[70,50]]');
  };

  // Draw on canvas
  useEffect(() => {
    if (!canvasRef.current || !modalTerrain || !isDrawingMode) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas first
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw terrain preview image
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = `${API_URL}/output/${modalTerrain.topViewPath?.split('\\').pop()}`;

    img.onerror = () => {
      // If image fails to load, just show gray background
      ctx.fillStyle = '#e0e0e0';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      redrawPath();
    };

    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      redrawPath();
    };

    function redrawPath() {
      if (!ctx) return;

      // Draw the drawn path (red line)
      if (drawnPoints.length > 1) {
        ctx.strokeStyle = '#FF0000';
        ctx.lineWidth = 4;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        ctx.moveTo(drawnPoints[0][0], drawnPoints[0][1]);
        for (let i = 1; i < drawnPoints.length; i++) {
          ctx.lineTo(drawnPoints[i][0], drawnPoints[i][1]);
        }
        ctx.stroke();
      }

      // Draw control points (green dots)
      try {
        const controlPoints = JSON.parse(roadPoints);
        if (Array.isArray(controlPoints) && controlPoints.length > 0) {
          ctx.fillStyle = '#00FF00';
          ctx.strokeStyle = '#006600';
          ctx.lineWidth = 2;
          const scaleX = canvas.width / 100;
          const scaleY = canvas.height / 100;
          controlPoints.forEach(([x, y]: [number, number]) => {
            ctx.beginPath();
            ctx.arc(x * scaleX, y * scaleY, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
          });
        }
      } catch (e) {
        // Invalid JSON, ignore
      }
    }
  }, [drawnPoints, modalTerrain, roadPoints, API_URL, isDrawingMode]);

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
      <h1>🏔️ Terrain Generator</h1>

      {/* Progress Modal */}
      {showProgressModal && progressJobId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: '#1a1a1a',
            padding: '30px',
            borderRadius: '12px',
            maxWidth: '600px',
            width: '90%',
            maxHeight: '80vh',
            overflow: 'auto'
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '20px'
            }}>
              <h2 style={{ margin: 0 }}>Terrain Generation Progress</h2>
              <button
                onClick={() => {
                  setShowProgressModal(false);
                  // Don't remove from localStorage - allow reconnection
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#fff',
                  fontSize: '24px',
                  cursor: 'pointer'
                }}
              >
                ×
              </button>
            </div>
            <ProgressMonitor
              jobId={progressJobId}
              onComplete={handleProgressComplete}
              onFailed={handleProgressFailed}
            />
          </div>
        </div>
      )}

      {/* 탭 네비게이션 */}
      <div style={{
        display: 'flex',
        gap: '10px',
        marginBottom: '20px',
        borderBottom: '2px solid #444'
      }}>
        <button
          onClick={() => setActiveTab('terrain')}
          style={{
            padding: '12px 24px',
            background: activeTab === 'terrain' ? '#4CAF50' : '#2a2a2a',
            color: '#fff',
            border: 'none',
            borderBottom: activeTab === 'terrain' ? '3px solid #4CAF50' : 'none',
            cursor: 'pointer',
            fontSize: '16px',
            fontWeight: activeTab === 'terrain' ? 'bold' : 'normal'
          }}
        >
          🏔️ Terrain Gallery
        </button>
        <button
          onClick={() => setActiveTab('road')}
          style={{
            padding: '12px 24px',
            background: activeTab === 'road' ? '#FF9800' : '#2a2a2a',
            color: '#fff',
            border: 'none',
            borderBottom: activeTab === 'road' ? '3px solid #FF9800' : 'none',
            cursor: 'pointer',
            fontSize: '16px',
            fontWeight: activeTab === 'road' ? 'bold' : 'normal'
          }}
        >
          🛣️ Road Gallery
        </button>
        <button
          onClick={() => setActiveTab('objects')}
          style={{
            padding: '12px 24px',
            background: activeTab === 'objects' ? '#2196F3' : '#2a2a2a',
            color: '#fff',
            border: 'none',
            borderBottom: activeTab === 'objects' ? '3px solid #2196F3' : 'none',
            cursor: 'pointer',
            fontSize: '16px',
            fontWeight: activeTab === 'objects' ? 'bold' : 'normal'
          }}
        >
          🌲 Objects Gallery
        </button>
      </div>

      {/* Objects Gallery */}
      {activeTab === 'objects' && (
        <div style={{ colorScheme: 'light', color: '#000' } as React.CSSProperties}>
          <ObjectsGallery
            onShowProgress={(jobId) => {
              setProgressJobId(jobId);
              setShowProgressModal(true);
            }}
            refreshTrigger={objectsRefreshTrigger}
          />
        </div>
      )}

      {/* Terrain & Road Sections (기존 코드) */}
      {activeTab !== 'objects' && (
        <>
          {/* Terrain Section */}
          {activeTab === 'terrain' && <div className="section">
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
      </div>}

      {/* Terrain Gallery */}
      {activeTab === 'terrain' && <div className="section">
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
            {terrains.map((terrain) => {
              const isProcessing = terrain.metadata?.status === 'processing' || !terrain.blendFilePath;

              return (
              <div
                key={terrain.id}
                style={{
                  border: selectedTerrain?.id === terrain.id ? '2px solid #4CAF50' : '1px solid #ddd',
                  borderRadius: '8px',
                  padding: '1rem',
                  backgroundColor: isProcessing ? '#fff3e0' : '#f9f9f9',
                  transition: 'all 0.2s',
                  position: 'relative'
                }}
              >
                {isProcessing && (
                  <div style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    background: '#FF9800',
                    color: '#fff',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: 'bold'
                  }}>
                    ⏳ Processing...
                  </div>
                )}

                {terrain.topViewPath && !isProcessing && (
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

                {isProcessing && (
                  <div style={{
                    width: '100%',
                    height: '200px',
                    backgroundColor: '#e0e0e0',
                    borderRadius: '4px',
                    marginBottom: '0.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#666',
                    fontSize: '14px'
                  }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '48px', marginBottom: '10px' }}>⏳</div>
                      <div>Generating terrain...</div>
                    </div>
                  </div>
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
                  {isProcessing ? (
                    // Show Progress 버튼 (처리 중일 때)
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (terrain.jobId) {
                          setProgressJobId(terrain.jobId);
                          setShowProgressModal(true);
                        }
                      }}
                      style={{
                        flex: 1,
                        padding: '0.5rem',
                        backgroundColor: '#FF9800',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '0.9em',
                        fontWeight: 'bold'
                      }}
                    >
                      📊 Show Progress
                    </button>
                  ) : (
                    <>
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
                    </>
                  )}
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
              );
            })}
          </div>
        )}
      </div>}

      {/* Road Gallery */}
      {activeTab === 'road' && <div className="section">
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
            {roads.map((road) => {
              const isProcessing = road.metadata?.status === 'processing' || !road.blendFilePath;
              const jobId = road.metadata?.jobId;

              return (
                <div
                  key={road.id}
                  style={{
                    border: '1px solid #ddd',
                    borderRadius: '8px',
                    padding: '1rem',
                    backgroundColor: '#f9f9f9',
                    position: 'relative'
                  }}
                >
                  {/* Processing 뱃지 */}
                  {isProcessing && (
                    <div style={{
                      position: 'absolute',
                      top: '10px',
                      right: '10px',
                      backgroundColor: '#FF9800',
                      color: '#fff',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 'bold'
                    }}>
                      Processing...
                    </div>
                  )}

                  {/* Placeholder for processing */}
                  {isProcessing ? (
                    <div style={{
                      width: '100%',
                      height: '200px',
                      backgroundColor: '#e0e0e0',
                      borderRadius: '4px',
                      marginBottom: '0.5rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#666',
                      fontSize: '14px'
                    }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '48px', marginBottom: '10px' }}>⏳</div>
                        <div>Generating road...</div>
                      </div>
                    </div>
                  ) : (
                    road.previewPath && (
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
                    )
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
                    gap: '0.5rem',
                    flexDirection: 'column'
                  }}>
                    {isProcessing ? (
                      // Show Progress 버튼 (처리 중일 때)
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (jobId) {
                            setProgressJobId(jobId);
                            setShowProgressModal(true);
                          }
                        }}
                        style={{
                          padding: '0.5rem',
                          backgroundColor: '#FF9800',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '0.9em',
                          fontWeight: 'bold'
                        }}
                      >
                        📊 Show Progress
                      </button>
                    ) : (
                      // 일반 버튼들 (완료 후)
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            createObjectsForRoad(road);
                          }}
                          style={{
                            padding: '0.5rem',
                            backgroundColor: '#4CAF50',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.9em'
                          }}
                          disabled={loading}
                        >
                          🌲 오브젝트 생성
                        </button>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteRoad(road.id);
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
                      </>
                    )}
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
              );
            })}
          </div>
        )}
      </div>}

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
                <p style={{ margin: '0.5rem 0', fontSize: '0.9em', color: '#000' }}>
                  Terrain: <strong>{modalTerrain.description || 'Untitled'}</strong>
                </p>
              </div>
            )}

            {/* Mode Toggle */}
            <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={() => setIsDrawingMode(true)}
                style={{
                  flex: 1,
                  padding: '0.5rem',
                  backgroundColor: isDrawingMode ? '#4CAF50' : '#ddd',
                  color: isDrawingMode ? 'white' : '#333',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: isDrawingMode ? 'bold' : 'normal'
                }}
              >
                🎨 Draw Mode
              </button>
              <button
                onClick={() => setIsDrawingMode(false)}
                style={{
                  flex: 1,
                  padding: '0.5rem',
                  backgroundColor: !isDrawingMode ? '#4CAF50' : '#ddd',
                  color: !isDrawingMode ? 'white' : '#333',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: !isDrawingMode ? 'bold' : 'normal'
                }}
              >
                ⌨️ Manual Input
              </button>
            </div>

            {/* Drawing Canvas */}
            {isDrawingMode ? (
              <div>
                <div style={{
                  border: '2px solid #4CAF50',
                  borderRadius: '4px',
                  overflow: 'hidden',
                  backgroundColor: '#f0f0f0',
                  aspectRatio: '1 / 1',
                  maxWidth: '500px',
                  margin: '0 auto'
                }}>
                  <canvas
                    ref={canvasRef}
                    width={500}
                    height={500}
                    onMouseDown={handleCanvasMouseDown}
                    onMouseMove={handleCanvasMouseMove}
                    onMouseUp={handleCanvasMouseUp}
                    onMouseLeave={handleCanvasMouseUp}
                    style={{
                      display: 'block',
                      width: '100%',
                      height: '100%',
                      cursor: 'crosshair'
                    }}
                  />
                </div>
                <div style={{ marginTop: '0.5rem', fontSize: '0.85em', color: '#666' }}>
                  💡 Click and drag to draw a road path on the terrain
                </div>
                <button
                  onClick={clearDrawing}
                  style={{
                    marginTop: '0.5rem',
                    padding: '0.5rem 1rem',
                    backgroundColor: '#ff9800',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '0.9em'
                  }}
                >
                  Clear Drawing
                </button>
              </div>
            ) : (
              <div className="form">
                <label>
                  Control Points (JSON):
                  <textarea
                    value={roadPoints}
                    onChange={(e) => setRoadPoints(e.target.value)}
                    placeholder="[[10,10],[50,30],[90,80]]"
                    style={{
                      width: '100%',
                      minHeight: '150px',
                      padding: '8px',
                      fontFamily: 'monospace',
                      fontSize: '0.9em',
                      border: '1px solid #ddd',
                      borderRadius: '4px'
                    }}
                  />
                </label>
                <div style={{ marginTop: '0.5rem', fontSize: '0.85em', color: '#666' }}>
                  💡 Enter control points as JSON array: [[x1,y1],[x2,y2],...]
                </div>
              </div>
            )}

            {/* Control Points Preview */}
            <div style={{
              marginTop: '1rem',
              padding: '0.5rem',
              backgroundColor: '#2a2a2a',
              borderRadius: '4px',
              fontSize: '0.85em',
              color: '#fff'
            }}>
              <strong>Current Control Points:</strong>
              <div style={{
                marginTop: '0.25rem',
                fontFamily: 'monospace',
                wordBreak: 'break-all',
                maxHeight: '60px',
                overflow: 'auto',
                color: '#fff'
              }}>
                {roadPoints}
              </div>
            </div>

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
                fontSize: '1rem',
                fontWeight: 'bold'
              }}
            >
              {loading ? 'Creating...' : '🛣️ Create Road'}
            </button>
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

            <div className="job-result" style={{ color: '#fff' }}>
              <p><strong>ID:</strong> {job.id}</p>
              <p><strong>Type:</strong> {job.type}</p>
              <p><strong>Status:</strong> <span className={`status ${job.status}`}>{job.status}</span></p>
              <p><strong>Created:</strong> {new Date(job.createdAt).toLocaleString()}</p>

              {job.terrain && (
                <div className="terrain-info" style={{ color: '#fff' }}>
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
                <div className="road-info" style={{ color: '#fff' }}>
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
                  <p style={{ marginTop: '0.5rem' }}>
                    <strong>Download .glb (GLTF):</strong>{' '}
                    <button
                      onClick={async () => {
                        if (!job.terrain) return;
                        try {
                          setLoading(true);
                          // 1. Export GLTF (캐싱됨)
                          const exportResponse = await fetch(`${API_URL}/api/terrain/${job.terrain.id}/export-gltf`, {
                            method: 'POST'
                          });
                          const exportData = await exportResponse.json();

                          if (!exportData.success) {
                            alert('GLTF export failed: ' + exportData.error);
                            return;
                          }

                          // 2. Download
                          window.location.href = `${API_URL}/api/terrain/${job.terrain.id}/download-gltf`;
                        } catch (error: any) {
                          alert('Error: ' + error.message);
                        } finally {
                          setLoading(false);
                        }
                      }}
                      disabled={loading}
                      style={{
                        padding: '0.5rem 1rem',
                        backgroundColor: '#2196F3',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '0.9em'
                      }}
                    >
                      {loading ? 'Exporting...' : 'Download GLTF'}
                    </button>
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
                  <p style={{ marginTop: '0.5rem' }}>
                    <strong>Download .glb (GLTF):</strong>{' '}
                    <button
                      onClick={async () => {
                        if (!job.road) return;
                        try {
                          setLoading(true);
                          // 1. Export GLTF (캐싱됨)
                          const exportResponse = await fetch(`${API_URL}/api/road/${job.road.id}/export-gltf`, {
                            method: 'POST'
                          });
                          const exportData = await exportResponse.json();

                          if (!exportData.success) {
                            alert('GLTF export failed: ' + exportData.error);
                            return;
                          }

                          // 2. Download
                          window.location.href = `${API_URL}/api/road/${job.road.id}/download-gltf`;
                        } catch (error: any) {
                          alert('Error: ' + error.message);
                        } finally {
                          setLoading(false);
                        }
                      }}
                      disabled={loading}
                      style={{
                        padding: '0.5rem 1rem',
                        backgroundColor: '#2196F3',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '0.9em'
                      }}
                    >
                      {loading ? 'Exporting...' : 'Download GLTF'}
                    </button>
                    <div style={{ fontSize: '0.75em', color: '#666', marginTop: '0.25rem' }}>
                      💡 Includes terrain + water + road
                    </div>
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
                    if (!job.terrain) return;
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
        </>
      )}
    </div>
  );
}

export default App;
