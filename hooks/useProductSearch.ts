import { useState, useEffect, useCallback } from 'react';
import { productService } from '@/services';
import type { Product } from '@/types';

export function useProductSearch(debounceMs = 300) {
    const [searchTerm, setSearchTerm] = useState('');
    const [results, setResults] = useState<Product[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    const doSearch = useCallback(async (term: string) => {
        const trimmed = term.trim();
        if (trimmed.length < 2) {
            setResults([]);
            setIsSearching(false);
            return;
        }

        setIsSearching(true);
        const data = await productService.search(trimmed);
        setResults(data);
        setIsSearching(false);
    }, []);

    useEffect(() => {
        let timer: ReturnType<typeof setTimeout>;
        if (searchTerm.trim().length < 2) {
            // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: clear results immediately on trim < 2
            doSearch(searchTerm);
        } else {
            timer = setTimeout(() => doSearch(searchTerm), debounceMs);
        }
        return () => clearTimeout(timer);
    }, [searchTerm, debounceMs, doSearch]);

    return { searchTerm, setSearchTerm, results, setResults, isSearching };
}
