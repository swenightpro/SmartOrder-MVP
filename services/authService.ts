// ============================================================
// services/authService.ts — Facade per autenticazione utente
//
// Espone login, getProfile, changePassword e logout.
// Incapsula le chiamate al backend FastAPI /auth/*.
// Consumato da LoginForm, UserProfilePanel e page.tsx.
// ============================================================

import type { UserProfile } from '@/types';
import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';

export const authService = {
    login: async (email: string, password: string): Promise<{ cod_cli: number; rag_soc: string }> => {
        const res = await apiFetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || data?.detail || data?.message || 'Login fallito');
        const user = data?.user;
        if (!user?.cod_cli || !user?.rag_soc) throw new Error('Risposta login non valida');
        return { cod_cli: Number(user.cod_cli), rag_soc: user.rag_soc };
    },

    getProfile: async (): Promise<UserProfile | null> => {
        const res = await apiFetch('/auth/me');
        if (!res.ok) return null;
        const data = await res.json();
        return data?.user || null;
    },

    changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
        const res = await apiFetch('/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore cambio password'));
    },

    logout: async (): Promise<void> => {
        await apiFetch('/auth/logout', { method: 'POST' });
    },
};
