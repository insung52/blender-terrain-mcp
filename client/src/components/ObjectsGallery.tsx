import { useState, useEffect } from 'react';
import type { Objects } from '../types';

const API_URL = 'http://localhost:3000';

export function ObjectsGallery() {
  const [objects, setObjects] = useState<Objects[]>([]);

  useEffect(() => {
    loadObjects();
  }, []);

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
          {objects.map(obj => (
            <div
              key={obj.id}
              style={{
                background: '#2a2a2a',
                padding: '15px',
                borderRadius: '8px',
                border: '1px solid #444'
              }}
            >
              {/* 정보 */}
              <div style={{ marginBottom: '10px' }}>
                <div><strong>ID:</strong> {obj.id.substring(0, 8)}...</div>
                <div><strong>오브젝트 개수:</strong> {obj.objectCount}</div>
                <div><strong>Terrain:</strong> {obj.terrain?.description || obj.terrainId.substring(0, 8)}</div>
                {obj.roadId && <div><strong>Road:</strong> 포함</div>}
                <div><strong>생성일:</strong> {new Date(obj.createdAt).toLocaleString()}</div>
              </div>

              {/* 액션 버튼 */}
              <div style={{ display: 'flex', gap: '10px', flexDirection: 'column' }}>
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
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
