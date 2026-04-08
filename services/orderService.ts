import type { OrderSummary, OrderDetail, OrderFilters } from '@/types';
import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';

function buildFiltersQuery(filters: OrderFilters = {}): string {
    const params = new URLSearchParams();
    if (filters.search) params.set('search', filters.search);
    if (filters.sortBy) params.set('sort_by', filters.sortBy);
    if (filters.sortDir) params.set('sort_dir', filters.sortDir);
    if (filters.dateFrom) params.set('date_from', filters.dateFrom);
    if (filters.dateTo) params.set('date_to', filters.dateTo);
    if (filters.searchCodCli) params.set('search_cod_cli', filters.searchCodCli);
    if (filters.searchRagSoc) params.set('search_rag_soc', filters.searchRagSoc);
    if (filters.limit != null) params.set('limit', String(filters.limit));
    if (filters.offset != null && filters.limit) {
        params.set('page', String(Math.floor(filters.offset / filters.limit)));
    }
    if (filters.esportato != null) params.set('esportato', String(filters.esportato));
    return params.toString();
}

export const orderService = {
    listAll: async (filters: OrderFilters = {}): Promise<OrderSummary[]> => {
        const qs = buildFiltersQuery(filters);
        const url = `/orders/all${qs ? '?' + qs : ''}`;
        const res = await apiFetch(url);
        if (!res.ok) return [];
        const data = await res.json();
        return Array.isArray(data) ? data : [];
    },

    list: async (codCli: number, page: number = 0, filters: OrderFilters = {}): Promise<OrderSummary[]> => {
        const baseParams = new URLSearchParams({ cod_cli: String(codCli), page: String(page) });
        const filterQs = buildFiltersQuery(filters);
        const qs = baseParams.toString() + (filterQs ? '&' + filterQs : '');
        const res = await apiFetch(`/orders/list?${qs}`);
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

    exportOrder: async (orderId: number, format: 'json' | 'csv' = 'json'): Promise<{ file_path: string; filename: string; format: string }> => {
        const res = await apiFetch(`/orders/export?id=${orderId}&format=${format}`, { method: 'POST' });
        if (!res.ok) {
            const err = await getApiErrorMessage(res, 'Errore esportazione ordine');
            throw new Error(err);
        }
        return res.json();
    },

    exportBatch: async (filters: OrderFilters = {}, limit = 50): Promise<{
        exported_count: number; failed_count: number; errors: string[]
    }> => {
        const params = buildFiltersQuery(filters);
        const qs = params ? `&${params}` : '';
        const res = await apiFetch(`/orders/export-batch?limit=${limit}${qs}`, { method: 'POST' });
        if (!res.ok) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d?.detail || d?.message || 'Export batch fallito');
        }
        return res.json();
    },
};
