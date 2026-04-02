// ============================================================
// components/cart/ProductSearch.tsx — Barra ricerca prodotti con autocomplete
//
// Input di ricerca con dropdown suggerimenti. Usa l'hook
// useProductSearch (pattern Observer) per gestire debounce,
// chiamata API e stato dei risultati in modo reattivo.
// ============================================================

"use client";
import type { Product } from '@/types';
import { useProductSearch } from '@/hooks';

interface ProductSearchProps {
    onSelect: (product: Product) => void;
    compact?: boolean;
}

export default function ProductSearch({ onSelect, compact = false }: ProductSearchProps) {
    const { searchTerm, setSearchTerm, results: suggestions, setResults: setSuggestions } = useProductSearch();

    const handleSelect = (product: Product) => {
        onSelect(product);
        setSearchTerm('');
        setSuggestions([]);
    };

    return (
        <div className="relative">
            <label className={`block text-[10px] font-bold text-gray-400 uppercase tracking-wider ${compact ? 'mb-1.5' : 'mb-2'}`}>
                Aggiungi Articolo
            </label>
            <input
                type="text"
                autoComplete="off"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onFocus={() => { if (searchTerm.length >= 2) { /* trigger search already handled by effect */ } }}
                onBlur={() => { setTimeout(() => setSuggestions([]), 200); }}
                className={`w-full outline-none text-sm bg-white transition-all ${compact
                    ? 'px-3.5 py-2.5 border-2 border-gray-200 rounded-xl focus:border-[hsl(234,60%,50%)]'
                    : 'px-4 py-3 border-2 border-gray-200 rounded-2xl focus:border-[hsl(234,60%,50%)] focus:ring-4 focus:ring-[hsl(234,60%,50%)]/10'
                    }`}
                placeholder={compact ? "Cerca articolo..." : "Digita nome o codice dell'articolo..."}
            />
            {suggestions.length > 0 && (
                <div className={`absolute w-full bg-white border border-gray-100 shadow-2xl z-[110] overflow-y-auto divide-y divide-gray-50 custom-scrollbar animate-slide-down ${compact ? 'mt-1.5 rounded-xl max-h-[200px]' : 'mt-2 rounded-2xl max-h-[220px]'}`}>
                    {suggestions.map((p) => (
                        <div
                            key={p.cod_art}
                            onClick={() => handleSelect(p)}
                            className={`hover:bg-[hsl(234,60%,97%)] cursor-pointer group transition-colors ${compact ? 'px-3.5 py-2.5' : 'p-3'}`}
                        >
                            <p className={`font-bold text-gray-800 leading-tight group-hover:text-[hsl(234,60%,36%)] ${compact ? 'text-xs mb-0.5' : 'text-sm mb-1'}`}>
                                {p.des_art}
                            </p>
                            <div className={`flex items-center gap-1.5 text-gray-400 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>
                                <span className="bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded-md border border-gray-200">{p.cod_art}</span>
                                <span className="text-gray-300">•</span>
                                <span className="uppercase">{p.linea}</span>
                                <span className="text-gray-300">/</span>
                                <span className="font-medium text-gray-500">{p.famiglia}</span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
