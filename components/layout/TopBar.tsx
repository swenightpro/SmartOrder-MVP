// ============================================================
// components/layout/TopBar.tsx — Header principale dell'applicazione
//
// Barra superiore fissa con logo, link "Contattaci" e avatar
// utente. Il click sull'avatar apre l'overlay di profilo.
// ============================================================

import Image from 'next/image';

interface TopBarProps {
    onProfileClick: () => void;
}

export default function TopBar({ onProfileClick }: TopBarProps) {
    return (
        <header className="shrink-0 bg-white border-b border-gray-100 shadow-sm z-30">
            <div className="flex items-center gap-3 px-4 py-2.5">
                {/* Logo */}
                <div className="shrink-0 flex items-center gap-2">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center">
                        <Image src="/icon.png" alt="SmartOrder" width={24} height={24} className="rounded-md object-contain" priority />
                    </div>
                    <span className="hidden sm:block text-lg font-extrabold tracking-tight">
                        <span className="text-[hsl(234,62%,26%)]">Smart</span>
                        <span className="text-[hsl(234,55%,44%)]">Order</span>
                    </span>
                </div>

                <div className="flex-1" />

                {/* Contact */}
                <a
                    href="mailto:assistenza@nightpro.it?subject=Richiesta%20Assistenza%20SmartOrder&body=Salve%20team%20di%20supporto,%0A%0A%5BScrivi%20qui%20la%20tua%20richiesta%5D"
                    className="flex flex-row items-center justify-center gap-2 shrink-0 px-3 py-1.5 rounded-xl text-sm font-bold text-[hsl(234,60%,40%)] bg-[hsl(234,60%,96%)] hover:bg-[hsl(234,60%,92%)] transition-colors whitespace-nowrap"
                >
                    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21.2 8.4c.5.38.8.97.8 1.6v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V10a2 2 0 0 1 .8-1.6l8-6a2 2 0 0 1 2.4 0l8 6Z" />
                        <path d="m22 10-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 10" />
                    </svg>
                    Contattaci
                </a>

                {/* User avatar */}
                <button
                    onClick={onProfileClick}
                    className="w-9 h-9 rounded-xl bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors shrink-0"
                >
                    <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                    </svg>
                </button>
            </div>
        </header>
    );
}
