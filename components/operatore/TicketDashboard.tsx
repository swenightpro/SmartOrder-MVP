"use client";
import { useState, useEffect, useCallback } from 'react';
import type { Ticket } from '@/types';
import { ticketService } from '@/services';
import TicketSubentroModal from './TicketSubentroModal';
import { useSSE } from '@/hooks/useSSE';

function formatWaiting(minutes?: number): string {
    if (minutes == null) return '—';
    if (minutes < 1) return 'appena';
    if (minutes < 60) return `${Math.round(minutes)} min`;
    const h = Math.floor(minutes / 60);
    const m = Math.round(minutes % 60);
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
}

function waitingVariant(minutes?: number): 'high' | 'mid' | 'low' | 'none' {
    if (minutes == null) return 'none';
    if (minutes > 30) return 'high';
    if (minutes > 10) return 'mid';
    return 'low';
}

function formatDate(iso: string): string {
    try {
        const d = new Date(iso);
        const day = String(d.getUTCDate()).padStart(2, '0');
        const months = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
        const month = months[d.getUTCMonth()];
        const year = d.getUTCFullYear();
        return `${day} ${month} ${year}`;
    } catch { return '—'; }
}

export default function TicketDashboard() {
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const fetchTickets = useCallback(async (showLoader = true) => {
        if (showLoader) setLoading(true);
        else setRefreshing(true);
        setError('');
        try {
            const data = await ticketService.getOpenTickets();
            // Sort by waiting time descending (most urgent first)
            const sorted = [...data].sort((a, b) => {
                const wa = a.waiting_minutes ?? 0;
                const wb = b.waiting_minutes ?? 0;
                return wb - wa;
            });
            setTickets(sorted);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Errore di rete');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        fetchTickets();
    }, [fetchTickets]);

    // Polling: refresh every 15s to update waiting times and catch missed SSE events
    useEffect(() => {
        const interval = setInterval(() => fetchTickets(false), 15_000);
        return () => clearInterval(interval);
    }, [fetchTickets]);

    // SSE: refresh ticket list on any ticket change
    useSSE('/sse/tickets', {
        onEvent: () => {
            fetchTickets(false);
        },
    });

    const handleTicketClosed = () => {
        setSelectedTicketId(null);
        fetchTickets(false);
    };

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                    <p className="text-xs text-gray-400 font-medium">Caricamento ticket...</p>
                </div>
            </div>
        );
    }

    return (
        <>
            {selectedTicketId !== null && (
                <TicketSubentroModal
                    ticketId={selectedTicketId}
                    onUnlocked={handleTicketClosed}
                />
            )}

            <div className="h-full flex flex-col overflow-hidden">
                {/* Header */}
                <div className="shrink-0 px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <h2 className="text-base font-extrabold text-gray-900">Ticket Aperti</h2>
                        <span className="text-[10px] bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] px-2.5 py-0.5 rounded-full font-bold">
                            {tickets.length}
                        </span>
                    </div>
                    <button
                        onClick={() => fetchTickets(false)}
                        disabled={refreshing}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-[hsl(234,60%,36%)] bg-[hsl(234,60%,95%)] hover:bg-[hsl(234,60%,90%)] transition-colors disabled:opacity-50"
                    >
                        <svg className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                        </svg>
                        Aggiorna
                    </button>
                </div>

                {/* Table */}
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    {error ? (
                        <div className="flex flex-col items-center justify-center h-full gap-3 text-red-400">
                            <span className="text-3xl">⚠️</span>
                            <p className="text-sm font-medium">{error}</p>
                            <button onClick={() => fetchTickets()} className="text-xs font-bold text-[hsl(234,60%,36%)] hover:underline">Riprova</button>
                        </div>
                    ) : tickets.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-300">
                            <svg className="w-14 h-14" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                            </svg>
                            <p className="text-sm font-medium text-gray-400">Nessun ticket aperto</p>
                        </div>
                    ) : (
                        <table className="w-full">
                            <thead className="sticky top-0 bg-white z-10">
                                <tr className="border-b border-gray-100">
                                    <th className="px-5 py-2.5 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider">ID</th>
                                    <th className="px-4 py-2.5 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider">Cliente</th>
                                    <th className="px-4 py-2.5 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider hidden sm:table-cell">Ragione Sociale</th>
                                    <th className="px-4 py-2.5 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider hidden md:table-cell">Data Apertura</th>
                                    <th className="px-4 py-2.5 text-left text-[10px] font-bold text-gray-400 uppercase tracking-wider">Attesa</th>
                                </tr>
                            </thead>
                            <tbody>
                                {tickets.map((ticket, idx) => {
                                    const variant = waitingVariant(ticket.waiting_minutes);
                                    return (
                                        <tr
                                            key={ticket.id}
                                            onClick={() => setSelectedTicketId(ticket.id)}
                                            className="border-b border-gray-50 hover:bg-[hsl(234,60%,97%)] cursor-pointer transition-colors animate-slide-up"
                                            style={{ animationDelay: `${idx * 30}ms` }}
                                        >
                                            <td className="px-5 py-3.5">
                                                <span className="text-sm font-mono font-bold text-[hsl(234,60%,36%)]">#{ticket.id}</span>
                                            </td>
                                            <td className="px-4 py-3.5">
                                                <span className="text-xs font-mono text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">
                                                    {ticket.cod_cli}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3.5 hidden sm:table-cell">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm font-bold text-gray-800">{ticket.rag_soc}</span>
                                                    {ticket.status === 'in_lavorazione' && (
                                                        <span className="text-[9px] font-bold text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded-full">
                                                            In carico
                                                        </span>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="px-4 py-3.5 hidden md:table-cell">
                                                <span className="text-xs text-gray-400 font-medium">{formatDate(ticket.created_at)}</span>
                                            </td>
                                            <td className="px-4 py-3.5">
                                                <div className="flex items-center gap-1.5">
                                                    <span className={`inline-block w-2 h-2 rounded-full ${
                                                        variant === 'high' ? 'bg-red-500 animate-pulse' :
                                                        variant === 'mid' ? 'bg-amber-400' :
                                                        variant === 'low' ? 'bg-emerald-400' : 'bg-gray-300'
                                                    }`} />
                                                    <span className={`text-xs font-bold ${
                                                        variant === 'high' ? 'text-red-600' :
                                                        variant === 'mid' ? 'text-amber-600' :
                                                        variant === 'low' ? 'text-emerald-600' : 'text-gray-400'
                                                    }`}>
                                                        {formatWaiting(ticket.waiting_minutes)}
                                                    </span>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </>
    );
}
