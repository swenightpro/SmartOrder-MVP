// ============================================================
// components/ui/EmptyState.tsx — Placeholder per liste vuote
//
// Componente atomico che mostra un'icona e un messaggio quando
// una lista è vuota (carrello, storico, chat). Tre varianti
// icona: cart, list, chat.
// ============================================================

interface EmptyStateProps {
    icon?: 'cart' | 'list' | 'chat';
    message: string;
    className?: string;
}

const icons = {
    cart: (
        <svg className="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" />
            <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
        </svg>
    ),
    list: <span className="text-3xl opacity-50">📋</span>,
    chat: (
        <svg className="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
    ),
};

export default function EmptyState({ icon = 'cart', message, className = '' }: EmptyStateProps) {
    return (
        <div className={`flex-1 flex flex-col items-center justify-center text-gray-300 text-sm italic text-center gap-2 min-h-[120px] ${className}`}>
            {icons[icon]}
            <span>{message}</span>
        </div>
    );
}
