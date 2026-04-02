// ============================================================
// types/index.ts — Definizioni TypeScript condivise (Single Source of Truth)
//
// Centralizza TUTTE le interfacce usate in frontend: entità
// di dominio (Client, Product, CartItem), chat (Message,
// SuggestedProduct), ordini (OrderSummary, OrderDetail),
// autenticazione (UserProfile) e health check (HealthStatus).
// Importato da componenti, services, hooks e contexts.
// ============================================================

// --- Entità di dominio ---

export interface Client {
    cod_cli: number;
    rag_soc: string;
}

export interface Product {
    cod_art: string;
    des_art: string;
    des_um: string;
    pezzi_conf: number;
    des_tipo_um: string;
    stato?: string;
    linea?: string;
    famiglia?: string;
}

export interface CartItem {
    id: number;
    cod_art: string | null;
    des_art?: string;
    qta: number;
    linea?: string;
    famiglia?: string;
    des_um?: string;
    pezzi_conf?: number;
    des_tipo_um?: string;
    source?: string;
    last_updated_by?: string;
    ai_confidence?: number | null;
    related_message_id?: number | null;
}

// --- Chat ---

export interface SuggestedProduct {
    name: string;
    cod_art?: string;
}

export interface Message {
    id: string;
    dbId?: number;
    role: 'user' | 'assistant';
    content: string;
    suggestedProducts?: SuggestedProduct[];
    feedback?: { is_positive: boolean } | null;
}

export interface CartEditItem {
    cart_item_id: number;
    action: 'remove' | 'set_quantity';
    new_quantity?: number;
}

// --- Ordini ---

export interface PreviewItem {
    cod_art: string;
    des_art: string | null;
    qta_ordinata: number;
}

export interface OrderSummary {
    order_id: number;
    data_ord: string;
    session_id: number | null;
    item_count: number;
    total_qty: number;
    message_count?: number;
    preview_items?: PreviewItem[] | null;
}

export interface OrderItem {
    id: number;
    cod_art: string;
    des_art: string;
    qta_ordinata: number;
    des_um: string;
    linea?: string;
    famiglia?: string;
    pezzi_conf?: number;
    des_tipo_um?: string;
    source?: string;
    ai_confidence?: number | null;
    related_message_id?: number | null;
}

export interface ChatMessage {
    id: number;
    sender: string;
    content: string;
    metadata: any;
    created_at: string;
}

export interface OrderDetail {
    order_id: number;
    cod_cli: number;
    data_ord: string;
    session_id: number | null;
    items: OrderItem[];
    messages: ChatMessage[];
}

// --- Auth ---

export interface UserProfile {
    email: string;
    cod_cli: number;
    rag_soc: string;
    role: string;
    created_at: string | null;
    updated_at: string | null;
}

// --- Health ---

export interface HealthStatus {
    status: 'healthy' | 'degraded';
    ai_service: boolean;
}
