// ============================================================
// services/sessionService.ts — Facade per sessioni chat
//
// Espone getActive (recupera sessione aperta) e create (nuova).
// Ogni sessione raggruppa messaggi chat e articoli correlati.
// Consumato da SessionContext per gestire il ciclo di vita
// della sessione corrente.
// ============================================================

import { apiFetch } from '@/lib/apiClient';

export const sessionService = {
    getActive: async (): Promise<number | null> => {
        try {
            const res = await apiFetch('/sessions');
            if (!res.ok) return null;
            const data = await res.json();
            return data.session?.id ? Number(data.session.id) : null;
        } catch { return null; }
    },

    create: async (): Promise<number | null> => {
        try {
            const res = await apiFetch('/sessions', { method: 'POST' });
            if (!res.ok) return null;
            const data = await res.json();
            return data.session?.id ? Number(data.session.id) : null;
        } catch { return null; }
    },
};
