"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type { CartItem } from '@/types';
import { cartService } from '@/services';

interface CartContextValue {
    cart: CartItem[];
    refreshCart: () => Promise<void>;
    addItem: (codArt: string, qta: number, extra?: { source?: string; ai_confidence?: number | null; related_message_id?: number | null }) => Promise<Response>;
    removeItem: (id: number) => Promise<void>;
    updateQty: (id: number, qta: number, source?: string) => Promise<void>;
    clearCart: () => void;
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
    sessionId?: number | null;
}

export function CartProvider({ children, codCli, sessionId }: CartProviderProps) {
    const [cart, setCart] = useState<CartItem[]>([]);

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
        // Salva snapshot per rollback
        const snapshot = cart;
        // Rimuovi subito dalla UI
        setCart(prev => prev.filter(item => item.id !== id));
        // Sincronizza col server in background
        try {
            const res = await cartService.removeItem(id, sessionId);
            if (!res.ok) {
                console.error('Errore server removeItem, rollback');
                setCart(snapshot);
            }
        } catch (e) {
            console.error('Errore removeItem, rollback', e);
            setCart(snapshot);
        }
    }, [cart, sessionId]);

    // ---------- Optimistic: updateQty ----------
    const updateQty = useCallback(async (id: number, qta: number, source = 'customer') => {
        // Se la quantità va a 0 o meno, tratta come rimozione
        if (qta < 1) {
            return removeItem(id);
        }
        // Salva snapshot per rollback
        const snapshot = cart;
        // Aggiorna subito la UI
        setCart(prev => prev.map(item =>
            item.id === id ? { ...item, qta, last_updated_by: source } : item
        ));
        // Sincronizza col server in background
        try {
            const res = await cartService.updateQty(id, qta, source, sessionId);
            if (!res.ok) {
                console.error('Errore server updateQty, rollback');
                setCart(snapshot);
            }
        } catch (e) {
            console.error('Errore updateQty, rollback', e);
            setCart(snapshot);
        }
    }, [cart, removeItem, sessionId]);

    const clearCart = useCallback(() => setCart([]), []);

    return (
        <CartContext.Provider value={{ cart, refreshCart, addItem, removeItem, updateQty, clearCart }}>
            {children}
        </CartContext.Provider>
    );
}
