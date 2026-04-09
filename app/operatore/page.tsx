"use client";
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import type { UserProfile } from '@/types';
import { authService, orderService } from '@/services';
import { ToastProvider, useToast } from '@/components/ui';
import OperatorLayout, { type NavItem } from '@/components/layout/OperatorLayout';
import TicketDashboard from '@/components/operatore/TicketDashboard';
import OperatorAnalyticsDashboard from '@/components/operatore/OperatorAnalyticsDashboard';
import OperatorOrderHistory from '@/components/operatore/OperatorOrderHistory';
import UserProfilePanel from '@/components/auth/UserProfilePanel';

function OperatoreContent() {
    const router = useRouter();
    const { showToast } = useToast();
    const [loading, setLoading] = useState(true);
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [activeNav, setActiveNav] = useState<NavItem>('ticket');
    const [client, setClient] = useState<{ cod_cli: number; rag_soc: string } | null>(null);
    const [showProfileModal, setShowProfileModal] = useState(false);

    useEffect(() => {
        const checkAuth = async () => {
            try {
                const p = await authService.getProfile();
                if (!p) {
                    router.replace('/');
                    return;
                }
                if (p.role !== 'admin') {
                    router.replace('/');
                    return;
                }
                setProfile(p);
                setClient({ cod_cli: p.cod_cli, rag_soc: p.rag_soc });

                // Export batch automatico su login
                const folder = await authService.getExportFolder();
                if (folder) {
                    try {
                        const result = await orderService.exportBatch({}, 50);
                        if (result.failed_count > 0 || result.errors.length > 0) {
                            showToast(
                                `Export: ${result.exported_count} ordini esportati, ${result.failed_count} falliti. Controlla la console.`,
                                'error'
                            );
                        } else if (result.exported_count > 0) {
                            showToast(`${result.exported_count} ordini esportati automaticamente`, 'success');
                        }
                    } catch (e: unknown) {
                        const msg = e instanceof Error ? e.message : String(e);
                        showToast(`Errore export automatico: ${msg}`, 'error');
                    }
                }
            } catch {
                router.replace('/');
            } finally {
                setLoading(false);
            }
        };
        checkAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [router]);

    const handleLogout = async () => {
        try { await authService.logout(); } catch { /* ignore */ }
        router.replace('/');
    };

    if (loading) {
        return (
            <div className="h-screen flex items-center justify-center bg-[hsl(230,25%,97%)]">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                    <p className="text-xs text-gray-400 font-medium">Caricamento...</p>
                </div>
            </div>
        );
    }

    if (!profile || !client) return null;

    return (
        <>
            {showProfileModal && (
                <div
                    className="fixed inset-0 z-[250] flex items-center justify-center bg-gray-100 animate-fade-in text-gray-900"
                    onClick={() => setShowProfileModal(false)}
                >
                    <div className="absolute top-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-slate-300/30 blur-3xl pointer-events-none" />
                    <div className="absolute bottom-[-15%] left-[-10%] w-[400px] h-[400px] rounded-full bg-slate-200/40 blur-3xl pointer-events-none" />

                    <div className="relative w-full max-w-md mx-4 animate-scale-in" onClick={e => e.stopPropagation()}>
                        <button
                            onClick={() => setShowProfileModal(false)}
                            className="absolute -top-12 right-0 p-2 text-slate-400 hover:text-slate-700 transition-colors"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>

                        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden">
                            <UserProfilePanel client={client} onLogout={() => router.replace('/')} />
                        </div>
                    </div>
                </div>
            )}

            <OperatorLayout
                activeNav={activeNav}
                onNavChange={setActiveNav}
                onProfileClick={() => setShowProfileModal(true)}
                onLogout={handleLogout}
                profileName={profile.rag_soc}
            >
                {activeNav === 'ticket' && <TicketDashboard />}
                {activeNav === 'analytics' && <OperatorAnalyticsDashboard />}
                {activeNav === 'storico' && <OperatorOrderHistory />}
            </OperatorLayout>
        </>
    );
}

export default function OperatorePage() {
    return (
        <ToastProvider>
            <OperatoreContent />
        </ToastProvider>
    );
}
