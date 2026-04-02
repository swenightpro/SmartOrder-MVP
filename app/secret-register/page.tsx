"use client";

import React, { useState } from 'react';
import ClientSelector, { Client } from '@/components/auth/ClientSelector';
import { apiFetch, getApiErrorMessage } from '@/lib/apiClient';

export default function SecretRegisterPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState<'customer' | 'admin'>('customer');
    const [client, setClient] = useState<Client | null>(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        if (role === 'customer' && !client) {
            setMessage({ text: 'Seleziona un cliente per il ruolo customer', type: 'error' });
            setLoading(false);
            return;
        }

        try {
            const res = await apiFetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email,
                    password,
                    role,
                    cod_cli: role === 'customer' ? client?.cod_cli : null,
                }),
            });

            if (!res.ok) {
                throw new Error(await getApiErrorMessage(res, "Errore durante la creazione dell'utente"));
            }

            await res.json().catch(() => null);

            setMessage({ text: 'Utente creato con successo! Ora puoi accedere.', type: 'success' });
            setEmail('');
            setPassword('');
            setClient(null);
        } catch (err: unknown) {
            setMessage({ text: err instanceof Error ? err.message : 'Errore Sconosciuto', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const generateRandomPassword = () => {
        const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
        let pw = '';
        for (let i = 0; i < 12; i++) {
            pw += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        setPassword(pw);
    };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-200 overflow-hidden w-full h-full font-sans">
            <div className="relative w-full max-w-md mx-4">

                <div className="bg-white rounded-3xl shadow-xl border border-gray-100 overflow-visible">
                    <div className="px-8 pt-10 pb-6 text-center">
                        <h1 className="text-2xl font-black text-slate-800 tracking-tight mb-2">
                            🧑‍💻 Crea Utente
                        </h1>
                    </div>

                    <div className="px-8 pb-8">
                        <form className="space-y-[18px]" onSubmit={handleSubmit}>
                            {message && (
                                <div className={`text-[11px] font-semibold px-3 py-2 rounded-xl animate-in fade-in slide-in-from-top-2 ${message.type === 'success' ? 'bg-[#f0f9f5] border border-[#bbf7d0] text-emerald-700' : 'bg-red-50 border border-red-100 text-red-600'}`}>
                                    {message.text}
                                </div>
                            )}

                            <div>
                                <label className="block text-[11px] font-bold text-gray-500 mb-2 uppercase tracking-widest">Email</label>
                                <input
                                    type="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full px-4 py-3.5 rounded-2xl text-[14px] transition-all outline-none border border-gray-200 focus:border-[#60a5fa] hover:border-gray-300 text-gray-800 placeholder-gray-400"
                                    placeholder="utente@azienda.it"
                                />
                            </div>

                            <div>
                                <div className="flex justify-between items-center mb-2">
                                    <label className="block text-[11px] font-bold text-gray-500 uppercase tracking-widest">Password</label>
                                    <button
                                        type="button"
                                        onClick={generateRandomPassword}
                                        className="text-[11px] font-bold text-gray-600 hover:text-gray-900 transition-colors flex items-center gap-1.5 bg-gray-100/80 hover:bg-gray-200 px-3 py-1 rounded-[8px]"
                                    >
                                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
                                        </svg>
                                        Genera
                                    </button>
                                </div>
                                <div className="relative">
                                    <input
                                        type="text"
                                        required
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="w-full px-4 py-3.5 rounded-2xl text-[14px] transition-all outline-none border border-gray-200 focus:border-[#60a5fa] hover:border-gray-300 text-gray-800 tracking-wide placeholder-gray-400"
                                        placeholder="Minimo 6 caratteri..."
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-[11px] font-bold text-gray-500 mb-2 uppercase tracking-widest">Ruolo</label>
                                <div className="relative">
                                    <select
                                        value={role}
                                        onChange={(e) => {
                                            setRole(e.target.value as 'customer' | 'admin');
                                            if (e.target.value === 'admin') setClient(null);
                                        }}
                                        className="block w-full px-4 py-3.5 rounded-2xl text-[14px] transition-all outline-none border border-gray-200 focus:border-[#60a5fa] hover:border-gray-300 text-gray-800 cursor-pointer !appearance-none bg-transparent pr-12 relative z-10 m-0"
                                        style={{ WebkitAppearance: 'none', MozAppearance: 'none', appearance: 'none', borderRadius: '1rem', background: 'transparent' }}
                                    >
                                        <option value="customer">Cliente (Customer)</option>
                                        <option value="admin">Amministratore (Admin)</option>
                                    </select>
                                    <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none z-20 text-gray-400">
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </div>
                                </div>
                            </div>

                            {role === 'customer' && (
                                <div className="mt-1 text-left w-full relative z-50">
                                    <label className="block text-[11px] font-bold text-gray-500 mb-2 uppercase tracking-widest">Azienda Associata</label>
                                    <ClientSelector
                                        onClientChange={setClient}
                                        currentClient={client}
                                        isOverlay={false}
                                    />
                                </div>
                            )}

                            <div className="pt-2" style={{ marginTop: '1.5rem' }}>
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className={`w-full py-4 rounded-2xl text-[14px] font-bold text-white bg-[hsl(234,60%,36%)] hover:bg-[hsl(234,60%,30%)] active:bg-[hsl(234,60%,24%)] transition-all ${loading ? 'opacity-70 cursor-wait' : 'hover:-translate-y-0.5 shadow-[0_4px_14px_rgba(29,35,85,0.25)] hover:shadow-[0_6px_20px_rgba(29,35,85,0.3)]'
                                        }`}
                                >
                                    {loading ? (
                                        <span className="flex justify-center items-center gap-2">
                                            <svg className="animate-spin h-5 w-5 text-white/80" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                            Salvataggio...
                                        </span>
                                    ) : (
                                        'Genera Utente'
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    );
}
