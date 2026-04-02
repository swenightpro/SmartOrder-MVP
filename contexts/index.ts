// ============================================================
// contexts/index.ts — Barrel export per i Context provider
//
// Centralizza gli export dei provider e hook di contesto,
// permettendo import più puliti: import { useCart, useSession } from '@/contexts'
// ============================================================

export { CartProvider, useCart } from './CartContext';
export { SessionProvider, useSession } from './SessionContext';
