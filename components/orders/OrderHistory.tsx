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
    const [loadingMore, setLoadingMore] = useState(false);
    const [, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);

    // Filtri UC_29, UC_30, UC_31
    const [filters, setFilters] = useState<OrderFilters>({ sortBy: 'data_ord', sortDir: 'desc' });
    const [searchInput, setSearchInput] = useState('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');

    const observerRef = useRef<HTMLDivElement | null>(null);
    const scrollContainerRef = useRef<HTMLDivElement | null>(null);
    const searchTimerRef = useRef<ReturnType<typeof setTimeout>>(null);

    const fetchOrders = useCallback(async (pageNum: number, f: OrderFilters) => {
        try {
            if (pageNum === 0) setLoading(true);
            else setLoadingMore(true);

            const data = await orderService.list(Number(cod_cli), pageNum, f);
            const noFilters = !f.search && !f.dateFrom && !f.dateTo;

            // Se il backend ci restituisce meno del limite, significa che siamo arrivati alla fine.
            // Limite senza filtri = 50, con filtri = 15.
            const limit = noFilters ? 50 : 15;
            if (data.length < limit) setHasMore(false);

            setOrders(prev => pageNum === 0 ? data : [...prev, ...data]);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }, [cod_cli]);

    // Apply filters and reset
    const applyFilters = useCallback((f: OrderFilters) => {
        setOrders([]);
        setPage(0);
        setHasMore(true);
        fetchOrders(0, f);
    }, [fetchOrders]);

    // Debounced search
    const handleSearchChange = (val: string) => {
        setSearchInput(val);
        if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
        searchTimerRef.current = setTimeout(() => {
            applyFilters({ ...filters, search: val, dateFrom, dateTo });
        }, 400);
    };

    const handleDateFromChange = (val: string) => {
        setDateFrom(val);
        applyFilters({ ...filters, search: searchInput, dateFrom: val, dateTo });
    };

    const handleDateToChange = (val: string) => {
        setDateTo(val);
        applyFilters({ ...filters, search: searchInput, dateFrom, dateTo: val });
    };

    const handleClearFilters = () => {
        setSearchInput('');
        setDateFrom('');
        setDateTo('');
        setFilters({ sortBy: 'data_ord', sortDir: 'desc' });
        applyFilters({ sortBy: 'data_ord', sortDir: 'desc' });
    };

    const hasActiveFilters = searchInput || dateFrom || dateTo;

    useEffect(() => {
        if (!cod_cli) return;
        fetchOrders(0, filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [cod_cli]);

    useEffect(() => {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && hasMore && !loading && !loadingMore) {
                setPage(p => {
                    const nextPage = p + 1;
                    fetchOrders(nextPage, filters);
                    return nextPage;
                });
            }
        }, { threshold: 0.1, root: scrollContainerRef.current });

        if (observerRef.current) observer.observe(observerRef.current);
        return () => observer.disconnect();
    }, [hasMore, loading, loadingMore, filters, fetchOrders]);

    if (loading) return (
        <div className="h-full flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                <p className="text-xs text-gray-400 font-medium">Caricamento storico...</p>
            </div>
        </div>
    );

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
                <div ref={scrollContainerRef} className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                    {orders.length === 0 ? (
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

                            {/* Elemento Sentinella per Infinite Scroll */}
                            {hasMore && (
                                <div ref={observerRef} className="py-4 flex justify-center">
                                    {loadingMore && (
                                        <div className="w-6 h-6 border-2 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                                    )}
                                </div>
                            )}

                            {!hasMore && orders.length > 0 && (
                                <p className="py-4 text-center text-[11px] text-gray-400">Hai raggiunto la fine dello storico.</p>
                            )}
                        </>
                    )}
                </div>
            </div>
        </>
    );
}
