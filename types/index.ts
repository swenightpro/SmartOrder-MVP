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

export interface ProductLink {
    name: string;
    cod_art: string;
}

export interface ProductLinkWithCode {
    cod_art: string;
    name: string;
    des_um?: string;       // unit of sale (e.g. "Cassa")
    pezzi_conf?: number;   // units per package
    des_tipo_um?: string;  // inner unit type (e.g. "Bottiglie")
    quantity?: number;     // preset quantity (used for image proposals)
}

export interface Message {
    id: string;
    dbId?: number;
    role: 'user' | 'assistant';
    content: string;
    suggestedProducts?: SuggestedProduct[];
    productLinks?: ProductLink[];
    productButtons?: ProductLinkWithCode[];
    feedback?: { is_positive: boolean } | null;
    intent?: 'ORDER' | 'CLARIFICATION' | 'ADVICE' | 'CONFIRMATION' | 'CART_EDIT' | 'REORDER';
    productConfidences?: Record<string, number>;
    imageData?: string;
    ocrText?: string;
    disambiguationCandidates?: DisambiguationCandidate[];
}

export interface DisambiguationCandidate {
    cod_art: string;
    name: string;
    des_um?: string;
    pezzi_conf?: number;
    des_tipo_um?: string;
    quantity?: number;
}

// --- Image / OCR ---

export interface OCRProduct {
    name: string;
    code: string;
    quantity: number;
    confidence: number;
}

export interface ImageMessage {
    id: string;
    dbId?: number;
    role: 'user';
    content: string; // empty for image messages
    imageData?: string; // base64 data URL
    ocrText?: string;   // only for operator view
}

export interface ImageUploadResponse {
    success: boolean;
    user_message_id?: number;
    ai_message_id?: number;
    response?: string;
    intent?: 'ORDER' | 'CLARIFICATION' | 'ADVICE' | 'CONFIRMATION' | 'CART_EDIT' | 'REORDER';
    product_codes_with_names?: Array<{
        cod_art: string;
        name: string;
        quantity?: number;
        des_um?: string;
    }>;
    product_confidences?: Record<string, number>;
    product_items?: Array<{ cod_art: string; quantity: number }>;
    cart_edits?: Array<{ cart_item_id: number; action: string; new_quantity?: number }>;
    edit_confirmed?: boolean;
    order_confirmed?: boolean;
    cart_synced?: boolean;
    cart_added_codes?: string[];
    cart_failed_codes?: string[];
    error?: string;
}

export interface CartEditItem {
    cart_item_id: number;
    action: 'remove' | 'set_quantity';
    new_quantity?: number;
}

// --- Ordini ---

export interface OrderFilters {
    search?: string;
    sortBy?: string;
    sortDir?: 'asc' | 'desc';
    dateFrom?: string;
    dateTo?: string;
    searchCodCli?: string;
    searchRagSoc?: string;
    limit?: number;
    offset?: number;
    esportato?: boolean;
}

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
    cod_cli?: number;
    rag_soc?: string | null;
    esportato?: boolean;
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
    metadata: Record<string, unknown> | string | null;
    created_at: string;
    feedbacks?: FeedbackReadOnly[];
}

export interface FeedbackReadOnly {
    id: number;
    user_id: number;
    is_positive: boolean;
    reason_category?: string | null;
    comment?: string | null;
    created_at?: string | null;
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
    export_folder?: string | null;
    created_at: string | null;
    updated_at: string | null;
}

// --- Ticket ---

export interface Ticket {
    id: number;
    session_id: number;
    cod_cli: number;
    rag_soc: string;
    status: 'aperto' | 'in_lavorazione' | 'chiuso';
    locked_by?: number | null;
    operator_name?: string | null;
    created_at: string;
    updated_at: string;
    last_message_at?: string | null;
    waiting_minutes?: number;
}

export interface OperatorTicketDetail extends Ticket {
    messages: ChatMessage[];
    cart_items: CartItem[];
}

export interface OperatorTrendPoint {
    day: string;
    value: number;
}

export interface OperatorTicketStatusSlice {
    status: 'aperto' | 'in_lavorazione' | 'chiuso';
    label: string;
    count: number;
}

export interface OperatorTopClientMetric {
    cod_cli: number;
    rag_soc: string;
    orders: number;
}

export interface OperatorPlatformOverview {
    generated_at: string | null;
    range_days: number;
    kpis: {
        total_orders: number;
        total_tickets: number;
        open_tickets: number;
        active_sessions: number;
        total_messages: number;
    };
    orders_daily: OperatorTrendPoint[];
    tickets_daily: OperatorTrendPoint[];
    ticket_status: OperatorTicketStatusSlice[];
    top_clients: OperatorTopClientMetric[];
}

// --- Health ---

export interface HealthStatus {
    status: 'healthy' | 'degraded';
    ai_service: boolean;
}
