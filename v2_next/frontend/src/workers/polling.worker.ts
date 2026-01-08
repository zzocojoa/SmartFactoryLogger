import { metricService } from '../api/metricService';
import { FactoryData } from '../types';

/* eslint-disable no-restricted-globals */
const ctx: Worker = self as any;

let timer: number | null = null;
let intervalMs = 500;

const tick = async () => {
    try {
        const t0 = performance.now();
        const data = await metricService.getLatest();
        const t1 = performance.now();
        const latency = t1 - t0;
        
        ctx.postMessage({
            type: 'DATA',
            payload: {
                data,
                timestamp: Date.now(),
                latency
            }
        });
    } catch (err: any) {
        ctx.postMessage({
            type: 'ERROR',
            payload: {
                message: err.message || 'Fetch failed'
            }
        });
    }
};

ctx.onmessage = (e: MessageEvent) => {
    const { type, payload } = e.data;
    
    if (type === 'START') {
        if (payload?.interval) {
            intervalMs = payload.interval;
        }
        if (timer) clearInterval(timer);
        tick(); // Initial tick
        timer = self.setInterval(tick, intervalMs);
    } else if (type === 'STOP') {
        if (timer) clearInterval(timer);
        timer = null;
    }
};
