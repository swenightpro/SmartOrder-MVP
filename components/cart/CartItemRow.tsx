"use client";
import { useState } from 'react';
import type { CartItem } from '@/types';
import { ConfidenceRing } from '@/components/ui';

interface CartItemRowProps {
    item: CartItem;
    isBlocked?: boolean;
    onRemove: (id: number) => void;
    onUpdateQty: (id: number, newQty: number) => void;
}

const getItemBorderClass = () => {
    return 'border-transparent';
};

export default function CartItemRow({ item, isBlocked = false, onRemove, onUpdateQty }: CartItemRowProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editingQty, setEditingQty] = useState(item.qta);
    const [isUpdating, setIsUpdating] = useState(false);
    const isDraft = !item.cod_art;

    const handleUpdate = async (newQty: number) => {
        setIsUpdating(true);
        await onUpdateQty(item.id, newQty);
        setIsUpdating(false);
        setIsEditing(false);
    };

    return (
        <div className={`relative p-3.5 border rounded-2xl transition-all ${isBlocked
            ? 'bg-red-50 border-red-300'
            : isDraft
                ? 'bg-amber-50 border-amber-200'
                : `bg-white border-gray-100 hover:border-[hsl(234,60%,80%)] hover:shadow-md ${getItemBorderClass()}`
            }`}>
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    {/* Name + AI badge */}
                    <div className="flex items-center gap-2 mb-1.5">
                        <p className={`text-sm font-bold leading-tight ${isBlocked ? 'text-red-700' : isDraft ? 'text-amber-900 italic' : 'text-gray-900'}`}>
                            {item.des_art || item.cod_art}
                        </p>
                        {item.source === 'ai' && (
                            <span className="shrink-0 text-[8px] font-bold text-violet-500 bg-violet-50 border border-violet-200 px-1 py-0.5 rounded leading-none">AI</span>
                        )}
                    </div>

                    {/* Blocked warning */}
                    {isBlocked && (
                        <p className="text-[10px] font-bold text-red-600 mb-1.5">⛔ Articolo non più disponibile — rimuovilo dal carrello</p>
                    )}

                    {/* Details + qty controls */}
                    {!isDraft && (
                        <>
                            <div className="flex items-center gap-1.5 text-[10px] text-gray-400 mb-2 flex-wrap">
                                <span className="bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded-md border border-gray-200">{item.cod_art}</span>
                                {item.linea && (
                                    <>
                                        <span className="text-gray-300">•</span>
                                        <span className="uppercase">{item.linea}</span>
                                    </>
                                )}
                                {item.famiglia && (
                                    <>
                                        <span className="text-gray-300">/</span>
                                        <span className="font-medium text-gray-500">{item.famiglia}</span>
                                    </>
                                )}
                            </div>

                            {/* Quantity controls & Bottom right */}
                            <div className="flex items-end justify-between w-full mt-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <div className="flex items-center gap-1">
                                        <button
                                            onClick={() => handleUpdate(item.qta - 1)}
                                            disabled={isUpdating}
                                            className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-red-50 hover:border-red-200 hover:text-red-500 transition-all text-sm font-bold disabled:opacity-40"
                                        >
                                            −
                                        </button>
                                        {isEditing ? (
                                            <input
                                                type="number"
                                                min="1"
                                                autoFocus
                                                value={editingQty}
                                                onChange={(e) => setEditingQty(Math.max(1, parseInt(e.target.value) || 1))}
                                                onBlur={() => handleUpdate(editingQty)}
                                                onKeyDown={(e) => { if (e.key === 'Enter') handleUpdate(editingQty); }}
                                                className="w-12 h-7 text-center border-2 border-[hsl(234,60%,50%)] rounded-lg text-sm font-bold text-[hsl(234,60%,36%)] bg-white outline-none"
                                            />
                                        ) : (
                                            <button
                                                onClick={() => { setIsEditing(true); setEditingQty(item.qta); }}
                                                disabled={isUpdating}
                                                className="min-w-[2.5rem] h-7 px-2 bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] border border-[hsl(234,60%,85%)] rounded-lg text-[12px] font-bold hover:bg-[hsl(234,60%,90%)] transition-colors cursor-pointer disabled:opacity-40"
                                                title="Clicca per modificare la quantità"
                                            >
                                                {isUpdating ? '...' : item.qta}
                                            </button>
                                        )}
                                        <button
                                            onClick={() => handleUpdate(item.qta + 1)}
                                            disabled={isUpdating}
                                            className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-600 transition-all text-sm font-bold disabled:opacity-40"
                                        >
                                            +
                                        </button>
                                    </div>
                                    {item.des_um && (
                                        <span className="text-[10px] text-gray-400">
                                            Venduto in {item.des_um}{item.pezzi_conf ? ` (${item.pezzi_conf} ${item.des_tipo_um || ''})` : ''}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Right side actions */}
                <div className="shrink-0 ml-2 flex flex-col items-end justify-between self-stretch">
                    {/* Remove button */}
                    <button
                        onClick={() => onRemove(item.id)}
                        className="w-8 h-8 flex items-center justify-center text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-xl transition-colors shrink-0"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                    </button>

                    {item.ai_confidence != null && !isDraft && (
                        <div className="mt-auto">
                            <ConfidenceRing value={item.ai_confidence} size={32} />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
