// ============================================================
// components/cart/ProductCard.tsx — Card di conferma prodotto selezionato
//
// Mostra il dettaglio del prodotto scelto dalla ricerca, con
// stepper quantità e pulsante di aggiunta al carrello.
// Usa il componente atomico QuantityStepper per l'input numerico.
// ============================================================

"use client";
import { useState } from 'react';
import type { Product } from '@/types';

interface ProductCardProps {
    product: Product;
    onAdd: (qty: number) => void;
    onDeselect: () => void;
    error?: string;
}

export default function ProductCard({ product, onAdd, onDeselect, error }: ProductCardProps) {
    const [qty, setQty] = useState<number | ''>(1);

    const handleQtyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;
        if (value === '') setQty('');
        else {
            const numValue = parseInt(value);
            if (!isNaN(numValue) && numValue >= 0) setQty(numValue);
        }
    };

    return (
        <div className="p-4 bg-[hsl(234,60%,97%)] border-2 border-[hsl(234,60%,85%)] rounded-2xl space-y-3 animate-scale-in">
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold leading-tight text-gray-900 mb-1">{product.des_art}</p>
                    <div className="flex items-center gap-1.5 text-[10px] text-gray-400 flex-wrap">
                        <span className="font-mono bg-white text-[hsl(234,60%,36%)] border border-[hsl(234,60%,85%)] px-1.5 py-0.5 rounded-md">{product.cod_art}</span>
                        {product.linea && (
                            <>
                                <span className="text-gray-300">•</span>
                                <span className="uppercase">{product.linea}</span>
                            </>
                        )}
                        {product.famiglia && (
                            <>
                                <span className="text-gray-300">/</span>
                                <span className="font-medium text-gray-500">{product.famiglia}</span>
                            </>
                        )}
                    </div>
                    {product.des_um && (
                        <p className="text-[10px] text-gray-400 mt-1">
                            Venduto in {product.des_um}{product.pezzi_conf ? ` (${product.pezzi_conf} ${product.des_tipo_um || ''})` : ''}
                        </p>
                    )}
                </div>
                <button
                    onClick={onDeselect}
                    className="shrink-0 w-7 h-7 flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors text-sm"
                >
                    ✕
                </button>
            </div>
            <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => setQty(typeof qty === 'number' ? Math.max(1, qty - 1) : 1)}
                        className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-red-50 hover:border-red-200 hover:text-red-500 transition-all text-sm font-bold"
                    >
                        −
                    </button>
                    <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={qty}
                        onChange={handleQtyChange}
                        className="w-12 h-7 text-center border-2 border-gray-200 rounded-lg text-sm font-bold text-gray-800 bg-white outline-none focus:border-[hsl(234,60%,50%)] [appearance:textfield]"
                    />
                    <button
                        onClick={() => setQty(typeof qty === 'number' ? qty + 1 : 2)}
                        className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-600 transition-all text-sm font-bold"
                    >
                        +
                    </button>
                </div>
                <button
                    onClick={() => onAdd(typeof qty === 'number' ? qty : 1)}
                    disabled={!qty || qty < 1}
                    className="flex-1 h-9 bg-[hsl(234,60%,36%)] text-white rounded-xl text-xs font-bold hover:bg-[hsl(234,60%,30%)] shadow-sm active:scale-[0.98] transition-all disabled:opacity-40 disabled:pointer-events-none"
                >
                    Aggiungi al carrello
                </button>
            </div>
            {error && (
                <div className="p-2.5 bg-red-50 text-red-600 rounded-xl text-xs font-bold border border-red-100 animate-scale-in">
                    ⚠️ {error}
                </div>
            )}
        </div>
    );
}
