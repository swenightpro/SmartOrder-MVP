import { apiFetch } from '@/lib/apiClient';

export const feedbackService = {
    submit: (messageId: number, isPositive: boolean, reason?: string | null, comment?: string) =>
        apiFetch('/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message_id: messageId,
                is_positive: isPositive,
                reason_category: reason || null,
                comment: comment || null,
            }),
        }),

    delete: (messageId: number) =>
        apiFetch('/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message_id: messageId, action: 'delete' }),
        }),
};
