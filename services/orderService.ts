// ============================================================
// services/orderService.ts — Facade per gestione ordini
//
// Espone list (elenco ordini), getDetail (dettaglio con chat e
// articoli) e create (conferma ordine con lista articoli).
// Consumato da OrderHistory, OrderDetailModal e CartPanel.
// ============================================================

import type { OrderSummary, OrderDetail } from '@/types';
import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';

export const orderService = {
    list: async (codCli: number, page: number = 0): Promise<OrderSummary[]> => {
        const res = await apiFetch(`/orders/list?cod_cli=${codCli}&page=${page}`);
        if (!res.ok) return [];
        const data = await res.json();
        return Array.isArray(data) ? data : [];
    },

    getDetail: async (orderId: number, codCli: number): Promise<OrderDetail> => {
        const res = await apiFetch(`/orders/detail?id=${orderId}&cod_cli=${codCli}`);
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore recupero dettaglio ordine'));
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        return data;
    },

    create: async (codCli: number, sessionId: number | null, items: { cod_art: string; qta: number; source: string; last_updated_by: string; ai_confidence: number | null; related_message_id: number | null }[]): Promise<{ order_id: number }> => {
        const res = await apiFetch('/orders/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cod_cli: codCli, session_id: sessionId, items }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore creazione ordine'));
        const data = await res.json();
        return data;
    },
};
