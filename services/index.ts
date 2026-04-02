// ============================================================
// services/index.ts — Barrel export di tutti i servizi (Facade Pattern)
//
// Centralizza gli export per consentire import puliti:
// import { authService, cartService, chatService } from '@/services'
// ============================================================

export { authService } from './authService';
export { cartService } from './cartService';
export { chatService } from './chatService';
export { orderService } from './orderService';
export { productService } from './productService';
export { sessionService } from './sessionService';
export { feedbackService } from './feedbackService';
export { healthService } from './healthService';
