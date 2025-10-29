import { useEffect, useState, useRef } from 'react';

interface ProgressStep {
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  message?: string;
  progress?: number;
}

interface ProgressEvent {
  type: string;
  status?: string;
  step?: string;
  message?: string;
  progress?: number;
  steps?: ProgressStep[];
  result?: any;
  error?: string;
}

interface Props {
  jobId: string;
  onComplete?: (result: any) => void;
  onFailed?: (error: string) => void;
}

export function ProgressMonitor({ jobId, onComplete, onFailed }: Props) {
  const [status, setStatus] = useState<string>('connecting');
  const [steps, setSteps] = useState<ProgressStep[]>([]);
  const [error, setError] = useState<string | undefined>();
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    // 'preparing' 상태일 때는 SSE 연결 안하고 대기
    if (jobId === 'preparing') {
      setStatus('preparing');
      console.log(`[ProgressMonitor] Preparing job...`);
      return;
    }

    console.log(`[ProgressMonitor] Connecting to job ${jobId}`);

    // SSE 연결
    const eventSource = new EventSource(`/api/job/${jobId}/progress`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data: ProgressEvent = JSON.parse(event.data);
        console.log('[ProgressMonitor] Event:', data);

        switch (data.type) {
          case 'connected':
          case 'status':
            setStatus(data.status || 'unknown');
            if (data.steps) setSteps(data.steps);
            break;

          case 'step_start':
            if (data.steps) setSteps(data.steps);
            break;

          case 'step_complete':
          case 'step_progress':
            if (data.steps) setSteps(data.steps);
            break;

          case 'step_failed':
            if (data.steps) setSteps(data.steps);
            if (data.error) setError(data.error);
            break;

          case 'completed':
            setStatus('completed');
            if (data.steps) setSteps(data.steps);
            if (onComplete && data.result) {
              onComplete(data.result);
            }
            break;

          case 'failed':
            setStatus('failed');
            if (data.error) {
              setError(data.error);
              if (onFailed) onFailed(data.error);
            }
            break;

          case 'not_found':
            setStatus('not_found');
            setError('Job not found');
            break;
        }
      } catch (err) {
        console.error('[ProgressMonitor] Failed to parse event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('[ProgressMonitor] SSE error:', err);
      setStatus('error');
      setError('Connection lost');
    };

    // Cleanup
    return () => {
      console.log('[ProgressMonitor] Closing SSE connection');
      eventSource.close();
    };
  }, [jobId]);

  const getStepIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return '✅';
      case 'in_progress':
        return '⏳';
      case 'failed':
        return '❌';
      default:
        return '⭕';
    }
  };

  const getStepLabel = (name: string) => {
    const labels: Record<string, string> = {
      'biome_analysis': 'Analyzing terrain description',
      'biome_maps': 'Generating biome maps',
      'terrain_generation': 'Creating 3D terrain mesh',
      'preview_render': 'Rendering preview image'
    };
    return labels[name] || name;
  };

  return (
    <div style={{
      padding: '20px',
      border: '1px solid #555',
      borderRadius: '8px',
      backgroundColor: '#2a2a2a',
      color: '#fff'
    }}>
      <h3 style={{ marginTop: 0, color: '#fff' }}>
        {status === 'completed' ? '✅ Complete!' :
         status === 'failed' ? '❌ Failed' :
         status === 'preparing' ? '🔄 Preparing job...' :
         status === 'processing' ? '⏳ Processing...' :
         '🔄 Starting...'}
      </h3>

      {error && (
        <div style={{
          padding: '10px',
          backgroundColor: '#fee',
          border: '1px solid #fcc',
          borderRadius: '4px',
          marginBottom: '10px',
          color: '#c00'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      <div>
        {steps.map((step) => (
          <div
            key={step.name}
            style={{
              padding: '10px',
              marginBottom: '8px',
              border: '1px solid #444',
              borderRadius: '4px',
              backgroundColor:
                step.status === 'completed' ? '#1b4d1b' :
                step.status === 'in_progress' ? '#4d3d00' :
                step.status === 'failed' ? '#4d1b1b' :
                '#1a1a1a',
              color: '#fff'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '20px' }}>{getStepIcon(step.status)}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 'bold', color: '#fff' }}>{getStepLabel(step.name)}</div>
                {step.message && (
                  <div style={{ fontSize: '12px', color: '#aaa' }}>{step.message}</div>
                )}
              </div>
              {step.progress !== undefined && (
                <div style={{ fontSize: '12px', color: '#aaa' }}>{step.progress}%</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {(status === 'processing' || status === 'preparing') && steps.length === 0 && (
        <div style={{ textAlign: 'center', padding: '20px', color: '#aaa' }}>
          <div>{status === 'preparing' ? 'Analyzing terrain description...' : 'Connecting to job...'}</div>
        </div>
      )}
    </div>
  );
}
