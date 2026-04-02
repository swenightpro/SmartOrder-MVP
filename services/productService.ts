// ============================================================
// services/productService.ts — Facade per ricerca catalogo prodotti
//
// Espone search() per cercare prodotti per codice o descrizione.
// Consumato dall'hook useProductSearch (pattern Observer).
// ============================================================

import type { Product } from '@/types';
import { apiFetch } from '@/lib/apiClient';

export const productService = {
    search: async (query: string): Promise<Product[]> => {
        if (!query || query.trim().length < 2) return [];
        const res = await apiFetch(`/products/search?q=${encodeURIComponent(query.trim())}`);
        if (!res.ok) return [];
        return res.json();
    },
};
