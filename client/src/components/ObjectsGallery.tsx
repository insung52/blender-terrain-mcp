import { useState, useEffect } from 'react';
import type { Objects } from '../types';

const API_URL = '';

interface ObjectsGalleryProps {
  onShowProgress?: (jobId: string) => void;
  refreshTrigger?: number;
}

export function ObjectsGallery({ onShowProgress, refreshTrigger }: ObjectsGalleryProps) {
  const [objects, setObjects] = useState<Objects[]>([]);

  useEffect(() => {
    loadObjects();
  }, [refreshTrigger]);

  const loadObjects = async () => {
    try {
      const response = await fetch(`${API_URL}/api/objects`);
      const data = await response.json();
      if (data.success) {
        setObjects(data.objects);
      }
    } catch (error) {
      console.error('Failed to load objects:', error);
    }
  };

  const downloadGLB = async (id: string) => {
    window.open(`${API_URL}/api/objects/${id}/download`, '_blank');
  };

  const downloadBlend = async (id: string) => {
    window.open(`${API_URL}/api/objects/${id}/download-blend`, '_blank');
  };

  const deleteObjects = async (id: string) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;

    try {
      const response = await fetch(`${API_URL}/api/objects/${id}`, {
        method: 'DELETE'
      });

      const data = await response.json();
      if (data.success) {
        alert('✅ 삭제 완료!');
        loadObjects();
      }
    } catch (error: any) {
      alert(`❌ 오류: ${error.message}`);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h2>🌲 Objects Gallery</h2>
      <p style={{ color: '#888', marginBottom: '20px' }}>
        Road Gallery에서 도로를 선택하고 "🌲 오브젝트 생성" 버튼을 클릭하세요.
      </p>

      <h3>생성된 오브젝트 ({objects.length})</h3>

      {objects.length === 0 ? (
        <p style={{ color: '#888' }}>아직 생성된 오브젝트가 없습니다.</p>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: '20px'
        }}>
          {objects.map(obj => {
            const isProcessing = obj.metadata?.status === 'processing' || !obj.blendFilePath;
            const jobId = obj.metadata?.jobId;

            return (
              <div
                key={obj.id}
                style={{
                  background: '#2a2a2a',
                  padding: '15px',
                  borderRadius: '8px',
                  border: '1px solid #444',
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
                {isProcessing && (
                  <div style={{
                    width: '100%',
                    height: '150px',
                    backgroundColor: '#3a3a3a',
                    borderRadius: '4px',
                    marginBottom: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#888',
                    fontSize: '14px'
                  }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '48px', marginBottom: '10px' }}>⏳</div>
                      <div>Placing objects...</div>
                    </div>
                  </div>
                )}

                {/* 정보 */}
                <div style={{ marginBottom: '10px' }}>
                  <div><strong>ID:</strong> {obj.id.substring(0, 8)}...</div>
                  <div><strong>오브젝트 개수:</strong> {isProcessing ? `0 / ${obj.metadata?.requestedCount || 0}` : obj.objectCount}</div>
                  <div><strong>Terrain:</strong> {obj.terrain?.description || obj.terrainId.substring(0, 8)}</div>
                  {obj.roadId && <div><strong>Road:</strong> 포함</div>}
                  <div><strong>생성일:</strong> {new Date(obj.createdAt).toLocaleString()}</div>
                </div>

                {/* 액션 버튼 */}
                <div style={{ display: 'flex', gap: '10px', flexDirection: 'column' }}>
                  {isProcessing ? (
                    // Show Progress 버튼 (처리 중일 때)
                    <button
                      onClick={() => {
                        if (jobId && onShowProgress) {
                          onShowProgress(jobId);
                        }
                      }}
                      style={{
                        width: '100%',
                        padding: '10px',
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
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button
                        onClick={() => downloadGLB(obj.id)}
                        style={{
                          flex: 1,
                          padding: '8px',
                          background: '#2196F3',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        📥 GLB
                      </button>
                      <button
                        onClick={() => downloadBlend(obj.id)}
                        style={{
                          flex: 1,
                          padding: '8px',
                          background: '#4CAF50',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        📦 Blend
                      </button>
                      <button
                        onClick={() => deleteObjects(obj.id)}
                        style={{
                          padding: '8px 12px',
                          background: '#f44336',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        🗑️
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
