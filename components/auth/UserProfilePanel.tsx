"use client";
import { useState, useEffect } from 'react';
import type { Client, UserProfile } from '@/types';
import { authService } from '@/services';

interface UserProfilePanelProps {
    client: Client;
    onLogout: () => void;
    hideLogout?: boolean;
}

function formatDate(d: string | null | undefined): string {
    if (!d) return '—';
    try {
        const dt = new Date(d);
        const day = String(dt.getUTCDate()).padStart(2, '0');
        const months = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'];
        const month = months[dt.getUTCMonth()];
        const year = dt.getUTCFullYear();
        return `${day} ${month} ${year}`;
    } catch { return '—'; }
}

export default function UserProfilePanel({ client, onLogout, hideLogout = false }: UserProfilePanelProps) {
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [changingPassword, setChangingPassword] = useState(false);
    const [currentPw, setCurrentPw] = useState('');
    const [newPw, setNewPw] = useState('');
    const [confirmPw, setConfirmPw] = useState('');
    const [pwError, setPwError] = useState('');
    const [pwSuccess, setPwSuccess] = useState('');
    const [pwLoading, setPwLoading] = useState(false);
    const [logoutLoading, setLogoutLoading] = useState(false);

    // Export folder state (admin only)
    const [editingFolder, setEditingFolder] = useState(false);
    const [exportFolder, setExportFolder] = useState('');
    const [folderLoading, setFolderLoading] = useState(true);
    const [folderSaving, setFolderSaving] = useState(false);
    const [folderError, setFolderError] = useState('');
    const [folderSuccess, setFolderSuccess] = useState('');

    useEffect(() => {
        authService.getProfile().then(p => { if (p) setProfile(p); }).catch(() => { });
    }, [client]);

    useEffect(() => {
        if (profile?.role === 'admin') {
            setFolderLoading(true);
            authService.getExportFolder()
                .then(f => { setExportFolder(f || ''); setFolderLoading(false); })
                .catch(() => { setExportFolder(''); setFolderLoading(false); });
        }
    }, [profile]);

    const handleChangePassword = async () => {
        setPwError(''); setPwSuccess('');
        if (!currentPw) { setPwError('Inserisci la password attuale'); return; }
        if (!newPw || newPw.length < 6) { setPwError('La nuova password deve avere almeno 6 caratteri'); return; }
        if (newPw !== confirmPw) { setPwError('Le due password non corrispondono'); return; }
        if (currentPw === newPw) { setPwError('La nuova password deve essere diversa da quella attuale'); return; }

        setPwLoading(true);
        try {
            await authService.changePassword(currentPw, newPw, confirmPw);
            setPwSuccess('Password aggiornata con successo');
            setCurrentPw(''); setNewPw(''); setConfirmPw(''); setChangingPassword(false);
            const updated = await authService.getProfile();
            if (updated) setProfile(updated);
        } catch (e) { setPwError(e instanceof Error ? e.message : 'Errore di rete'); }
        finally { setPwLoading(false); }
    };

    const handleSaveFolder = async () => {
        setFolderError('');
        setFolderSuccess('');
        setFolderSaving(true);
        try {
            const path = exportFolder.trim() || null;
            await authService.setExportFolder(path);
            setFolderSuccess('Cartella salvata');
            setEditingFolder(false);
        } catch (e) {
            setFolderError(e instanceof Error ? e.message : 'Errore di rete');
        } finally {
            setFolderSaving(false);
        }
    };

    const handleLogout = async () => {
        setLogoutLoading(true);
        try { await authService.logout(); onLogout(); }
        finally { setLogoutLoading(false); }
    };

    const isAdmin = profile?.role === 'admin';
    const isOperator = profile?.role === 'admin' || profile?.role === 'operator';
    const personalAreaTitle = isOperator ? 'Area personale operatore' : 'Area personale cliente';

    return (
        <>
            <div className="px-8 pt-8 pb-5">
                <h2 className="text-lg font-extrabold text-gray-900 tracking-tight mb-5">{personalAreaTitle}</h2>
                <div className="space-y-4">
                    {/* Email */}
                    <div>
                        <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Email</label>
                        <div className="w-full px-4 py-3 rounded-2xl text-sm bg-gray-50 text-gray-700 border-2 border-gray-100 font-medium">{profile?.email || '...'}</div>
                    </div>
                    {/* Ragione sociale (solo customer) */}
                    {!isOperator && (
                        <div>
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Ragione Sociale</label>
                            <div className="w-full px-4 py-3 rounded-2xl text-sm bg-gray-50 text-gray-700 border-2 border-gray-100 font-medium">{profile?.rag_soc || client.rag_soc || '...'}</div>
                        </div>
                    )}

                    {/* Export folder — solo admin */}
                    {isAdmin && (
                        <div>
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                                Cartella Esportazione Ordini
                            </label>
                            {folderLoading ? (
                                <div className="w-full px-4 py-3 rounded-2xl text-sm bg-gray-50 border-2 border-gray-100 text-gray-400">Caricamento...</div>
                            ) : !editingFolder ? (
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 px-4 py-3 rounded-2xl text-sm bg-gray-50 border-2 border-gray-100 text-gray-600 font-mono truncate" title={exportFolder || undefined}>
                                        {exportFolder || <span className="italic text-gray-400 font-sans">Non configurata</span>}
                                    </div>
                                    <button
                                        onClick={() => { setEditingFolder(true); setFolderError(''); setFolderSuccess(''); }}
                                        className="shrink-0 px-4 py-3 rounded-2xl text-xs font-bold border-2 border-[hsl(234,60%,85%)] text-[hsl(234,60%,36%)] hover:bg-[hsl(234,60%,96%)] transition-colors">
                                        {exportFolder ? 'Modifica' : 'Configura'}
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-2.5 animate-slide-down">
                                    <input
                                        type="text"
                                        value={exportFolder}
                                        onChange={e => setExportFolder(e.target.value)}
                                        placeholder="/Users/davide/ordini"
                                        className="w-full px-4 py-3 rounded-2xl text-sm bg-gray-50 text-gray-800 border-2 border-gray-200 outline-none focus:border-[hsl(234,60%,50%)] transition-all font-mono"
                                    />
                                    <p className="text-[10px] text-gray-400 -mt-1">
                                        Path assoluto della cartella dove verranno salvati i file ordine (es. <span className="font-mono">/Users/davide/ordini</span>).
                                    </p>
                                    {folderError && <div className="text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">{folderError}</div>}
                                    {folderSuccess && <div className="text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2 animate-fade-in">{folderSuccess}</div>}
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => { setEditingFolder(false); setFolderError(''); }}
                                            className="flex-1 py-2.5 rounded-2xl text-xs font-bold border-2 border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors">
                                            Annulla
                                        </button>
                                        <button
                                            onClick={handleSaveFolder}
                                            disabled={folderSaving}
                                            className="flex-1 py-2.5 rounded-2xl text-xs font-bold bg-[hsl(234,60%,36%)] text-white hover:bg-[hsl(234,60%,30%)] disabled:opacity-60 transition-all">
                                            {folderSaving ? 'Salvataggio...' : 'Salva'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Password */}
                    <div>
                        <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Password</label>
                        {!changingPassword ? (
                            <div className="flex items-center gap-2">
                                <div className="flex-1 px-4 py-3 rounded-2xl text-sm bg-gray-50 text-gray-400 border-2 border-gray-100 font-mono tracking-widest">••••••••</div>
                                <button onClick={() => { setChangingPassword(true); setPwError(''); setPwSuccess(''); }}
                                    className="shrink-0 px-4 py-3 rounded-2xl text-xs font-bold border-2 border-[hsl(234,60%,85%)] text-[hsl(234,60%,36%)] hover:bg-[hsl(234,60%,96%)] transition-colors">Modifica</button>
                            </div>
                        ) : (
                            <div className="space-y-2.5 animate-slide-down">
                                <input type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} placeholder="Password attuale"
                                    className="w-full px-4 py-3 rounded-2xl text-sm bg-gray-50 text-gray-800 border-2 border-gray-200 outline-none focus:border-[hsl(234,60%,50%)] transition-all" />
                                <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} placeholder="Nuova password"
                                    className="w-full px-4 py-3 rounded-2xl text-sm bg-gray-50 text-gray-800 border-2 border-gray-200 outline-none focus:border-[hsl(234,60%,50%)] transition-all" />
                                <input type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === 'Enter') handleChangePassword(); }} placeholder="Conferma nuova password"
                                    className="w-full px-4 py-3 rounded-2xl text-sm bg-gray-50 text-gray-800 border-2 border-gray-200 outline-none focus:border-[hsl(234,60%,50%)] transition-all" />
                                {pwError && <div className="text-xs font-semibold text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">{pwError}</div>}
                                <div className="flex gap-2">
                                    <button onClick={() => { setChangingPassword(false); setCurrentPw(''); setNewPw(''); setConfirmPw(''); setPwError(''); }}
                                        className="flex-1 py-2.5 rounded-2xl text-xs font-bold border-2 border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors">Annulla</button>
                                    <button onClick={handleChangePassword} disabled={pwLoading}
                                        className="flex-1 py-2.5 rounded-2xl text-xs font-bold bg-[hsl(234,60%,36%)] text-white hover:bg-[hsl(234,60%,30%)] disabled:opacity-60 transition-all">
                                        {pwLoading ? 'Salvataggio...' : 'Salva password'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                    {pwSuccess && <div className="text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2 animate-fade-in">{pwSuccess}</div>}
                    {/* Account dates */}
                    <div className="flex gap-3 pt-2">
                        <div className="flex-1">
                            <label className="block text-[9px] font-bold text-gray-300 uppercase tracking-wider mb-1">Account creato</label>
                            <p className="text-xs text-gray-500 font-medium">{formatDate(profile?.created_at)}</p>
                        </div>
                        <div className="flex-1">
                            <label className="block text-[9px] font-bold text-gray-300 uppercase tracking-wider mb-1">Ultima modifica password</label>
                            <p className="text-xs text-gray-500 font-medium">{formatDate(profile?.updated_at)}</p>
                        </div>
                    </div>
                </div>
            </div>
            {/* Logout — nascosto quando il layout padre ha già il proprio bottone logout */}
            {!hideLogout && (
                <div className="px-8 pb-8 pt-2">
                    <button onClick={handleLogout} disabled={logoutLoading}
                        className="w-full py-3 rounded-2xl text-sm font-bold border-2 border-red-200 text-red-600 hover:bg-red-50 transition-all disabled:opacity-60">
                        {logoutLoading ? 'Logout...' : 'Logout'}
                    </button>
                </div>
            )}
        </>
    );
}
