"use client";
import { useState, useEffect, useCallback, useRef } from 'react';
import type { OrderSummary, OrderFilters } from '@/types';
import { orderService } from '@/services';
import OrderDetailModal from '@/components/orders/OrderDetailModal';

const PAGE_SIZE = 50;
type SortCol = 'data_ord' | 'id' | 'cod_cli' | 'rag_soc' | 'item_count';

function formatDate(iso: string): string {
    try {
        const d = new Date(iso);
        const day = String(d.getUTCDate()).padStart(2, '0');
        const months = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
        const month = months[d.getUTCMonth()];
        const year = d.getUTCFullYear();
        return `${day} ${month} ${year}`;
    } catch { return '—'; }
}

function SortHeader({ col, label, sortable, currentSort, currentDir, onSort }: {
    col: SortCol; label: string; sortable?: boolean;
    currentSort: SortCol; currentDir: 'asc' | 'desc';
    onSort: (c: SortCol) => void;
}) {
    const active = currentSort === col;
    return (
        <th
            className={`px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider ${sortable ? 'cursor-pointer select-none hover:text-[hsl(234,60%,50%)]' : 'text-gray-400'} transition-colors`}
            onClick={sortable ? () => onSort(col) : undefined}
        >
            <span className="flex items-center">
                {label}
                {sortable && (
                    <span className="flex flex-col ml-1 -space-y-0.5">
                        <svg className={`w-2.5 h-2.5 ${active && currentDir === 'asc' ? 'text-[hsl(234,60%,50%)] opacity-100' : 'opacity-25'}`} viewBox="0 0 10 10" fill="currentColor">
                            <path d="M5 2L9 7H1L5 2Z" />
                        </svg>
                        <svg className={`w-2.5 h-2.5 ${active && currentDir === 'desc' ? 'text-[hsl(234,60%,50%)] opacity-100' : 'opacity-25'}`} viewBox="0 0 10 10" fill="currentColor">
                            <path d="M5 8L1 3H9L5 8Z" />
                        </svg>
                    </span>
                )}
            </span>
        </th>
    );
}

