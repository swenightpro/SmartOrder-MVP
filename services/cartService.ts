import type { CartItem } from '@/types';
import { apiFetch } from '@/lib/apiClient';

export const cartService = {
    getCart: async (sessionId?: number | null): Promise<CartItem[]> => {
        const query = sessionId ? `?session_id=${sessionId}` : '';
        const res = await apiFetch(`/cart${query}`);
        if (!res.ok) return [];
        const data = await res.json();
        return Array.isArray(data) ? data : [];
    },

    addItem: (codArt: string, qta: number, extra?: { source?: string; ai_confidence?: number | null; related_message_id?: number | null; sessionId?: number | null }) =>
        apiFetch('/cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add', cod_art: codArt, qta, session_id: extra?.sessionId, ...extra }),
        }),

    removeItem: (id: number, sessionId?: number | null) =>
        apiFetch('/cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'remove', id, session_id: sessionId }),
        }),

    updateQty: (id: number, qta: number, source = 'customer', sessionId?: number | null) =>
        apiFetch('/cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'update_quantity', id, qta, source, session_id: sessionId }),
        }),
};
