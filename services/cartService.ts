// ============================================================
// services/cartService.ts — Facade per operazioni carrello
//
// Espone getCart, addItem, removeItem e updateQty.
// Usa gli endpoint FastAPI /cart (GET e POST con action dispatch).
// Consumato da CartContext e ChatPanel.
// ============================================================

import type { CartItem } from '@/types';
import { apiFetch } from '@/lib/apiClient';

export const cartService = {
    getCart: async (): Promise<CartItem[]> => {
        const res = await apiFetch('/cart');
        if (!res.ok) return [];
        const data = await res.json();
        return Array.isArray(data) ? data : [];
    },

    addItem: (codArt: string, qta: number, extra?: { source?: string; ai_confidence?: number | null; related_message_id?: number | null }) =>
        apiFetch('/cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add', cod_art: codArt, qta, ...extra }),
        }),

    removeItem: (id: number) =>
        apiFetch('/cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'remove', id }),
        }),

    updateQty: (id: number, qta: number, source = 'customer') =>
        apiFetch('/cart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'update_quantity', id, qta, source }),
        }),
};
