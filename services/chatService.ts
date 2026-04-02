// ============================================================
// services/chatService.ts — Facade per chat AI e trascrizione
//
// Espone sendMessage (invio messaggio alla IA), getMessages
// (storico sessione) e transcribe (speech-to-text via Whisper).
// Consumato da ChatPanel per l'interazione conversazionale.
// ============================================================

import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';
import type { Message } from '@/types';

export interface ChatApiResponse {
    success?: boolean;
    response?: string;
    message?: string;
    error?: string;
    user_message_id?: number;
    ai_message_id?: number;
    product_items?: { cod_art: string; quantity: number }[];
    product_codes?: string[];
    product_confidences?: Record<string, number>;
    order_confirmed?: boolean;
    cart_edits?: { cart_item_id: number; action: string; new_quantity?: number }[];
    edit_confirmed?: boolean;
}

export const chatService = {
    sendMessage: async (
        message: string,
        clientId: number,
        history: { role: string; content: string }[],
        sessionId: number | null,
        pendingCartEdits?: unknown[] | null
    ): Promise<ChatApiResponse> => {
        const res = await apiFetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                clientId,
                history: history.slice(-10),
                session_id: sessionId,
                pending_cart_edits: pendingCartEdits,
            }),
        });

        if (!res.ok) throw new Error(await getApiErrorMessage(res, `Errore ${res.status}`));
        return res.json();
    },

    getMessages: async (sessionId: number): Promise<Message[]> => {
        const res = await apiFetch(`/messages?session_id=${sessionId}`);
        if (!res.ok) return [];

        const data = await res.json();
        const apiMessages = Array.isArray(data.messages) ? data.messages : [];

        return apiMessages.map((msg: any) => {
            let suggestedProducts = [];

            try {
                if (typeof msg.metadata === 'string') {
                    const parsed = JSON.parse(msg.metadata);
                    suggestedProducts = parsed?.suggested_products || [];
                } else if (msg.metadata) {
                    suggestedProducts = msg.metadata.suggested_products || [];
                }
            } catch (e) {
                console.error('Error parsing metadata', e);
            }

            return {
                id: String(msg.id),
                dbId: msg.id,
                role: msg.sender === 'user' ? 'user' : 'assistant',
                content: msg.content,
                suggestedProducts,
            };
        });
    },

    transcribe: async (audioBlob: Blob): Promise<string> => {
        const formData = new FormData();
        formData.append('file', audioBlob, 'audio.webm');

        const res = await apiFetch('/transcribe', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore trascrizione'));
        const data = await res.json();
        return data.text || '';
    },
};
