import { useState, useEffect } from 'react';
import { healthService } from '@/services';

export type AiStatus = 'ok' | 'error' | 'loading';

export function useHealthCheck(intervalMs = 30_000) {
    const [status, setStatus] = useState<AiStatus>('loading');

    useEffect(() => {
        let mounted = true;

        const check = async () => {
            if (document.hidden) return;

            try {
                const data = await healthService.check();
                if (mounted) setStatus(data.ai_service ? 'ok' : 'error');
            } catch {
                if (mounted) setStatus('error');
            }
        };

        // Esegui subito al mount
        check();

        // Imposta il polling
        const interval = setInterval(check, intervalMs);

        // Se l'utente torna sulla tab, facciamo subito un controllo extra immediato
        const handleVisibilityChange = () => {
            if (!document.hidden) check();
        };
        document.addEventListener("visibilitychange", handleVisibilityChange);

        return () => {
            mounted = false;
            clearInterval(interval);
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [intervalMs]);

    return status;
}
