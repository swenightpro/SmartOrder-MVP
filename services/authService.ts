import type { UserProfile } from '@/types';
import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';

export const authService = {
    login: async (email: string, password: string): Promise<{ cod_cli: number; rag_soc: string; role: string }> => {
        const res = await apiFetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || data?.detail || data?.message || 'Login fallito');
        const user = data?.user;
        if (!user) throw new Error('Risposta login non valida');
        const cod_cli = user.cod_cli != null ? Number(user.cod_cli) : 0;
        return { cod_cli, rag_soc: user.rag_soc || '', role: user.role || 'customer' };
    },

    getProfile: async (): Promise<UserProfile | null> => {
        const res = await apiFetch('/auth/me');
        if (!res.ok) return null;
        const data = await res.json();
        return data?.user || null;
    },

    changePassword: async (currentPassword: string, newPassword: string, confirmNewPassword: string): Promise<void> => {
        const res = await apiFetch('/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword,
                confirm_new_password: confirmNewPassword,
            }),
        });
        if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Errore cambio password'));
    },

    logout: async (): Promise<void> => {
        await apiFetch('/auth/logout', { method: 'POST' });
    },

    getExportFolder: async (): Promise<string | null> => {
        const res = await apiFetch('/auth/export-folder');
        if (!res.ok) return null;
        const data = await res.json();
        return data?.export_folder || null;
    },

    setExportFolder: async (path: string | null): Promise<void> => {
        const res = await apiFetch('/auth/export-folder', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ export_folder: path }),
        });
        const status = res.status;
        const statusText = res.statusText;
        let errorDetail = '';
        try {
            const data = await res.json();
            errorDetail = data?.error || data?.detail || data?.message || '';
        } catch {
            errorDetail = await res.text();
        }
        if (!res.ok) {
            throw new Error(`[${status} ${statusText}] ${errorDetail || 'Errore sconosciuto'}`);
        }
    },
};
