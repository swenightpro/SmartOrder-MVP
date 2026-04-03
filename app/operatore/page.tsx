"use client";
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import type { UserProfile } from '@/types';
import { authService } from '@/services';
import OperatorLayout from '@/components/layout/OperatorLayout';
import TicketDashboard from '@/components/operatore/TicketDashboard';
import OperatorOrderHistory from '@/components/operatore/OperatorOrderHistory';
import UserProfilePanel from '@/components/auth/UserProfilePanel';

type NavItem = 'ticket' | 'storico' | 'profilo';

export default function OperatorePage() {
    const router = useRouter();
    const [loading, setLoading] = useState(true);
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [activeNav, setActiveNav] = useState<NavItem>('ticket');
    const [client, setClient] = useState<{ cod_cli: number; rag_soc: string } | null>(null);

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
            } catch {
                router.replace('/');
            } finally {
                setLoading(false);
            }
        };
        checkAuth();
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
        <OperatorLayout
            activeNav={activeNav}
            onNavChange={setActiveNav}
            onLogout={handleLogout}
            profileName={profile.rag_soc}
        >
            {activeNav === 'ticket' && <TicketDashboard />}
            {activeNav === 'storico' && <OperatorOrderHistory />}
            {activeNav === 'profilo' && (
                <div className="h-full overflow-y-auto custom-scrollbar">
                    <UserProfilePanel client={client} onLogout={handleLogout} />
                </div>
            )}
        </OperatorLayout>
    );
}
