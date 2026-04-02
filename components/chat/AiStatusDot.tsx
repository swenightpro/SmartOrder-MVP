// ============================================================
// components/chat/AiStatusDot.tsx — Indicatore stato backend
//
// Pallino colorato (verde/rosso/giallo) che mostra in tempo reale
// se il backend Python è raggiungibile. Usa l'hook useHealthCheck
// (pattern Observer) per polling periodico dello stato.
// ============================================================

"use client";

import { useHealthCheck } from '@/hooks';

export default function AiStatusDot() {
    const status = useHealthCheck(30_000);

    const color = status === 'ok' ? 'bg-emerald-400' : status === 'error' ? 'bg-red-400' : 'bg-gray-300';
    const label = status === 'ok' ? 'Backend Online' : status === 'error' ? 'Backend Offline' : '…';

    return (
        <div className="flex items-center gap-1.5" title={label}>
            <span className={`w-2 h-2 rounded-full ${color} ${status === 'ok' ? 'shadow-[0_0_4px_rgba(16,185,129,0.6)]' : ''}`} />
            <span className="text-[10px] text-gray-400 font-medium">
                {status === 'ok' ? 'Backend Online' : status === 'error' ? 'Backend Offline' : '…'}
            </span>
        </div>
    );
}
