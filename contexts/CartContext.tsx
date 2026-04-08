"use client";

import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react';
import type { CartItem } from '@/types';
import { cartService } from '@/services';
import { useSession } from './SessionContext';

interface CartContextValue {
    cart: CartItem[];
    refreshCart: () => Promise<void>;
    addItem: (codArt: string, qta: number, extra?: { source?: string; ai_confidence?: number | null; related_message_id?: number | null }) => Promise<Response>;
    removeItem: (id: number) => Promise<void>;
    updateQty: (id: number, qta: number, source?: string) => void;
    clearCart: () => void;
    hasPendingUpdates: () => boolean;
}

const CartContext = createContext<CartContextValue | null>(null);

export function useCart(): CartContextValue {
    const ctx = useContext(CartContext);
    if (!ctx) throw new Error('useCart deve essere usato dentro un <CartProvider>');
    return ctx;
}

interface CartProviderProps {
    children: ReactNode;
    codCli: number | undefined;
}

export function CartProvider({ children, codCli }: CartProviderProps) {
    const { sessionId } = useSession();
    const [cart, setCart] = useState<CartItem[]>([]);
    // Debounce map: itemId → { targetQty, timer }
    const pendingUpdates = useRef<Map<number, { targetQty: number; timer: ReturnType<typeof setTimeout> }>>(new Map());

    const refreshCart = useCallback(async () => {
        if (!codCli) { setCart([]); return; }
        try {
            const data = await cartService.getCart(sessionId);
            setCart(data);
        } catch (e) { console.error('Errore fetch carrello', e); }
    }, [codCli, sessionId]);

    const addItem = useCallback(async (codArt: string, qta: number, extra?: { source?: string; ai_confidence?: number | null; related_message_id?: number | null }) => {
        const res = await cartService.addItem(codArt, qta, { ...extra, sessionId });
        // Dopo l'add facciamo refresh perché non abbiamo i dati completi
        // del prodotto (des_art, linea, famiglia, etc.) per creare un item locale
        await refreshCart();
        return res;
    }, [refreshCart, sessionId]);

    // ---------- Optimistic: removeItem ----------
    const removeItem = useCallback(async (id: number) => {
        // Cancella eventuali update pendenti per questo articolo
        const pending = pendingUpdates.current.get(id);
        if (pending) { clearTimeout(pending.timer); pendingUpdates.current.delete(id); }
        // Rimuovi subito dalla UI (snapshot via functional update per evitare stale closure)
        setCart(prev => prev.filter(item => item.id !== id));
        try {
            const res = await cartService.removeItem(id, sessionId);
            if (!res.ok) {
                console.error('Errore server removeItem, risincronizzazione dal server');
                await refreshCart();
            }
        } catch (e) {
            console.error('Errore removeItem', e);
            await refreshCart();
        }
    }, [sessionId, refreshCart]);

    // ---------- Debounced optimistic: updateQty ----------
    // UI aggiornata immediatamente; API call ritardata di 600ms per
    // accorpare click rapidi sullo stesso articolo in una sola chiamata.
    const updateQty = useCallback((id: number, qta: number, source = 'customer') => {
        // Se la quantità va a 0 o meno, tratta come rimozione
        if (qta < 1) {
            // Cancella eventuale pending per questo id
            const existing = pendingUpdates.current.get(id);
            if (existing) { clearTimeout(existing.timer); pendingUpdates.current.delete(id); }
            return removeItem(id);
        }
        // Aggiorna subito la UI (optimistic)
        setCart(prev => prev.map(item =>
            item.id === id ? { ...item, qta, last_updated_by: source } : item
        ));
        // Cancella il timer precedente per lo stesso articolo
        const existing = pendingUpdates.current.get(id);
        if (existing) clearTimeout(existing.timer);
        // Schedula la chiamata API dopo 600ms di silenzio
        const timer = setTimeout(async () => {
            pendingUpdates.current.delete(id);
            try {
                const res = await cartService.updateQty(id, qta, source, sessionId);
                if (!res.ok) {
                    console.error('Errore server updateQty, risincronizzazione dal server');
                    await refreshCart();
                } else {
                    // Risincronizza solo se non ci sono altri update in attesa
                    // (es. aggiornamenti dell'operatore arrivati via SSE nel frattempo)
                    if (pendingUpdates.current.size === 0) {
                        await refreshCart();
                    }
                }
            } catch (e) {
                console.error('Errore updateQty', e);
                await refreshCart();
            }
        }, 600);
        pendingUpdates.current.set(id, { targetQty: qta, timer });
    }, [removeItem, sessionId, refreshCart]);

    const clearCart = useCallback(() => setCart([]), []);

    const hasPendingUpdates = useCallback(() => pendingUpdates.current.size > 0, []);

    return (
        <CartContext.Provider value={{ cart, refreshCart, addItem, removeItem, updateQty, clearCart, hasPendingUpdates }}>
            {children}
        </CartContext.Provider>
    );
}
