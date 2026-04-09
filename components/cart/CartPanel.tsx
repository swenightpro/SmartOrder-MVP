"use client";
import { useState } from 'react';
import type { Client, Product } from '@/types';
import { orderService, ticketService } from '@/services';
import { useCart, useSession } from '@/contexts';
import ProductSearch from './ProductSearch';
import ProductCard from './ProductCard';
import CartItemRow from './CartItemRow';
import { EmptyState } from '@/components/ui';
import { useSSE } from '@/hooks';

const BLOCKING_STATUSES = ["ARTICOLO SOSPESO", "SU AUTORIZZAZIONE", "DISPONIBILE DAL", "NON DISPONIBILE"];

interface CartPanelProps {
  currentClient: Client | null;
  onClose?: () => void;
  onOrderSuccess: () => void;
  hasOpenTicket?: boolean;
  onTicketChange?: () => void;
  isMobile?: boolean;
}

export default function CartPanel({ currentClient, onClose, onOrderSuccess, hasOpenTicket = false, onTicketChange, isMobile = false }: CartPanelProps) {
  const { cart, addItem, removeItem, updateQty, refreshCart, hasPendingUpdates } = useCart();
  const { sessionId } = useSession();
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [error, setError] = useState('');
  const [blockedItems, setBlockedItems] = useState<Set<number>>(new Set());
  const [confirmingAssistenza, setConfirmingAssistenza] = useState(false);
  const [assistenzaLoading, setAssistenzaLoading] = useState(false);

  // SSE: real-time cart updates (from operator changes or ticket session)
  // Skip refresh if there are pending debounced qty updates to avoid overwriting optimistic state
  useSSE(sessionId ? `/sse/${sessionId}` : null, {
      onEvent: (event) => {
          if (event.type === 'cart_update' && !hasPendingUpdates()) {
              refreshCart();
          }
      },
  });

  // --- Cart operations (delegate to CartContext for optimistic updates) ---
  const addToCart = async (qty: number) => {
    if (!currentClient?.cod_cli) { setError("Errore: Seleziona prima un cliente."); return; }
    if (!selectedProduct) { setError("Errore: Seleziona un articolo dalla ricerca."); return; }
    const isBlocked = BLOCKING_STATUSES.some(s => selectedProduct.stato?.toUpperCase().includes(s));
    if (isBlocked) { setError(`Articolo bloccato: ${selectedProduct.stato}`); return; }
    if (qty <= 0) { setError("Inserisci una quantità valida (minimo 1)."); return; }

    setError('');
    try {
      const res = await addItem(selectedProduct.cod_art, qty, { source: 'customer' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || data.detail || "Errore durante l'aggiunta al carrello");
      }
      setSelectedProduct(null);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Errore"); }
  };

  const removeFromCart = async (id: number) => {
    await removeItem(id);
  };

  const updateCartQty = (id: number, newQty: number) => {
    updateQty(id, newQty);
  };

  // --- Send order (Facade: orderService) ---
  const handleSendFullOrder = async () => {
    if (cart.length === 0 || !currentClient) return;
    setError('');
    setBlockedItems(new Set());
    try {
      await orderService.create(currentClient.cod_cli, sessionId, cart.filter(i => i.cod_art).map(i => ({
        cod_art: i.cod_art!, qta: i.qta, source: i.source || 'customer',
        last_updated_by: i.last_updated_by || 'customer',
        ai_confidence: i.ai_confidence || null,
        related_message_id: i.related_message_id || null,
      })));
      onOrderSuccess();
      if (onClose) onClose();
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Errore invio ordine';
      const codArtMatch = errorMsg.match(/Articolo\s+(\S+)/);
      if (codArtMatch) {
        const blockedCodArt = codArtMatch[1];
        setBlockedItems(new Set(cart.filter(i => i.cod_art === blockedCodArt).map(i => i.id)));
      }
      setError(errorMsg);
    }
  };

  // --- Assistenza toggle ---
  const handleAssistenzaAction = async () => {
    if (!sessionId || assistenzaLoading) return;
    setAssistenzaLoading(true);
    try {
      if (hasOpenTicket) {
        await ticketService.closeTicketBySession(sessionId);
      } else {
        await ticketService.openTicket(sessionId);
      }
      onTicketChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore assistenza');
    } finally {
      setAssistenzaLoading(false);
      setConfirmingAssistenza(false);
    }
  };

  // --- Shared: Confirm button ---
  const ConfirmButton = () => (
    <div className="flex gap-2 flex-1">
      {onTicketChange !== undefined && (
        confirmingAssistenza ? (
          <div className="flex items-center gap-2 shrink-0 bg-gray-50 border border-gray-200 rounded-2xl px-3 h-12">
            <span className="text-xs font-semibold text-gray-600 whitespace-nowrap">
              {hasOpenTicket ? 'Chiudere l\'assistenza?' : 'Richiedere assistenza?'}
            </span>
            <button
              onClick={handleAssistenzaAction}
              disabled={assistenzaLoading}
              className="h-7 px-3 rounded-xl text-xs font-bold bg-[hsl(234,60%,36%)] text-white hover:bg-[hsl(234,60%,30%)] transition-all disabled:opacity-50"
            >
              {assistenzaLoading ? '...' : 'Sì'}
            </button>
            <button
              onClick={() => setConfirmingAssistenza(false)}
              className="h-7 px-3 rounded-xl text-xs font-bold border border-gray-200 text-gray-500 hover:bg-gray-100 transition-all"
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmingAssistenza(true)}
            className={`h-12 px-4 rounded-2xl font-bold text-sm transition-all active:scale-[0.98] flex items-center justify-center gap-2 shrink-0 ${
              hasOpenTicket
                ? 'bg-red-50 text-red-600 border-2 border-red-200 hover:bg-red-100'
                : 'bg-emerald-50 text-emerald-700 border-2 border-emerald-200 hover:bg-emerald-100'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            {hasOpenTicket ? 'Chiudi Assistenza' : 'Richiedi Assistenza'}
          </button>
        )
      )}
      <button
        onClick={handleSendFullOrder}
        disabled={cart.length === 0}
        className="flex-1 h-12 bg-[hsl(234,60%,36%)] text-white rounded-2xl font-bold text-sm shadow-lg hover:bg-[hsl(234,60%,30%)] disabled:bg-gray-200 disabled:text-gray-400 disabled:shadow-none transition-all active:scale-[0.98] flex justify-center items-center gap-2"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
        CONFERMA E INVIA
      </button>
    </div>
  );

  // --- Shared: Cart list ---
  const CartList = ({ className = '' }: { className?: string }) => (
    <div className={className}>
      {cart.length === 0 ? (
        <EmptyState icon="cart" message={isMobile ? 'Carrello vuoto' : 'Nessun articolo'} />
      ) : (
        <div className={isMobile ? 'space-y-2' : 'space-y-2.5 pb-2'}>
          {cart.map(item => (
            <CartItemRow
              key={item.id}
              item={item}
              isBlocked={blockedItems.has(item.id)}
              onRemove={removeFromCart}
              onUpdateQty={updateCartQty}
            />
          ))}
        </div>
      )}
    </div>
  );

  // === MOBILE LAYOUT ===
  if (isMobile) {
    return (
      <div className="h-full flex flex-col overflow-hidden">
        <div className="shrink-0 p-3 border-b border-gray-100 relative z-20">
          {!selectedProduct ? (
            <ProductSearch onSelect={(p) => { setSelectedProduct(p); setError(''); }} compact />
          ) : (
            <ProductCard product={selectedProduct} onAdd={addToCart} onDeselect={() => { setSelectedProduct(null); setError(''); }} error={error} />
          )}
          {error && !selectedProduct && (
            <div className="mt-2 p-2.5 bg-red-50 text-red-600 rounded-xl text-xs font-bold border border-red-100 animate-scale-in">⚠️ {error}</div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Carrello</span>
            <span className="text-[10px] bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] px-2 py-0.5 rounded-full font-bold">{cart.length}</span>
          </div>
          <CartList />
        </div>
        <div className="shrink-0 p-3 border-t border-gray-100">
          <ConfirmButton />
        </div>
      </div>
    );
  }

  // === DESKTOP LAYOUT ===
  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex-1 flex flex-col pt-4 px-4 pb-2 overflow-hidden">
        <div className="space-y-3 mb-4 shrink-0 relative z-20">
          {!selectedProduct && (
            <ProductSearch onSelect={(p) => { setSelectedProduct(p); setError(''); }} />
          )}
          {selectedProduct && (
            <ProductCard product={selectedProduct} onAdd={addToCart} onDeselect={() => { setSelectedProduct(null); setError(''); }} error={error} />
          )}
        </div>
        <div className="flex-1 overflow-y-auto pr-2 space-y-2.5 custom-scrollbar -mr-2">
          <div className="flex items-center justify-between mb-2">
            <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Carrello</label>
            <span className="text-[10px] bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] px-2.5 py-0.5 rounded-full font-bold">{cart.length} Articoli</span>
          </div>
          <CartList />
        </div>
        <div className="pt-3 border-t border-gray-100 mt-2 flex items-center gap-3">
          {error && !selectedProduct && (
            <div className="p-2.5 bg-red-50 text-red-600 rounded-xl text-[11px] font-bold border border-red-100 flex-1 animate-scale-in">⚠️ {error}</div>
          )}
          <ConfirmButton />
        </div>
      </div>
    </div>
  );
}
