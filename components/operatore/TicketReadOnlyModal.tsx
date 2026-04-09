"use client";
import { useState, useEffect, useRef, useCallback } from 'react';
import type { OperatorTicketDetail, CartItem, FeedbackReadOnly } from '@/types';
import { ticketService, cartService } from '@/services';
import { ConfidenceRing } from '@/components/ui';
import { formatChatMessage, ImageMessageBubble } from '@/components/chat/ChatMessage';
import { useSSE } from '@/hooks/useSSE';

interface TicketReadOnlyModalProps {
    ticketId: number;
    onClose: () => void;
}

interface ChatMessageUI {
    id: string;
    dbId?: number;
    role: 'user' | 'assistant' | 'system';
    content: string;
    imageData?: string;
    ocrText?: string;
    feedbacks?: FeedbackReadOnly[];
}

export default function TicketReadOnlyModal({ ticketId, onClose }: TicketReadOnlyModalProps) {
    const [detail, setDetail] = useState<OperatorTicketDetail | null>(null);
    const [messages, setMessages] = useState<ChatMessageUI[]>([]);
    const [cartItems, setCartItems] = useState<CartItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const chatRef = useRef<HTMLDivElement>(null);

    const refreshCartItems = useCallback(async () => {
        try {
            const cartData = await cartService.getCart(detail?.session_id);
            setCartItems(Array.isArray(cartData) ? cartData : []);
        } catch { /* ignore */ }
    }, [detail?.session_id]);

    useEffect(() => {
        let mounted = true;
        const init = async () => {
            setLoading(true);
            setError('');
            try {
                const data = await ticketService.getTicketDetail(ticketId);
                if (!mounted) return;
                setDetail(data);
                setCartItems(data.cart_items || []);
                const msgs: ChatMessageUI[] = (data.messages || []).map((m: { id: number; sender: string; content: string; image_data?: string; ocr_text?: string }) => ({
                    id: String(m.id),
                    dbId: m.id,
                    role: m.sender === 'user' ? 'user' : m.sender === 'system' ? 'system' : 'assistant',
                    content: m.content,
                    imageData: m.image_data,
                    ocrText: m.ocr_text,
                    feedbacks: Array.isArray((m as { feedbacks?: FeedbackReadOnly[] }).feedbacks)
                        ? (m as { feedbacks?: FeedbackReadOnly[] }).feedbacks
                        : [],
                }));
                setMessages(msgs);
            } catch (e) {
                if (mounted) setError(e instanceof Error ? e.message : 'Errore di rete');
            } finally {
                if (mounted) setLoading(false);
            }
        };
        init();
        return () => { mounted = false; };
    }, [ticketId]);

    // SSE: aggiornamenti in tempo reale (solo lettura)
    useSSE(detail?.session_id ? `/sse/${detail.session_id}` : null, {
        onEvent: (event) => {
            if (event.type === 'message') {
                const msg = event.data as { id: number; sender: string; content: string };
                setMessages(prev => {
                    const prevIds = new Set(prev.map(m => m.dbId ?? m.id));
                    if (prevIds.has(msg.id)) return prev;
                    const role = msg.sender === 'user' ? 'user' : msg.sender === 'system' ? 'system' : 'assistant';
                    return [...prev, { id: String(msg.id), dbId: msg.id, role, content: msg.content }];
                });
            } else if (event.type === 'image_message') {
                const img = event.data as { id: number; image_data: string; ocr_text?: string };
                setMessages(prev => {
                    const prevIds = new Set(prev.map(m => m.dbId ?? m.id));
                    if (prevIds.has(img.id)) return prev;
                    return [...prev, {
                        id: String(img.id), dbId: img.id, role: 'user' as const,
                        content: '', imageData: img.image_data, ocrText: img.ocr_text,
                    }];
                });
            } else if (event.type === 'ticket_update') {
                const update = event.data as { status: 'aperto' | 'in_lavorazione' | 'chiuso' };
                setDetail(prev => prev ? { ...prev, status: update.status } : prev);
                if (update.status === 'chiuso') onClose();
            } else if (event.type === 'cart_update') {
                void refreshCartItems();
            }
        },
    });

    useEffect(() => {
        if (!detail?.session_id) return;
        const fallback = setInterval(() => { void refreshCartItems(); }, 60_000);
        return () => clearInterval(fallback);
    }, [detail?.session_id, refreshCartItems]);

    useEffect(() => {
        if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }, [messages]);

    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);

    const renderFeedbacks = (feedbacks: FeedbackReadOnly[] | undefined) => {
        if (!feedbacks || feedbacks.length === 0) return null;
        return (
            <div className="mt-1.5 space-y-1">
                {feedbacks.map((fb) => (
                    <div
                        key={fb.id}
                        className={`px-2 py-1 rounded-lg border text-[10px] leading-snug ${
                            fb.is_positive
                                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                                : 'bg-rose-50 border-rose-200 text-rose-700'
                        }`}
                    >
                        <p className="font-bold">
                            Feedback cliente: {fb.is_positive ? 'Positivo' : 'Negativo'}
                        </p>
                        {fb.reason_category && <p>Motivo: {fb.reason_category}</p>}
                        {fb.comment && <p className="italic">&quot;{fb.comment}&quot;</p>}
                    </div>
                ))}
            </div>
        );
    };

    return (
        <div
            className="fixed inset-0 z-[200] flex items-center justify-center p-4 animate-fade-in"
            style={{ background: 'rgba(15, 20, 50, 0.55)', backdropFilter: 'blur(4px)' }}
            onClick={onClose}
        >
            <div
                className="relative bg-white rounded-3xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden animate-scale-in"
                onClick={e => e.stopPropagation()}
            >
                {/* Header con banner sola lettura */}
                <div className="shrink-0 px-6 py-4 border-b border-gray-100 bg-[hsl(230,25%,97%)]">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 flex-wrap">
                            {detail ? (
                                <>
                                    <span className="text-sm font-extrabold text-gray-900">Ticket #{ticketId}</span>
                                    <span className="text-gray-300">•</span>
                                    <span className="text-xs font-mono bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded border border-gray-200">
                                        {detail.cod_cli}
                                    </span>
                                    <span className="text-sm font-bold text-gray-700">{detail.rag_soc}</span>
                                    <span className="text-[10px] font-bold text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                                        In carico ad altro operatore
                                    </span>
                                </>
                            ) : (
                                <span className="text-sm font-extrabold text-gray-400">Caricamento...</span>
                            )}
                        </div>
                        <button
                            onClick={onClose}
                            className="w-9 h-9 rounded-xl flex items-center justify-center text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    </div>
                    <div className="mt-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700 font-medium">
                        Modalit&agrave; sola lettura &mdash; questo ticket &egrave; gestito da un altro operatore.
                    </div>
                </div>

                {/* Body */}
                {loading ? (
                    <div className="flex-1 flex flex-col items-center justify-center py-16 gap-3">
                        <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                        <p className="text-xs text-gray-400 font-medium">Caricamento ticket...</p>
                    </div>
                ) : error ? (
                    <div className="flex-1 flex flex-col items-center justify-center py-16 gap-3 text-red-400">
                        <p className="text-sm font-medium">{error}</p>
                        <button onClick={onClose} className="text-xs font-bold text-[hsl(234,60%,36%)] hover:underline">Chiudi</button>
                    </div>
                ) : (
                    <div className="flex-1 overflow-hidden flex min-h-0">
                        {/* LEFT: Chat (50%) — sola lettura, nessun input */}
                        <div className="w-1/2 flex flex-col overflow-hidden border-r border-gray-100">
                            <div className="shrink-0 px-5 py-3 border-b border-gray-100">
                                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                                    Chat ({messages.length})
                                </p>
                            </div>
                            <div
                                ref={chatRef}
                                className="flex-1 overflow-y-auto px-4 py-4 space-y-2.5 custom-scrollbar"
                                style={{ background: 'linear-gradient(to bottom, hsl(230, 25%, 97%), hsl(230, 20%, 95%))' }}
                            >
                                {messages.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full gap-2 text-gray-300">
                                        <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
                                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                                        </svg>
                                        <p className="text-xs text-gray-400 italic">Nessun messaggio</p>
                                    </div>
                                ) : (
                                    messages.map((msg) => (
                                        msg.imageData ? (
                                            <div key={msg.id}>
                                                <ImageMessageBubble imageData={msg.imageData} ocrText={msg.ocrText} isOperator={true} />
                                                {renderFeedbacks(msg.feedbacks)}
                                            </div>
                                        ) : (
                                            <div
                                                key={msg.id}
                                                className={`flex ${msg.role === 'assistant' ? 'justify-end' : msg.role === 'system' ? 'justify-center' : 'justify-start'}`}
                                            >
                                                <div className="max-w-[88%]">
                                                    <div
                                                        className={`px-3 py-2 text-[12px] leading-relaxed shadow-sm rounded-xl ${
                                                            msg.role === 'assistant'
                                                                ? 'bg-gradient-to-br from-[hsl(234,62%,30%)] to-[hsl(234,55%,40%)] text-white rounded-br-sm'
                                                                : msg.role === 'system'
                                                                ? 'bg-[hsl(210,40%,96%)] border border-[hsl(210,30%,88%)] text-[hsl(210,40%,40%)] text-[11px] italic rounded-bl-sm text-center max-w-full'
                                                                : 'bg-white text-gray-700 border border-gray-100 rounded-bl-sm'
                                                        }`}
                                                    >
                                                        {msg.role === 'system' ? (
                                                            msg.content
                                                        ) : msg.role === 'assistant' ? (
                                                            <span
                                                                className="break-words [&_strong]:font-semibold"
                                                                dangerouslySetInnerHTML={{ __html: formatChatMessage(msg.content) }}
                                                            />
                                                        ) : (
                                                            msg.content
                                                        )}
                                                    </div>
                                                    {msg.role !== 'system' && renderFeedbacks(msg.feedbacks)}
                                                </div>
                                            </div>
                                        )
                                    ))
                                )}
                            </div>
                        </div>

                        {/* RIGHT: Cart (50%) — sola lettura, no azioni */}
                        <div className="flex-1 overflow-y-auto px-5 py-4 custom-scrollbar">
                            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-3">
                                Articoli in carrello ({cartItems.length})
                            </p>

                            {cartItems.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-10 gap-3 text-gray-300">
                                    <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
                                        <circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" />
                                        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
                                    </svg>
                                    <p className="text-sm text-gray-400 italic">Nessun articolo</p>
                                </div>
                            ) : (
                                <div className="space-y-2.5">
                                    {cartItems.map((item) => (
                                        <div
                                            key={item.id}
                                            className="p-3.5 bg-white border border-gray-100 rounded-2xl"
                                        >
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-1.5">
                                                        <p className="text-sm font-bold text-gray-900 leading-tight">
                                                            {item.des_art || item.cod_art || '(senza codice)'}
                                                        </p>
                                                        {item.source === 'ai' && (
                                                            <span className="shrink-0 text-[8px] font-bold text-violet-500 bg-violet-50 border border-violet-200 px-1 py-0.5 rounded leading-none">
                                                                AI
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-1.5 text-[10px] text-gray-400 mb-2 flex-wrap">
                                                        {item.cod_art && (
                                                            <>
                                                                <span className="bg-gray-100 text-gray-600 font-mono px-1.5 py-0.5 rounded-md border border-gray-200">
                                                                    {item.cod_art}
                                                                </span>
                                                                <span className="text-gray-300">•</span>
                                                            </>
                                                        )}
                                                        {item.linea && <span className="uppercase">{item.linea}</span>}
                                                        {item.famiglia && (
                                                            <>
                                                                <span className="text-gray-300">/</span>
                                                                <span className="font-medium text-gray-500">{item.famiglia}</span>
                                                            </>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="px-2.5 py-1 bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] border border-[hsl(234,60%,85%)] rounded-lg text-[12px] font-bold">
                                                            {item.qta}
                                                        </span>
                                                        {item.des_um && (
                                                            <span className="text-[10px] text-gray-400">
                                                                {item.des_um}
                                                                {item.pezzi_conf ? ` (${item.pezzi_conf} ${item.des_tipo_um || ''})` : ''}
                                                            </span>
                                                        )}
                                                    </div>
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
                            )}
                        </div>
                    </div>
                )}

                {/* Footer — solo bottone chiudi */}
                <div className="shrink-0 px-6 py-4 border-t border-gray-100 flex items-center justify-end">
                    <button
                        onClick={onClose}
                        className="px-5 py-2.5 rounded-xl text-sm font-bold border-2 border-gray-200 text-gray-600 hover:bg-gray-50 transition-all"
                    >
                        Chiudi
                    </button>
                </div>
            </div>
        </div>
    );
}
