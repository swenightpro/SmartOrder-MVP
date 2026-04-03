import type { OrderSummary } from '@/types';

interface OrderCardProps {
    order: OrderSummary;
    index: number;
    onClick: () => void;
}

export default function OrderCard({ order, index, onClick }: OrderCardProps) {
    // Formatta la data in modo stabile (UTC) per evitare mismatch SSR/client
    const formattedDate = (() => {
        try {
            const d = new Date(order.data_ord);
            const day = String(d.getUTCDate()).padStart(2, '0');
            const month = String(d.getUTCMonth() + 1).padStart(2, '0');
            const year = d.getUTCFullYear();
            return `${day}/${month}/${year}`;
        } catch {
            return order.data_ord;
        }
    })();

    const hasMessages = (order.message_count || 0) > 0;
    const preview = order.preview_items || [];
    const extraCount = Number(order.item_count) - preview.length;

    return (
        <div
            className="border border-gray-100 rounded-2xl overflow-hidden animate-slide-up bg-white hover:border-[hsl(234,60%,80%)] hover:shadow-md transition-all cursor-pointer"
            style={{ animationDelay: `${index * 50}ms` }}
            onClick={onClick}
        >
            {/* Order header */}
            <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-gray-50 border-b border-gray-100">
                <div className="flex items-center gap-3 min-w-0">
                    <span className="shrink-0 flex items-center gap-1.5 text-xs font-extrabold text-[hsl(234,60%,36%)] bg-[hsl(234,60%,95%)] border border-[hsl(234,60%,85%)] px-2.5 py-1 rounded-xl">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
                        </svg>
                        #{order.order_id}
                    </span>
                    <span className="text-xs text-gray-500 font-medium">
                        {Number(order.item_count)} prodott{Number(order.item_count) === 1 ? 'o' : 'i'}
                    </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    {hasMessages && (
                        <span className="text-[9px] font-bold text-violet-600 bg-violet-50 border border-violet-200 px-1.5 py-0.5 rounded-md" title="Chat allegata">
                            💬
                        </span>
                    )}
                    <span className="text-xs font-bold text-[hsl(234,60%,36%)]">{formattedDate}</span>
                </div>
            </div>

            {/* Product preview */}
            {preview.length > 0 && (
                <div className="px-4 py-2 space-y-1">
                    {preview.map((p, i) => (
                        <div key={i} className="flex items-center justify-between text-[11px]">
                            <span className="font-medium text-gray-700 truncate max-w-[220px]">{p.des_art || p.cod_art}</span>
                            <span className="text-gray-400 shrink-0 ml-2">×{p.qta_ordinata}</span>
                        </div>
                    ))}
                    {extraCount > 0 && (
                        <p className="text-[10px] text-gray-400 font-medium">+{extraCount} altr{extraCount === 1 ? 'o' : 'i'}</p>
                    )}
                </div>
            )}
        </div>
    );
}
