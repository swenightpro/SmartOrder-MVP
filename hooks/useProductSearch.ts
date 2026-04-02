// ============================================================
// hooks/useProductSearch.ts — Hook reattivo: ricerca prodotti
//
// Pattern Observer: reagisce ai cambiamenti del searchTerm con
// debounce configurabile, invocando productService.search().
// Restituisce stato di ricerca, risultati e setter.
// Consumato da ProductSearch per disaccoppiare logica e UI.
// ============================================================

import { useState, useEffect } from 'react';
import { productService } from '@/services';
import type { Product } from '@/types';

export function useProductSearch(debounceMs = 300) {
    const [searchTerm, setSearchTerm] = useState('');
    const [results, setResults] = useState<Product[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    useEffect(() => {
        if (searchTerm.trim().length < 2) {
            setResults([]);
            return;
        }

        setIsSearching(true);
        const timer = setTimeout(async () => {
            const data = await productService.search(searchTerm);
            setResults(data);
            setIsSearching(false);
        }, debounceMs);

        return () => clearTimeout(timer);
    }, [searchTerm, debounceMs]);

    return { searchTerm, setSearchTerm, results, setResults, isSearching };
}