export default function OperatorOrderHistory() {
    const [orders, setOrders] = useState<OrderSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [selectedOrder, setSelectedOrder] = useState<{ id: number; cod_cli: number } | null>(null);

    // Filtri UC_29, UC_30, UC_31
    const [search, setSearch] = useState('');
    const [searchCodCli, setSearchCodCli] = useState('');
    const [searchRagSoc, setSearchRagSoc] = useState('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [sortBy, setSortBy] = useState<SortCol>('data_ord');
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

    const searchTimerRef = useRef<ReturnType<typeof setTimeout>>(null);

    const currentFilters = (): OrderFilters => ({
        search, sortBy, sortDir, dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined, searchCodCli, searchRagSoc,
        limit: PAGE_SIZE,
    });

    const fetchOrders = useCallback(async (pageNum: number, f: OrderFilters) => {
        try {
            setLoading(true);
            const offset = pageNum * PAGE_SIZE;
            const data = await orderService.listAll({ ...f, limit: PAGE_SIZE, offset });
            setOrders(data);
            setHasMore(data.length >= PAGE_SIZE);
        } catch {
            setOrders([]);
        } finally {
            setLoading(false);
        }
    }, []);

    const applyFilters = useCallback((f: OrderFilters) => {
        setOrders([]);
        setPage(0);
        setHasMore(true);
        fetchOrders(0, f);
    }, [fetchOrders]);

    const handleSearchChange = (setter: (v: string) => void, field: keyof OrderFilters) => (val: string) => {
        setter(val);
        if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
        searchTimerRef.current = setTimeout(() => {
            const f = currentFilters();
            applyFilters({ ...f, [field]: val });
        }, 400);
    };

    const handleSort = (col: SortCol) => {
        const newDir = sortBy === col && sortDir === 'desc' ? 'asc' : 'desc';
        setSortBy(col);
        setSortDir(newDir);
        applyFilters({ ...currentFilters(), sortBy: col, sortDir: newDir });
    };

    const handleDateChange = (setter: (v: string) => void, field: 'dateFrom' | 'dateTo') => (val: string) => {
        setter(val);
        const f = currentFilters();
        applyFilters({ ...f, [field]: val });
    };

    const handleClearFilters = () => {
        setSearch(''); setSearchCodCli(''); setSearchRagSoc('');
        setDateFrom(''); setDateTo('');
        setSortBy('data_ord'); setSortDir('desc');
        applyFilters({ sortBy: 'data_ord', sortDir: 'desc' });
    };

    const hasActiveFilters = search || searchCodCli || searchRagSoc || dateFrom || dateTo;

    useEffect(() => {
        fetchOrders(0, currentFilters());
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const goToPage = (p: number) => {
        if (p < 0 || p === page) return;
        setPage(p);
        fetchOrders(p, currentFilters());
    };

    return (
        <>
            {selectedOrder && (
                <OrderDetailModal
                    orderId={selectedOrder.id}
                    codCli={selectedOrder.cod_cli}
                    isAdmin={true}
                    onClose={() => setSelectedOrder(null)}
                />
            )}

            <div className="h-full flex flex-col overflow-hidden">
                {/* Header + filtri */}
                <div className="shrink-0 px-4 pt-3 pb-2 space-y-2 border-b border-gray-100">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <h2 className="text-sm font-extrabold text-gray-900">Storico Ordini</h2>
                        </div>
                        <button
                            onClick={() => fetchOrders(0, currentFilters())}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold text-[hsl(234,60%,36%)] bg-[hsl(234,60%,95%)] hover:bg-[hsl(234,60%,90%)] transition-colors"
                        >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                                <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                            </svg>
                            Aggiorna
                        </button>
                    </div>

                    {/* Riga ricerca ID */}
                    <div className="flex gap-2">
                        <div className="relative flex-1">
                            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                                <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                            </svg>
                            <input
                                type="text"
                                value={search}
                                onChange={e => handleSearchChange(setSearch, 'search')(e.target.value)}
                                placeholder="ID Ordine..."
                                className="w-full pl-8 pr-3 py-1.5 text-[11px] rounded-lg border border-gray-200 bg-white text-gray-700 placeholder-gray-400 outline-none focus:border-[hsl(234,60%,50%)] transition-colors"
                            />
                        </div>
                        <div className="relative flex-1">
                            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
                            </svg>
                            <input
                                type="text"
                                value={searchCodCli}
                                onChange={e => handleSearchChange(setSearchCodCli, 'searchCodCli')(e.target.value)}
                                placeholder="Cod. Cliente..."
                                className="w-full pl-8 pr-3 py-1.5 text-[11px] rounded-lg border border-gray-200 bg-white text-gray-700 placeholder-gray-400 outline-none focus:border-[hsl(234,60%,50%)] transition-colors"
                            />
                        </div>
                        <div className="relative flex-1">
                            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
                            </svg>
                            <input
                                type="text"
                                value={searchRagSoc}
                                onChange={e => handleSearchChange(setSearchRagSoc, 'searchRagSoc')(e.target.value)}
                                placeholder="Ragione Sociale..."
                                className="w-full pl-8 pr-3 py-1.5 text-[11px] rounded-lg border border-gray-200 bg-white text-gray-700 placeholder-gray-400 outline-none focus:border-[hsl(234,60%,50%)] transition-colors"
                            />
                        </div>
                    </div>

                    {/* Riga date */}
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider shrink-0">Periodo:</span>
                        <input type="date" value={dateFrom}
                            onChange={e => handleDateChange(setDateFrom, 'dateFrom')(e.target.value)}
                            className="flex-1 px-2 py-1.5 text-[11px] rounded-lg border border-gray-200 bg-white text-gray-700 outline-none focus:border-[hsl(234,60%,50%)] transition-colors" />
                        <span className="text-xs text-gray-400 shrink-0">—</span>
                        <input type="date" value={dateTo}
                            onChange={e => handleDateChange(setDateTo, 'dateTo')(e.target.value)}
                            className="flex-1 px-2 py-1.5 text-[11px] rounded-lg border border-gray-200 bg-white text-gray-700 outline-none focus:border-[hsl(234,60%,50%)] transition-colors" />
                        {hasActiveFilters && (
                            <button onClick={handleClearFilters}
                                className="shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                                title="Pulisci filtri">
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                                    <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
                                </svg>
                            </button>
                        )}
                    </div>
                </div>

                {/* Tabella */}
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    {loading ? (
                        <div className="h-full flex items-center justify-center">
                            <div className="flex flex-col items-center gap-3">
                                <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                                <p className="text-xs text-gray-400 font-medium">Caricamento...</p>
                            </div>
                        </div>
                    ) : orders.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-300">
                            <svg className="w-14 h-14" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
                                <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                            </svg>
                            <p className="text-sm font-medium text-gray-400">Nessun ordine trovato</p>
                        </div>
                    ) : (
                        <table className="w-full">
                            <thead className="sticky top-0 bg-white z-10 shadow-sm">
                                <tr className="border-b border-gray-100">
                                    <SortHeader col="id" label="ID" sortable currentSort={sortBy} currentDir={sortDir} onSort={handleSort} />
                                    <SortHeader col="rag_soc" label="Cliente" sortable currentSort={sortBy} currentDir={sortDir} onSort={handleSort} />
                                    <SortHeader col="data_ord" label="Data" sortable currentSort={sortBy} currentDir={sortDir} onSort={handleSort} />
                                    <SortHeader col="item_count" label="Art." sortable currentSort={sortBy} currentDir={sortDir} onSort={handleSort} />
                                    <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wider text-gray-400">Stato</th>
                                </tr>
                            </thead>
                            <tbody>
                                {orders.map((order, idx) => (
                                    <tr
                                        key={`${order.order_id}-${order.session_id ?? 'null'}-${idx}`}
                                        onClick={() => setSelectedOrder({ id: order.order_id, cod_cli: order.cod_cli ?? 0 })}
                                        className="border-b border-gray-50 hover:bg-[hsl(234,60%,97%)] cursor-pointer transition-colors"
                                    >
                                        <td className="px-4 py-3">
                                            <span className="text-sm font-mono font-bold text-[hsl(234,60%,36%)]">#{order.order_id}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex flex-col">
                                                <span className="text-xs font-medium text-gray-800 truncate max-w-[120px]">{order.rag_soc || '—'}</span>
                                                {order.cod_cli && (
                                                    <span className="text-[10px] text-gray-400 font-mono">#{order.cod_cli}</span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="text-xs text-gray-500 font-medium">{formatDate(order.data_ord)}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="inline-flex items-center justify-center min-w-[1.5rem] h-6 px-2 rounded-full text-[11px] font-bold bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] border border-[hsl(234,60%,85%)]">
                                                {order.item_count}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            {order.esportato ? (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-green-50 text-green-700 border border-green-200">
                                                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                                                        <polyline points="20 6 9 17 4 12" />
                                                    </svg>
                                                    Esportato
                                                </span>
                                            ) : (
                                                <span className="text-[10px] text-gray-300">—</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {/* Pagination */}
                {!loading && orders.length > 0 && (
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
