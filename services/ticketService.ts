import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';
import type { Ticket, OperatorTicketDetail, OperatorPlatformOverview } from '@/types';

export const ticketService = {
    // Get all open/in-progress tickets (operator)
    getOpenTickets: async (): Promise<Ticket[]> => {
        const res = await apiFetch('/tickets');
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore caricamento ticket'));
        const data = await res.json();
        return data.tickets || [];
    },

    // Get ticket detail (operator)
    getTicketDetail: async (ticketId: number): Promise<OperatorTicketDetail> => {
        const res = await apiFetch(`/tickets/${ticketId}`);
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore caricamento dettaglio'));
        const data = await res.json();
        return data.ticket;
    },

    // Read-only platform analytics (operator)
    getPlatformUsageOverview: async (days = 14): Promise<OperatorPlatformOverview> => {
        const params = new URLSearchParams({ days: String(days) });
        const res = await apiFetch(`/tickets/analytics/overview?${params.toString()}`);
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore caricamento statistiche'));
        const data = await res.json();
        return data.overview;
    },

    // Lock ticket (operator takes it)
    lockTicket: async (ticketId: number): Promise<void> => {
        const res = await apiFetch(`/tickets/${ticketId}/lock`, { method: 'PATCH' });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore presa in carico ticket'));
    },

    // Unlock ticket (operator releases without closing)
    unlockTicket: async (ticketId: number): Promise<void> => {
        const res = await apiFetch(`/tickets/${ticketId}/unlock`, { method: 'PATCH' });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore rilascio ticket'));
    },

    // Close ticket
    closeTicket: async (ticketId: number, closedBy: 'operator' | 'customer' | 'order_sent' = 'operator'): Promise<void> => {
        const res = await apiFetch(`/tickets/${ticketId}/close`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ closed_by: closedBy }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore chiusura ticket'));
    },

    // Open ticket for current session (customer)
    openTicket: async (sessionId: number): Promise<Ticket> => {
        const res = await apiFetch('/tickets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore apertura ticket'));
        const data = await res.json();
        return data.ticket;
    },

    // Get ticket for current session (customer)
    getTicketBySession: async (sessionId: number): Promise<Ticket | null> => {
        const res = await apiFetch(`/tickets/session/${sessionId}`);
        if (res.status === 404) return null;
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore'));
        const data = await res.json();
        return data.ticket || null;
    },

    // Close ticket from customer side
    closeTicketBySession: async (sessionId: number): Promise<void> => {
        const res = await apiFetch(`/tickets/session/${sessionId}/close`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ closed_by: 'customer' }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore chiusura assistenza'));
    },

    // Send chat message as operator
    sendChatMessage: async (ticketId: number, content: string): Promise<void> => {
        const res = await apiFetch(`/tickets/${ticketId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore invio messaggio'));
    },

    // Send chat message as customer (when ticket is open)
    sendCustomerMessage: async (sessionId: number, content: string): Promise<void> => {
        const res = await apiFetch(`/tickets/session/${sessionId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore invio messaggio'));
    },
};
