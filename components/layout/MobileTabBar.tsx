// ============================================================
// components/layout/MobileTabBar.tsx — Barra tab mobile (Chat, Carrello, Storico)
//
// Visibile solo su schermi piccoli (md:hidden). Tre tab con
// icone e badge conteggio articoli sul tab Carrello.
// ============================================================

interface MobileTabBarProps {
    activePanel: 'chat' | 'cart' | 'history';
    cartCount: number;
    onTabChange: (panel: 'chat' | 'cart' | 'history') => void;
}

export default function MobileTabBar({ activePanel, cartCount, onTabChange }: MobileTabBarProps) {
    const tabs = [
        {
            id: 'chat' as const,
            label: 'Chat',
            icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>,
        },
        {
            id: 'cart' as const,
            label: 'Carrello',
            icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" /><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" /></svg>,
            badge: cartCount > 0 ? cartCount : undefined,
        },
        {
            id: 'history' as const,
            label: 'Storico',
            icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>,
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
                    {tab.icon}
                    {tab.label}
                    {tab.badge && (
                        <span className="absolute top-1 right-1/4 w-4 h-4 bg-[hsl(234,60%,36%)] text-white text-[8px] font-bold rounded-full flex items-center justify-center">
                            {tab.badge}
                        </span>
                    )}
                </button>
            ))}
        </div>
    );
}
