"use client";
import TopBar from './TopBar';

export type NavItem = 'ticket' | 'analytics' | 'storico' | 'profilo';

interface OperatorLayoutProps {
    activeNav: NavItem;
    onNavChange: (nav: NavItem) => void;
    onProfileClick: () => void;
    onLogout: () => void;
    children: React.ReactNode;
    profileName?: string;
}

const navItems: { id: NavItem; label: string; icon: React.ReactNode }[] = [
    {
        id: 'ticket',
        label: 'Ticket Aperti',
        icon: (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
        ),
    },
    {
        id: 'analytics',
        label: 'Analytics',
        icon: (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 3v18h18" /><path d="M7 14l4-4 3 3 5-6" />
            </svg>
        ),
    },
    {
        id: 'storico',
        label: 'Storico Ordini',
        icon: (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
            </svg>
        ),
    },
    {
        id: 'profilo',
        label: 'Profilo',
        icon: (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
            </svg>
        ),
    },
];

export default function OperatorLayout({ activeNav, onNavChange, onProfileClick, onLogout, children }: OperatorLayoutProps) {
    const sidebarNavItems = navItems.filter(item => item.id !== 'profilo');

    return (
        <div className="h-screen flex flex-col overflow-hidden">
            {/* TopBar */}
            <TopBar onProfileClick={onProfileClick} />

            {/* Desktop: sidebar + main content */}
            <div className="hidden md:flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <aside className="w-60 shrink-0 bg-white border-r border-gray-100 flex flex-col py-4">
                    {/* Logo / Brand */}
                    <div className="px-5 mb-5 flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-[hsl(234,60%,95%)] flex items-center justify-center shrink-0">
                            <svg className="w-4 h-4 text-[hsl(234,60%,36%)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
                                <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
                            </svg>
                        </div>
                        <div>
                            <p className="text-xs font-extrabold text-[hsl(234,60%,36%)] leading-tight">Backoffice</p>
                            <p className="text-[10px] text-gray-400 font-medium leading-tight">Operatore</p>
                        </div>
                    </div>

                    {/* Nav items */}
                    <nav className="flex-1 px-3 space-y-1">
                        {sidebarNavItems.map(item => (
                            <button
                                key={item.id}
                                onClick={() => onNavChange(item.id)}
                                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold transition-all text-left ${
                                    activeNav === item.id
                                        ? 'bg-[hsl(234,60%,36%)] text-white shadow-lg shadow-[hsl(234,60%,36%)]/20'
                                        : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
                                }`}
                            >
                                <span className={activeNav === item.id ? 'text-white' : 'text-gray-400'}>{item.icon}</span>
                                {item.label}
                            </button>
                        ))}
                    </nav>

                    {/* Logout */}
                    <div className="px-3 pt-4 border-t border-gray-100 mt-4">
                        <button
                            onClick={onLogout}
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold text-red-500 hover:bg-red-50 transition-all"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                            </svg>
                            Logout
                        </button>
                    </div>
                </aside>

                {/* Main content */}
                <main className="flex-1 overflow-hidden bg-[hsl(230,25%,97%)] p-4">
                    <div className="h-full bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                        {children}
                    </div>
                </main>
            </div>

            {/* Mobile: content + bottom tab bar */}
            <div className="md:hidden flex-1 flex flex-col overflow-hidden">
                <main className="flex-1 overflow-hidden bg-[hsl(230,25%,97%)] p-3">
                    <div className="h-full bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                        {children}
                    </div>
                </main>

                {/* Bottom tab bar */}
                <nav className="shrink-0 bg-white border-t border-gray-100 flex">
                    {sidebarNavItems.map(item => (
                        <button
                            key={item.id}
                            onClick={() => onNavChange(item.id)}
                            className={`flex-1 flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-bold transition-colors relative ${
                                activeNav === item.id
                                    ? 'text-[hsl(234,60%,36%)]'
                                    : 'text-gray-400'
                            }`}
                        >
                            {activeNav === item.id && (
                                <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-[hsl(234,60%,36%)] rounded-b-full" />
                            )}
                            {item.icon}
                            {item.label}
                        </button>
                    ))}
                    <button
                        onClick={onLogout}
                        className="flex-1 flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-bold text-red-400"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                        </svg>
                        Logout
                    </button>
                </nav>
            </div>
        </div>
    );
}
