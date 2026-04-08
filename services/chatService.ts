import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';
import type { Message, ProductLinkWithCode, ImageUploadResponse, DisambiguationCandidate } from '@/types';

export interface ChatApiResponse {
    success?: boolean;
    response?: string;
    message?: string;
    error?: string;
    user_message_id?: number;
    ai_message_id?: number;
    product_items?: { cod_art: string; quantity: number }[];
    product_codes?: string[];
    product_codes_with_names?: ProductLinkWithCode[];
    product_confidences?: Record<string, number>;
    intent?: 'ORDER' | 'CLARIFICATION' | 'ADVICE' | 'CONFIRMATION' | 'CART_EDIT' | 'REORDER';
    order_confirmed?: boolean;
    cart_edits?: { cart_item_id: number; action: string; new_quantity?: number }[];
    edit_confirmed?: boolean;
    is_proposal?: boolean;  // true when the assistant's last message was a proposal
    disambiguation_candidates?: DisambiguationCandidate[];
}

export const chatService = {
    sendMessage: async (
        message: string,
        clientId: number,
        sessionId: number | null,
        pendingCartEdits?: unknown[] | null
    ): Promise<ChatApiResponse> => {
        const res = await apiFetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                clientId,
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

        return apiMessages.map((msg: {
            id: number;
            sender: string;
            content: string;
            metadata?: string | Record<string, unknown>;
            image_data?: string | null;
            feedback?: { is_positive?: boolean } | null;
        }) => {
            let suggestedProducts: unknown[] = [];

            try {
                const meta: Record<string, unknown> = typeof msg.metadata === 'string'
                    ? JSON.parse(msg.metadata) as Record<string, unknown>
                    : (msg.metadata as Record<string, unknown>) || {};
                // Supporta sia il vecchio schema (suggested_products) sia il nuovo (products_proposed)
                suggestedProducts =
                    (Array.isArray(meta.products_proposed) ? meta.products_proposed : null) ??
                    (Array.isArray(meta.suggested_products) ? meta.suggested_products : []);
            } catch (e) {
                console.error('Error parsing metadata', e);
            }

            return {
                id: String(msg.id),
                dbId: msg.id,
                role: (msg.sender === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
                content: msg.content,
                suggestedProducts,
                feedback: typeof msg.feedback?.is_positive === 'boolean'
                    ? { is_positive: msg.feedback.is_positive }
                    : null,
                // Restore image data for image messages (base64 from DB)
                imageData: msg.image_data || undefined,
            };
        });
    },

    saveMessage: async (sessionId: number, sender: 'user' | 'ai' | 'system', content: string): Promise<number> => {
        const res = await apiFetch('/chat/save-message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, sender, content }),
        });
        if (!res.ok) return 0;
        const data = await res.json();
        return data.message_id || 0;
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

    uploadImage: async (
        imageBlob: Blob,
        _sessionId: number | null
    ): Promise<ImageUploadResponse> => {
        const formData = new FormData();
        formData.append('file', imageBlob, 'image.jpg');

        const res = await apiFetch('/chat/image', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `Errore ${res.status}` }));
            throw new Error(err.detail || 'Errore upload immagine');
        }
        return res.json();
    },
};
