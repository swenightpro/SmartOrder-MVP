// ============================================================
// components/auth/LoginForm.tsx — Form di autenticazione utente
//
// Gestisce l'input email/password e la validazione lato client.
// Delega l'autenticazione al Facade authService.login().
// In caso di successo notifica il parent tramite callback onLogin.
// ============================================================

"use client";
import { useState } from 'react';
import Image from 'next/image';
import type { Client } from '@/types';
import { authService } from '@/services';

interface LoginFormProps {
    onLogin: (client: Client) => void;
}

export default function LoginForm({ onLogin }: LoginFormProps) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleLogin = async () => {
        setError('');
        if (!email.trim() || !password.trim()) { setError('Inserisci email e password'); return; }

        setLoading(true);
        try {
            const user = await authService.login(email.trim(), password);
            onLogin({ cod_cli: user.cod_cli, rag_soc: user.rag_soc });
            setPassword('');
        } catch (e) { setError(e instanceof Error ? e.message : 'Errore di rete durante il login'); }
        finally { setLoading(false); }
    };

    return (
        <>
            <div className="px-8 pt-10 pb-6 text-center">
                <div className="flex justify-center mb-5">
                    <div className="flex items-center justify-center">
                        <Image src="/icon.png" alt="SmartOrder" width={48} height={48} className="object-contain" priority />
                    </div>
                </div>
                <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight mb-1">Accedi</h1>
                <p className="text-sm text-gray-400">Inserisci le tue credenziali</p>
            </div>
            <div className="px-8 pb-8 space-y-4">
                <div>
                    <label className="block text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">Email</label>
                    <input
                        type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                        placeholder="Inserisci email"
                        className="w-full px-4 py-3.5 rounded-2xl text-sm transition-all outline-none border-2 border-gray-200 focus:border-[hsl(234,60%,50%)] focus:ring-4 focus:ring-[hsl(234,60%,50%)]/10 bg-gray-50 text-gray-800"
                    />
                </div>
                <div>
                    <label className="block text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">Password</label>
                    <input
                        type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleLogin(); }}
                        placeholder="Inserisci password"
                        className="w-full px-4 py-3.5 rounded-2xl text-sm transition-all outline-none border-2 border-gray-200 focus:border-[hsl(234,60%,50%)] focus:ring-4 focus:ring-[hsl(234,60%,50%)]/10 bg-gray-50 text-gray-800"
                    />
                </div>
                {error && (
                    <div className="text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">{error}</div>
                )}
                <input
                    type="button" value={loading ? 'Accesso...' : 'Accedi'} onClick={handleLogin} disabled={loading}
                    className="w-full py-3 rounded-2xl text-sm font-bold bg-[hsl(234,60%,36%)] text-white hover:bg-[hsl(234,60%,30%)] transition-all disabled:opacity-60 cursor-pointer mb-3"
                />

                <div className="pt-4 mt-2 border-t border-gray-100 flex flex-col items-center">
                    <p className="text-xs text-gray-400 mb-2">Hai bisogno di maggiore assistenza?</p>
                    <a
                        href="mailto:assistenza@nightpro.it?subject=Richiesta%20Assistenza%20Generica%20SmartOrder&body=Salve%20team%20di%20supporto,%0A%0AAvrei%20bisogno%20di%20assistenza%20in%20merito%20a:%0A%0A%5BScrivi%20qui%20la%20tua%20richiesta%5D"
                        className="flex flex-row items-center justify-center gap-2 px-3 py-1.5 rounded-xl text-sm font-bold text-[hsl(234,60%,40%)] bg-[hsl(234,60%,96%)] hover:bg-[hsl(234,60%,92%)] transition-colors whitespace-nowrap"
                    >
                        <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21.2 8.4c.5.38.8.97.8 1.6v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V10a2 2 0 0 1 .8-1.6l8-6a2 2 0 0 1 2.4 0l8 6Z" />
                            <path d="m22 10-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 10" />
                        </svg>
                        Contatta il Supporto
                    </a>
                </div>
            </div>
        </>
    );
}
