// ============================================================
// components/orders/OrderHistory.tsx — Lista storico ordini cliente
//
// Carica e visualizza gli ordini passati del cliente corrente.
// Compone OrderCard per ogni ordine e OrderDetailModal per il
// dettaglio. Delega il caricamento al Facade orderService.list().
// ============================================================

"use client";
import { useState, useEffect, useRef, useCallback } from 'react';
import type { OrderSummary } from '@/types';
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

  const observerRef = useRef<HTMLDivElement | null>(null);

  const fetchOrders = useCallback(async (pageNum: number) => {
    try {
      if (pageNum === 0) setLoading(true);
      else setLoadingMore(true);

      const data = await orderService.list(Number(cod_cli), pageNum);

      // Se il backend ci restituisce meno di 15 elementi, significa che siamo arrivati alla fine
      if (data.length < 15) setHasMore(false);

      setOrders(prev => pageNum === 0 ? data : [...prev, ...data]);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [cod_cli]);

  useEffect(() => {
    if (!cod_cli) return;
    setOrders([]);
    setPage(0);
    setHasMore(true);
    fetchOrders(0);
  }, [cod_cli, fetchOrders]);

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore && !loading && !loadingMore) {
        setPage(p => {
          const nextPage = p + 1;
          fetchOrders(nextPage);
          return nextPage;
        });
      }
    }, { threshold: 0.1 });

    if (observerRef.current) observer.observe(observerRef.current);

    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, fetchOrders]);

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

      <div className="h-full overflow-y-auto pr-2 space-y-3 custom-scrollbar">
        <div className="flex items-center justify-between mb-1">
          <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Storico Ordini</label>
          <span className="text-[10px] bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] px-2.5 py-0.5 rounded-full font-bold">
            {orders.length} Ordin{orders.length === 1 ? 'e' : 'i'}
          </span>
        </div>

        {orders.length === 0 ? (
          <EmptyState icon="list" message="Nessun ordine recente" />
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
    </>
  );
}