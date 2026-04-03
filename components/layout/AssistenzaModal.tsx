"use client";
import { useState, useEffect } from 'react';
import type { Ticket } from '@/types';
import { ticketService } from '@/services';

interface AssistenzaModalProps {
    sessionId: number | null;
    onClose: () => void;
    onTicketChange: () => void;
}

export default function AssistenzaModal({ sessionId, onClose, onTicketChange }: AssistenzaModalProps) {
    const [ticket, setTicket] = useState<Ticket | null>(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!sessionId) { setLoading(false); return; }
        setLoading(true);
        ticketService.getTicketBySession(sessionId)
            .then(t => { setTicket(t); setError(''); })
            .catch(() => { setError('Errore caricamento stato assistenza'); })
            .finally(() => { setLoading(false); });
    }, [sessionId]);

    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);

    const handleOpenTicket = async () => {
        if (!sessionId) return;
        setActionLoading(true);
        setError('');
        try {
            const t = await ticketService.openTicket(sessionId);
            setTicket(t);
            onTicketChange();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Errore apertura assistenza');
        } finally {
            setActionLoading(false);
        }
    };

    const handleCloseTicket = async () => {
        if (!sessionId) return;
        setActionLoading(true);
        setError('');
        try {
            await ticketService.closeTicketBySession(sessionId);
            setTicket(null);
            onTicketChange();
            onClose();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Errore chiusura assistenza');
        } finally {
            setActionLoading(false);
        }
    };

    const statusLabel = (t: Ticket) => {
        if (t.status === 'in_lavorazione') return 'In carico da un operatore';
        if (t.status === 'chiuso') return 'Chiuso';
        return 'In attesa';
    };

    return (
        <div
            className="fixed inset-0 z-[200] flex items-center justify-center p-4 animate-fade-in"
            style={{ background: 'rgba(15, 20, 50, 0.55)', backdropFilter: 'blur(4px)' }}
            onClick={onClose}
        >
            <div
                className="relative bg-white rounded-3xl shadow-2xl w-full max-w-sm p-6 space-y-5 animate-scale-in"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-9 h-9 rounded-xl bg-[hsl(234,60%,95%)] flex items-center justify-center">
                            <svg className="w-5 h-5 text-[hsl(234,60%,36%)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                            </svg>
                        </div>
                        <h3 className="text-base font-extrabold text-gray-900">Assistenza</h3>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-9 h-9 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>

                {loading ? (
                    <div className="flex flex-col items-center gap-3 py-6">
                        <div className="w-7 h-7 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                        <p className="text-xs text-gray-400 font-medium">Caricamento...</p>
                    </div>
                ) : ticket ? (
                    // Ticket open
                    <div className="space-y-4">
                        <div className="flex items-center gap-3 p-4 bg-[hsl(234,60%,96%)] border border-[hsl(234,60%,88%)] rounded-2xl">
                            <div className={`w-3 h-3 rounded-full shrink-0 ${ticket.status === 'in_lavorazione' ? 'bg-amber-400 animate-pulse' : 'bg-blue-400'}`} />
                            <div>
                                <p className="text-sm font-bold text-[hsl(234,60%,36%)]">{statusLabel(ticket)}</p>
                                <p className="text-[11px] text-gray-500 mt-0.5">Ticket #{ticket.id}</p>
                            </div>
                        </div>

                        {ticket.operator_name && (
                            <p className="text-xs text-gray-500">
                                <span className="font-semibold">{ticket.operator_name}</span> sta gestendo la tua richiesta.
                            </p>
                        )}

                        {ticket.status === 'aperto' && (
                            <p className="text-xs text-gray-400">
                                Ti risponderemo il prima possibile. Grazie per la pazienza.
                            </p>
                        )}

                        {error && (
                            <div className="text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 animate-scale-in">
                                ⚠️ {error}
                            </div>
                        )}

                        <button
                            onClick={handleCloseTicket}
                            disabled={actionLoading}
                            className="w-full py-3 rounded-2xl text-sm font-bold border-2 border-red-200 text-red-600 hover:bg-red-50 transition-all disabled:opacity-50"
                        >
                            {actionLoading ? 'Attendere...' : 'Chiudi Assistenza'}
                        </button>
                    </div>
                ) : (
                    // No ticket
                    <div className="space-y-4">
                        <div className="flex flex-col items-center gap-3 py-2 text-center">
                            <div className="w-14 h-14 rounded-2xl bg-[hsl(234,60%,96%)] flex items-center justify-center">
                                <svg className="w-7 h-7 text-[hsl(234,60%,36%)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                                </svg>
                            </div>
                            <div>
                                <p className="text-sm font-bold text-gray-700">Nessuna richiesta di assistenza</p>
                                <p className="text-xs text-gray-400 mt-1">Hai bisogno di aiuto? Apri un ticket e un operatore ti risponderà.</p>
                            </div>
                        </div>

                        {error && (
                            <div className="text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 animate-scale-in">
                                ⚠️ {error}
                            </div>
                        )}

                        <button
                            onClick={handleOpenTicket}
                            disabled={actionLoading || !sessionId}
                            className="w-full py-3 rounded-2xl text-sm font-bold bg-[hsl(234,60%,36%)] text-white hover:bg-[hsl(234,60%,30%)] transition-all disabled:opacity-50"
                        >
                            {actionLoading ? 'Apertura...' : 'Richiedi Assistenza'}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
