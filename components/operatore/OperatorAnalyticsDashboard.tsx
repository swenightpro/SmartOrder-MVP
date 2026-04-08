"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ticketService } from '@/services';
import type {
    OperatorPlatformOverview,
    OperatorTicketStatusSlice,
    OperatorTopClientMetric,
    OperatorTrendPoint,
} from '@/types';

const RANGE_OPTIONS = [7, 14, 30] as const;

function formatShortDate(day: string): string {
    try {
        const d = new Date(`${day}T00:00:00Z`);
        return d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short' }).replace('.', '');
    } catch {
        return day;
    }
}

function formatCompact(value: number): string {
    return new Intl.NumberFormat('it-IT', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function TrendChart({
    title,
    subtitle,
    points,
    stroke,
    fill,
}: {
    title: string;
    subtitle: string;
    points: OperatorTrendPoint[];
    stroke: string;
    fill: string;
}) {
    const chartWidth = 640;
    const chartHeight = 220;
    const padX = 24;
    const padY = 18;
    const safePoints = points.length > 0 ? points : [{ day: '', value: 0 }];
    const maxValue = Math.max(...safePoints.map(p => p.value), 1);
    const innerWidth = chartWidth - padX * 2;
    const innerHeight = chartHeight - padY * 2;
    const xStep = safePoints.length > 1 ? innerWidth / (safePoints.length - 1) : 0;

    const coords = safePoints.map((point, index) => {
        const x = padX + xStep * index;
        const y = chartHeight - padY - (point.value / maxValue) * innerHeight;
        return { x, y, value: point.value, day: point.day };
    });

    const linePath = coords
        .map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(2)} ${c.y.toFixed(2)}`)
        .join(' ');

    const areaPath = `${linePath} L ${coords[coords.length - 1].x.toFixed(2)} ${(chartHeight - padY).toFixed(2)} L ${coords[0].x.toFixed(2)} ${(chartHeight - padY).toFixed(2)} Z`;

    const yTicks = [0, 0.33, 0.66, 1].map(v => Math.round(v * maxValue));
    const labelStride = Math.max(1, Math.floor(coords.length / 5));

    return (
        <section className="rounded-2xl border border-gray-100 bg-white p-4 shadow-sm">
            <div className="mb-3">
                <h3 className="text-sm font-extrabold text-gray-900">{title}</h3>
                <p className="text-xs text-gray-500">{subtitle}</p>
            </div>

            <div className="w-full overflow-x-auto">
                <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="min-w-130 w-full h-52">
                    {yTicks.map((tick, i) => {
                        const y = chartHeight - padY - (tick / maxValue) * innerHeight;
                        return (
                            <g key={`${tick}-${i}`}>
                                <line x1={padX} y1={y} x2={chartWidth - padX} y2={y} stroke="#edf0f7" strokeWidth="1" />
                                <text x={4} y={y + 4} fill="#94a3b8" fontSize="10" fontWeight="700">
                                    {tick}
                                </text>
                            </g>
                        );
                    })}

                    <path d={areaPath} fill={fill} opacity="0.22" />
                    <path d={linePath} fill="none" stroke={stroke} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />

                    {coords.map((c, i) => (
                        <circle key={`dot-${i}`} cx={c.x} cy={c.y} r="3.2" fill={stroke} />
                    ))}

                    {coords.map((c, i) => {
                        if (i % labelStride !== 0 && i !== coords.length - 1) return null;
                        return (
                            <text key={`lbl-${i}`} x={c.x} y={chartHeight - 2} textAnchor="middle" fill="#64748b" fontSize="10" fontWeight="700">
                                {formatShortDate(c.day)}
                            </text>
                        );
                    })}
                </svg>
            </div>
        </section>
    );
}

function TicketStatusBreakdown({ rows }: { rows: OperatorTicketStatusSlice[] }) {
    const total = rows.reduce((sum, row) => sum + row.count, 0);

    const statusStyle: Record<OperatorTicketStatusSlice['status'], { color: string; soft: string }> = {
        aperto: { color: '#f59e0b', soft: '#fef3c7' },
        in_lavorazione: { color: '#2563eb', soft: '#dbeafe' },
        chiuso: { color: '#16a34a', soft: '#dcfce7' },
    };

    return (
        <section className="rounded-2xl border border-gray-100 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-extrabold text-gray-900">Distribuzione Ticket</h3>
            <p className="text-xs text-gray-500 mb-4">Snapshot generale sugli stati correnti.</p>

            <div className="space-y-3">
                {rows.map(row => {
                    const pct = total > 0 ? Math.round((row.count / total) * 100) : 0;
                    const styles = statusStyle[row.status];
                    return (
                        <div key={row.status}>
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-xs font-bold text-gray-700">{row.label}</span>
                                <span className="text-xs font-mono text-gray-500">{row.count} ({pct}%)</span>
                            </div>
                            <div className="h-2.5 rounded-full" style={{ backgroundColor: styles.soft }}>
                                <div
                                    className="h-2.5 rounded-full transition-all"
                                    style={{ width: `${pct}%`, backgroundColor: styles.color }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

function TopClientsChart({ clients }: { clients: OperatorTopClientMetric[] }) {
    const maxOrders = Math.max(...clients.map(c => c.orders), 1);

    return (
        <section className="rounded-2xl border border-gray-100 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-extrabold text-gray-900">Clienti piu attivi (ultimi 30 giorni)</h3>
            <p className="text-xs text-gray-500 mb-4">Classifica per numero ordini nel periodo.</p>

            {clients.length === 0 ? (
                <p className="text-xs text-gray-400">Nessun dato disponibile.</p>
            ) : (
                <div className="space-y-3">
                    {clients.map(client => {
                        const widthPct = Math.max(8, Math.round((client.orders / maxOrders) * 100));
                        return (
                            <div key={`${client.cod_cli}-${client.rag_soc}`}>
                                <div className="flex items-center justify-between mb-1.5">
                                    <div className="min-w-0">
                                        <p className="text-xs font-bold text-gray-800 truncate">{client.rag_soc}</p>
                                        <p className="text-[11px] font-mono text-gray-400">#{client.cod_cli}</p>
                                    </div>
                                    <span className="text-xs font-bold text-[hsl(234,60%,36%)]">{client.orders}</span>
                                </div>
                                <div className="h-2 rounded-full bg-[hsl(234,40%,93%)]">
                                    <div className="h-2 rounded-full bg-[hsl(234,70%,48%)]" style={{ width: `${widthPct}%` }} />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </section>
    );
}

export default function OperatorAnalyticsDashboard() {
    const [days, setDays] = useState<number>(14);
    const [overview, setOverview] = useState<OperatorPlatformOverview | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');

    const fetchOverview = useCallback(async (showLoader: boolean) => {
        if (showLoader) setLoading(true);
        else setRefreshing(true);

        setError('');
        try {
            const data = await ticketService.getPlatformUsageOverview(days);
            setOverview(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Errore caricamento analytics');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [days]);

    useEffect(() => {
        fetchOverview(true);
    }, [fetchOverview]);

    const generatedAt = useMemo(() => {
        if (!overview?.generated_at) return 'n/d';
        try {
            return new Date(overview.generated_at).toLocaleString('it-IT');
        } catch {
            return overview.generated_at;
        }
    }, [overview?.generated_at]);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-3 border-gray-200 border-t-[hsl(234,60%,36%)] rounded-full animate-spin" />
                    <p className="text-xs text-gray-400 font-medium">Caricamento analytics...</p>
                </div>
            </div>
        );
    }

    if (error || !overview) {
        return (
            <div className="h-full flex items-center justify-center px-6">
                <div className="max-w-sm w-full rounded-2xl border border-red-100 bg-red-50 p-4 text-center">
                    <p className="text-sm font-bold text-red-700 mb-1">Analytics non disponibili</p>
                    <p className="text-xs text-red-500">{error || 'Errore inaspettato'}</p>
                    <button
                        onClick={() => fetchOverview(true)}
                        className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-red-500 hover:bg-red-600 transition-colors"
                    >
                        Riprova
                    </button>
                </div>
            </div>
        );
    }

    const kpiCards = [
        { label: 'Ordini totali', value: overview.kpis.total_orders, tone: 'from-sky-500 to-cyan-500' },
        { label: 'Ticket totali', value: overview.kpis.total_tickets, tone: 'from-indigo-500 to-blue-600' },
        { label: 'Ticket aperti', value: overview.kpis.open_tickets, tone: 'from-amber-500 to-orange-500' },
        { label: 'Sessioni attive', value: overview.kpis.active_sessions, tone: 'from-emerald-500 to-teal-500' },
        { label: 'Messaggi totali', value: overview.kpis.total_messages, tone: 'from-fuchsia-500 to-pink-500' },
    ];

    return (
        <div className="h-full flex flex-col overflow-hidden">
            <div className="shrink-0 px-5 py-4 border-b border-gray-100 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <div className="flex items-center gap-2.5">
                        <h2 className="text-base font-extrabold text-gray-900">Analytics Piattaforma</h2>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Ultimo aggiornamento: {generatedAt}</p>
                </div>

                <div className="flex items-center gap-2">
                    {RANGE_OPTIONS.map(option => (
                        <button
                            key={option}
                            onClick={() => setDays(option)}
                            className={`px-2.5 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                                days === option
                                    ? 'bg-[hsl(234,60%,36%)] text-white'
                                    : 'bg-[hsl(234,40%,95%)] text-[hsl(234,60%,36%)] hover:bg-[hsl(234,40%,91%)]'
                            }`}
                        >
                            {option}g
                        </button>
                    ))}
                    <button
                        onClick={() => fetchOverview(false)}
                        disabled={refreshing}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-[hsl(234,60%,36%)] bg-[hsl(234,40%,95%)] hover:bg-[hsl(234,40%,91%)] disabled:opacity-50 transition-colors"
                    >
                        <svg className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                            <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                        </svg>
                        Aggiorna
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar bg-[hsl(230,35%,98%)]">
                <div className="p-4 md:p-5 space-y-4">
                    <section className="grid grid-cols-2 xl:grid-cols-5 gap-3">
                        {kpiCards.map(card => (
                            <article
                                key={card.label}
                                className={`rounded-2xl bg-linear-to-br ${card.tone} text-white p-3.5 shadow-md shadow-slate-200/70`}
                            >
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-white/85">{card.label}</p>
                                <p className="text-2xl font-extrabold mt-1">{formatCompact(card.value)}</p>
                            </article>
                        ))}
                    </section>

                    <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
                        <TrendChart
                            title="Trend Ordini"
                            subtitle={`Ultimi ${overview.range_days} giorni`}
                            points={overview.orders_daily}
                            stroke="#2563eb"
                            fill="#93c5fd"
                        />
                        <TrendChart
                            title="Trend Ticket"
                            subtitle={`Ultimi ${overview.range_days} giorni`}
                            points={overview.tickets_daily}
                            stroke="#0ea5e9"
                            fill="#67e8f9"
                        />
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                        <TicketStatusBreakdown rows={overview.ticket_status} />
                        <TopClientsChart clients={overview.top_clients} />
                    </div>
                </div>
            </div>
        </div>
    );
}
