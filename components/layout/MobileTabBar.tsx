interface MobileTabBarProps {
    activePanel: 'chat' | 'cart' | 'history' | 'assistenza';
    cartCount: number;
    onTabChange: (panel: 'chat' | 'cart' | 'history' | 'assistenza') => void;
    hasOpenTicket?: boolean;
}

export default function MobileTabBar({ activePanel, cartCount, onTabChange, hasOpenTicket = false }: MobileTabBarProps) {
    const tabs: { id: MobileTabBarProps['activePanel']; label: string; icon: React.ReactNode; badge?: number; urgent?: boolean }[] = [
        {
            id: 'chat',
            label: 'Chat',
            icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>,
        },
        {
            id: 'cart',
            label: 'Carrello',
            icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" /><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" /></svg>,
            badge: cartCount > 0 ? cartCount : undefined,
        },
        {
            id: 'history',
            label: 'Storico',
            icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>,
        },
        {
            id: 'assistenza',
            label: 'Assistenza',
            icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 3h18v4H3z" /><path d="M19 9H5" /><circle cx="7.5" cy="13.5" r="4.5" /><circle cx="17.5" cy="13.5" r="4.5" />
                </svg>
            ),
            urgent: hasOpenTicket,
        },
    ];

    return (
        <div className="md:hidden shrink-0 bg-white border-b border-gray-100 flex">
            {tabs.map(tab => (
                <button
                    key={tab.id}
                    onClick={() => onTabChange(tab.id)}
                    className={`flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-bold transition-colors relative ${activePanel === tab.id ? 'text-[hsl(234,60%,36%)] border-b-2 border-[hsl(234,60%,36%)]' : 'text-gray-400'
                        }`}
                >
                    <span className="relative">
                        {tab.icon}
                        {tab.badge && (
                            <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-[hsl(234,60%,36%)] text-white text-[8px] font-bold rounded-full flex items-center justify-center">
                                {tab.badge}
                            </span>
                        )}
                        {tab.urgent && (
                            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" />
                        )}
                    </span>
                    {tab.label}
                </button>
            ))}
        </div>
    );
}
