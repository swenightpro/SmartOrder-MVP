// ============================================================
// services/healthService.ts — Facade per health check servizio AI
//
// Espone check() che interroga /health sul backend FastAPI.
// Ritorna sempre un
// oggetto HealthStatus, anche in caso di errore di rete.
// Consumato dall'hook useHealthCheck (pattern Observer).
// ============================================================

import type { HealthStatus } from '@/types';
import { apiFetch } from '@/lib/apiClient';

export const healthService = {
    check: async (): Promise<HealthStatus> => {
        try {
            const res = await apiFetch(`/health?_t=${Date.now()}`);
            if (!res.ok) return { status: 'degraded', ai_service: false };
            return res.json();
        } catch {
            return { status: 'degraded', ai_service: false };
        }
    },
};
