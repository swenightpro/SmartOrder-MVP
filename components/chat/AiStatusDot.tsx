"use client";

import { useHealthCheck } from '@/hooks';

interface AiStatusDotProps {
    hasOpenTicket?: boolean;
    ticketStatus?: 'aperto' | 'in_lavorazione' | null;
}

export default function AiStatusDot({ hasOpenTicket = false, ticketStatus = null }: AiStatusDotProps) {
    const status = useHealthCheck(30_000);

    // Ticket mode: show operator status instead of AI status
    if (hasOpenTicket) {
        const isOperatorOnline = ticketStatus === 'in_lavorazione';
        return (
            <div className="flex items-center gap-1.5" title={isOperatorOnline ? 'Operatore online' : 'In attesa di un operatore'}>
                <span className={`w-2 h-2 rounded-full ${isOperatorOnline ? 'bg-emerald-400 shadow-[0_0_4px_rgba(16,185,129,0.6)]' : 'bg-amber-400 animate-pulse'}`} />
                <span className={`text-[10px] font-medium ${isOperatorOnline ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {isOperatorOnline ? 'Operatore online' : 'In attesa di un operatore...'}
                </span>
            </div>
        );
    }

    const color = status === 'ok' ? 'bg-emerald-400' : status === 'error' ? 'bg-red-400' : 'bg-gray-300';

    return (
        <div className="flex items-center gap-1.5" title={status === 'ok' ? 'Assistente AI attivo' : status === 'error' ? 'Assistente Offline' : '…'}>
            <span className={`w-2 h-2 rounded-full ${color} ${status === 'ok' ? 'shadow-[0_0_4px_rgba(16,185,129,0.6)]' : ''}`} />
            <span className="text-[10px] text-gray-400 font-medium">
                {status === 'ok' ? 'AI' : status === 'error' ? 'Offline' : '…'}
            </span>
        </div>
    );
}
