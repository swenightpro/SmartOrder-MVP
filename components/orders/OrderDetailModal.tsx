// ============================================================
// components/orders/OrderDetailModal.tsx — Modale dettaglio ordine
//
// Visualizza il dettaglio completo di un ordine: articoli ordinati
// e storico conversazione chat. Supporta il click su un articolo
// per scrollare al messaggio chat corrispondente (highlight).
// Delega il caricamento dati al Facade orderService.getDetail().
// ============================================================

"use client";
import { useState, useEffect, useRef } from 'react';
import type { OrderDetail } from '@/types';
import { orderService } from '@/services';
import { formatChatMessage } from '@/components/chat/ChatMessage';
import { SectionHeader, ConfidenceRing } from '@/components/ui';

interface OrderDetailModalProps {
    orderId: number;
    codCli: number;
    onClose: () => void;
}

export default function OrderDetailModal({ orderId, codCli, onClose }: OrderDetailModalProps) {
    const [detail, setDetail] = useState<OrderDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const chatRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        let mounted = true;

        orderService.getDetail(orderId, codCli)
            .then(data => {
                if (mounted) { setDetail(data); setLoading(false); }
            })
            .catch(e => {
                if (mounted) { setError(e instanceof Error ? e.message : 'Errore di rete'); setLoading(false); }
            });

        return () => { mounted = false; };
    }, [orderId, codCli]);


    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);

    const formattedDate = detail
        ? new Date(detail.data_ord).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' })
        : '';

    const scrollToMessage = (messageId: number) => {
        if (!chatRef.current) return;
        const wrapper = chatRef.current.querySelector(`[data-msg-id="${messageId}"]`);
        if (!wrapper) return;
        const bubble = wrapper.querySelector('.msg-bubble') as HTMLElement | null;
        const target = bubble || wrapper;
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.classList.add('highlight-pulse');
        setTimeout(() => target.classList.remove('highlight-pulse'), 2200);
    };

    const hasChat = detail && detail.messages.length > 0;

    return (
        <div
            className="fixed inset-0 z-[200] flex items-center justify-center p-4 animate-fade-in"
            style={{ background: 'rgba(15, 20, 50, 0.55)', backdropFilter: 'blur(4px)' }}
            onClick={onClose}
        >
            <div
                className="relative bg-white rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-scale-in"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="shrink-0 px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-wrap">
                        <span className="flex items-center gap-1.5 text-sm font-extrabold text-[hsl(234,60%,36%)]">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
                            </svg>
                            Ordine #{orderId}
                        </span>
                        {detail && (
                            <>
                                <span className="text-[10px] text-gray-300">•</span>
                                <span className="text-xs text-gray-500 font-medium">{formattedDate}</span>
                            </>
                        )}
                    </div>
                    <button onClick={onClose} className="w-9 h-9 rounded-xl flex items-center justify-center text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="flex-1 overflow-hidden flex">
                    {loading ? (
                        <div className="flex-1 flex flex-col items-center justify-center py-16 gap-3">
                            <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                            <p className="text-xs text-gray-400 font-medium">Caricamento dettagli...</p>
                        </div>
                    ) : error ? (
                        <div className="flex-1 flex flex-col items-center justify-center py-16 gap-3 text-red-400">
                            <span className="text-3xl">⚠️</span>
                            <p className="text-sm font-medium">{error}</p>
                        </div>
                    ) : detail ? (
                        <>
                            {/* Chat panel (LEFT) */}
                            {hasChat && (
                                <div className="w-[45%] flex flex-col overflow-hidden border-r border-gray-100">
                                    <div className="shrink-0 px-5 py-3 border-b border-gray-100">
                                        <SectionHeader label="Chat dell'ordine" count={detail.messages.length} />
                                    </div>
                                    <div ref={chatRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-2.5 custom-scrollbar" style={{ background: 'linear-gradient(to bottom, hsl(230, 25%, 97%), hsl(230, 20%, 95%))' }}>
                                        <style>{`
                      .highlight-pulse {
                        animation: msgPulse 2.2s ease-out;
                      }
                      @keyframes msgPulse {
                        0%, 100% { box-shadow: none; }
                        15%, 70% { box-shadow: 0 0 0 3px hsl(234, 60%, 50%, 0.35); }
                      }
                    `}</style>
                                        {detail.messages.map((msg) => (
                                            <div
                                                key={msg.id}
                                                data-msg-id={msg.id}
                                                className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} transition-all duration-300`}
                                            >
                                                <div className={`msg-bubble max-w-[85%] px-3 py-2 text-[12px] leading-relaxed shadow-sm rounded-xl transition-shadow duration-300 ${msg.sender === 'user'
                                                    ? 'bg-gradient-to-br from-[hsl(234,62%,30%)] to-[hsl(234,55%,40%)] text-white rounded-br-sm'
                                                    : 'bg-white text-gray-700 border border-gray-100 rounded-bl-sm'
                                                    }`}>
                                                    {msg.sender === 'user' ? (
                                                        msg.content
                                                    ) : (
                                                        <span className="break-words [&_strong]:font-semibold" dangerouslySetInnerHTML={{ __html: formatChatMessage(msg.content) }} />
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Products panel (RIGHT, or full if no chat) */}
                            <div className="flex-1 overflow-y-auto px-5 py-3 custom-scrollbar">
                                <SectionHeader label="Articoli ordinati" count={detail.items.length} />
                                <div className="space-y-3">
                                    {detail.items.map((item, idx) => (
                                        <div
                                            key={item.id}
                                            className={`p-4 bg-white border rounded-2xl hover:shadow-md transition-all animate-slide-up border-gray-100 ${item.related_message_id ? 'cursor-pointer hover:border-[hsl(234,60%,80%)]' : ''}`}
                                            style={{ animationDelay: `${idx * 40}ms` }}
                                            onClick={() => { if (item.related_message_id) scrollToMessage(item.related_message_id); }}
                                        >
                                            <div className="mb-2 flex items-center justify-between gap-2">
                                                <p className="text-sm font-bold text-gray-900 leading-tight">{item.des_art || item.cod_art}</p>
                                                {item.source === 'ai' && (
                                                    <span className="shrink-0 text-[8px] font-bold text-violet-500 bg-violet-50 border border-violet-200 px-1 py-0.5 rounded leading-none">AI</span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-1.5 text-[10px] text-gray-400 mb-2 flex-wrap">
                                                <span className="bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded-md border border-gray-200">{item.cod_art}</span>
                                                {(item.linea || item.famiglia) && (
                                                    <>
                                                        <span className="text-gray-300">•</span>
                                                        <span className="uppercase tracking-tight">{item.linea}</span>
                                                        <span className="text-gray-300">/</span>
                                                        <span className="font-medium text-gray-500">{item.famiglia}</span>
                                                    </>
                                                )}
                                            </div>
                                            <div className="flex items-end justify-between w-full mt-2">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <span className="bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] border border-[hsl(234,60%,85%)] px-2 py-0.5 rounded-lg text-[11px] font-bold">
                                                        Qta: {item.qta_ordinata}
                                                    </span>
                                                    {item.des_um && (
                                                        <span className="text-[10px] text-gray-400">
                                                            Venduto in {item.des_um}
                                                            {item.pezzi_conf ? ` (${item.pezzi_conf} ${item.des_tipo_um || ''})` : ''}
                                                        </span>
                                                    )}
                                                    {item.related_message_id && (
                                                        <span className="text-[9px] text-gray-400 italic">← vedi in chat</span>
                                                    )}
                                                </div>
                                                {item.ai_confidence != null && (
                                                    <div className="shrink-0 ml-2">
                                                        <ConfidenceRing value={item.ai_confidence} size={32} />
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    ) : null}
                </div>
            </div>
        </div>
    );
}
