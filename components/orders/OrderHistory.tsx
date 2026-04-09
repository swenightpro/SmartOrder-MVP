"use client";
import { useState, useEffect, useRef, useCallback } from 'react';
import type { OrderSummary, OrderFilters } from '@/types';
import { orderService } from '@/services';
import OrderDetailModal from './OrderDetailModal';
import OrderCard from './OrderCard';
import { EmptyState } from '@/components/ui';

export default function OrderHistory({ cod_cli }: { cod_cli: string }) {
    const [orders, setOrders] = useState<OrderSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);

    // Filtri UC_29, UC_30, UC_31
    const [sortBy, setSortBy] = useState<OrderFilters['sortBy']>('data_ord');
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
    const [searchInput, setSearchInput] = useState('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');

    const searchTimerRef = useRef<ReturnType<typeof setTimeout>>(null);

    const currentFilters = useCallback((): OrderFilters => ({
        search: searchInput || undefined,
        sortBy,
        sortDir,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
    }), [searchInput, sortBy, sortDir, dateFrom, dateTo]);

    const fetchOrders = useCallback(async (pageNum: number, f: OrderFilters) => {
        try {
            setLoading(true);

            const data = await orderService.list(Number(cod_cli), pageNum, f);
            const noFilters = !f.search && !f.dateFrom && !f.dateTo;

            const limit = noFilters ? 50 : 15;
            setOrders(data);
            setHasMore(data.length >= limit);
        } catch (e) {
            console.error(e);
            setOrders([]);
            setHasMore(false);
        } finally {
            setLoading(false);
        }
    }, [cod_cli]);

    // Apply filters and reset
    const applyFilters = useCallback((f: OrderFilters) => {
        setPage(0);
        setHasMore(true);
        fetchOrders(0, f);
    }, [fetchOrders]);

    // Debounced search
    const handleSearchChange = (val: string) => {
        setSearchInput(val);
        if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
        searchTimerRef.current = setTimeout(() => {
            applyFilters({ ...currentFilters(), search: val || undefined });
        }, 400);
    };

    const handleDateFromChange = (val: string) => {
        setDateFrom(val);
        applyFilters({ ...currentFilters(), dateFrom: val || undefined });
    };

    const handleDateToChange = (val: string) => {
        setDateTo(val);
        applyFilters({ ...currentFilters(), dateTo: val || undefined });
    };

    const handleClearFilters = () => {
        setSearchInput('');
        setDateFrom('');
        setDateTo('');
        setSortBy('data_ord');
        setSortDir('desc');
        applyFilters({ sortBy: 'data_ord', sortDir: 'desc' });
    };

    const hasActiveFilters = Boolean(searchInput || dateFrom || dateTo);

    useEffect(() => {
        if (!cod_cli) return;
        setPage(0);
        fetchOrders(0, currentFilters());
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [cod_cli]);

    useEffect(() => {
        return () => {
            if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
        };
    }, []);

    const goToPage = (p: number) => {
        if (p < 0 || p === page) return;
        setPage(p);
        fetchOrders(p, currentFilters());
    };

    return (
        <>
            {selectedOrderId !== null && (
                <OrderDetailModal orderId={selectedOrderId} codCli={Number(cod_cli)} onClose={() => setSelectedOrderId(null)} />
            )}

            <div className="h-full flex flex-col overflow-hidden">
                {/* Header con filtri */}
                <div className="shrink-0 px-4 pt-3 pb-2 space-y-2">
                    <div className="flex items-center justify-between">
                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Storico Ordini</label>
                    </div>

                    {/* Riga ricerca */}
                    <div className="relative">
                        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                            <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                        </svg>
                        <input
                            type="text"
                            value={searchInput}
                            onChange={e => handleSearchChange(e.target.value)}
                            placeholder="Cerca per ID ordine..."
                            className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-gray-200 bg-white text-gray-700 placeholder-gray-400 outline-none focus:border-[hsl(234,60%,50%)] transition-colors"
                        />
                    </div>

                    {/* Riga date */}
                    <div className="flex gap-2 items-center">
                        <input
                            type="date"
                            value={dateFrom}
                            onChange={e => handleDateFromChange(e.target.value)}
                            className="flex-1 px-3 py-1.5 text-xs rounded-xl border border-gray-200 bg-white text-gray-700 outline-none focus:border-[hsl(234,60%,50%)] transition-colors"
                        />
                        <span className="text-xs text-gray-400 shrink-0">—</span>
                        <input
                            type="date"
                            value={dateTo}
                            onChange={e => handleDateToChange(e.target.value)}
                            className="flex-1 px-3 py-1.5 text-xs rounded-xl border border-gray-200 bg-white text-gray-700 outline-none focus:border-[hsl(234,60%,50%)] transition-colors"
                        />
                        {hasActiveFilters && (
                            <button
                                onClick={handleClearFilters}
                                className="shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                                title="Pulisci filtri"
                            >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                                    <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
                                </svg>
                            </button>
                        )}
                    </div>
                </div>

                {/* Lista */}
                <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                    {loading && orders.length === 0 ? (
                        <div className="h-full flex items-center justify-center">
                            <div className="flex flex-col items-center gap-3">
                                <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                                <p className="text-xs text-gray-400 font-medium">Caricamento storico...</p>
                            </div>
                        </div>
                    ) : orders.length === 0 ? (
                        <EmptyState icon="list" message={hasActiveFilters ? "Nessun ordine trovato" : "Nessun ordine recente"} />
                    ) : (
                        <>
                            {orders.map((order, idx) => (
                                <OrderCard
                                    key={`${order.order_id}-${idx}`}
                                    order={order}
                                    index={idx % 15}
                                    onClick={() => setSelectedOrderId(order.order_id)}
                                />
                            ))}
                        </>
                    )}
                </div>

                {orders.length > 0 && (
                    <div className="shrink-0 px-4 py-3 border-t border-gray-100 flex items-center justify-between">
                        <span className="text-[11px] text-gray-400 font-medium">
                            Pagina {page + 1}
                        </span>
                        <div className="flex items-center gap-1">
                            <button
                                onClick={() => goToPage(0)}
                                disabled={page === 0}
                                className="px-2 py-1 rounded-lg text-[11px] font-bold text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            >
                                &laquo;
                            </button>
                            <button
                                onClick={() => goToPage(page - 1)}
                                disabled={page === 0}
                                className="px-2.5 py-1 rounded-lg text-[11px] font-bold text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            >
                                &lsaquo; Prec
                            </button>
                            <button
                                onClick={() => goToPage(page + 1)}
                                disabled={!hasMore}
                                className="px-2.5 py-1 rounded-lg text-[11px] font-bold text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            >
                                Succ &rsaquo;
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}
