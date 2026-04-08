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
