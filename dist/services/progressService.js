"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.progressService = void 0;
class ProgressService {
    constructor() {
        this.jobs = new Map();
    }
    // 새 작업 등록
    registerJob(jobId, steps) {
        this.jobs.set(jobId, {
            jobId,
            status: 'queued',
            steps: steps.map(name => ({ name, status: 'pending' })),
            connections: []
        });
    }
    // SSE 연결 추가
    addConnection(jobId, res) {
        const job = this.jobs.get(jobId);
        if (job) {
            job.connections.push(res);
            // 연결 해제 시 제거
            res.on('close', () => {
                this.removeConnection(jobId, res);
            });
        }
    }
    // SSE 연결 제거
    removeConnection(jobId, res) {
        const job = this.jobs.get(jobId);
        if (job) {
            job.connections = job.connections.filter(conn => conn !== res);
        }
    }
    // 작업 상태 업데이트
    updateJobStatus(jobId, status) {
        const job = this.jobs.get(jobId);
        if (job) {
            job.status = status;
            this.broadcast(jobId, {
                type: 'status',
                status,
                steps: job.steps
            });
        }
    }
    // 스텝 시작
    startStep(jobId, stepName, message) {
        const job = this.jobs.get(jobId);
        if (job) {
            const step = job.steps.find(s => s.name === stepName);
            if (step) {
                step.status = 'in_progress';
                step.message = message;
                job.currentStep = stepName;
                this.broadcast(jobId, {
                    type: 'step_start',
                    step: stepName,
                    message,
                    steps: job.steps
                });
            }
        }
    }
    // 스텝 완료
    completeStep(jobId, stepName, message) {
        const job = this.jobs.get(jobId);
        if (job) {
            const step = job.steps.find(s => s.name === stepName);
            if (step) {
                step.status = 'completed';
                step.message = message;
                step.progress = 100;
                this.broadcast(jobId, {
                    type: 'step_complete',
                    step: stepName,
                    message,
                    steps: job.steps
                });
            }
        }
    }
    // 스텝 실패
    failStep(jobId, stepName, error) {
        const job = this.jobs.get(jobId);
        if (job) {
            const step = job.steps.find(s => s.name === stepName);
            if (step) {
                step.status = 'failed';
                step.message = error;
                this.broadcast(jobId, {
                    type: 'step_failed',
                    step: stepName,
                    error,
                    steps: job.steps
                });
            }
        }
    }
    // 스텝 진행률 업데이트
    updateStepProgress(jobId, stepName, progress, message) {
        const job = this.jobs.get(jobId);
        if (job) {
            const step = job.steps.find(s => s.name === stepName);
            if (step) {
                step.progress = progress;
                if (message)
                    step.message = message;
                this.broadcast(jobId, {
                    type: 'step_progress',
                    step: stepName,
                    progress,
                    message,
                    steps: job.steps
                });
            }
        }
    }
    // 작업 완료
    completeJob(jobId, result) {
        const job = this.jobs.get(jobId);
        if (job) {
            job.status = 'completed';
            job.result = result;
            this.broadcast(jobId, {
                type: 'completed',
                result,
                steps: job.steps
            });
            // 연결 닫기
            setTimeout(() => {
                this.closeConnections(jobId);
            }, 1000);
        }
    }
    // 작업 실패
    failJob(jobId, error) {
        const job = this.jobs.get(jobId);
        if (job) {
            job.status = 'failed';
            job.error = error;
            this.broadcast(jobId, {
                type: 'failed',
                error,
                steps: job.steps
            });
            // 연결 닫기
            setTimeout(() => {
                this.closeConnections(jobId);
            }, 1000);
        }
    }
    // 작업 상태 조회
    getJobProgress(jobId) {
        return this.jobs.get(jobId);
    }
    // SSE로 이벤트 브로드캐스트
    broadcast(jobId, data) {
        const job = this.jobs.get(jobId);
        if (job) {
            const message = `data: ${JSON.stringify(data)}\n\n`;
            job.connections.forEach(res => {
                try {
                    res.write(message);
                }
                catch (err) {
                    console.error(`[Progress] Failed to send message to connection:`, err);
                }
            });
        }
    }
    // 모든 연결 닫기
    closeConnections(jobId) {
        const job = this.jobs.get(jobId);
        if (job) {
            job.connections.forEach(res => {
                try {
                    res.end();
                }
                catch (err) {
                    // ignore
                }
            });
            job.connections = [];
        }
    }
    // 작업 삭제 (완료 후 일정 시간 후)
    cleanupJob(jobId) {
        this.closeConnections(jobId);
        this.jobs.delete(jobId);
    }
}
exports.progressService = new ProgressService();
