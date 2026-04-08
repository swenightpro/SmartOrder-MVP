/* eslint-disable react-hooks/immutability, react-hooks/refs */
import { useEffect, useRef, useCallback, useState } from 'react';

export type SSEEventType = 'message' | 'ticket_update' | 'cart_update' | 'connected' | 'image_message';

export interface SSEEvent {
    type: string;
    data: unknown;
}

export interface UseSSEOptions {
    /** Called when connected */
    onConnected?: () => void;
    /** Called on any SSE event */
    onEvent?: (event: SSEEvent) => void;
    /** Called on non-recoverable error */
    onError?: (error: Event) => void;
    /** Base reconnection delay in ms (default 1000) */
    baseDelay?: number;
    /** Max reconnect attempts (default 5) */
    maxRetries?: number;
}

export interface UseSSEReturn {
    connected: boolean;
    reconnectAttempts: number;
}

/**
 * Fetch a short-lived SSE token from the backend (via the Next.js proxy
 * so the HTTPOnly cookie is forwarded automatically).
 */
async function fetchSSEToken(): Promise<string | null> {
    try {
        const res = await fetch('/api/auth/sse-token', { credentials: 'include' });
        if (!res.ok) return null;
        const json = await res.json();
        return json.token ?? null;
    } catch {
        return null;
    }
}

/**
 * Build the full EventSource URL.
 * In production (NEXT_PUBLIC_API_URL set) → connect directly to FastAPI with ?token=
 * In development (no NEXT_PUBLIC_API_URL)  → connect via Next.js proxy /api/...
 */
function buildSSEUrl(path: string, token: string | null): string {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL;
    if (backendUrl && token) {
        // Direct connection to FastAPI — bypasses Next.js proxy buffering
        return `${backendUrl.replace(/\/+$/, '')}${path}?token=${encodeURIComponent(token)}`;
    }
    // Dev fallback: go through Next.js proxy (rewrites handle cookie forwarding)
    return `/api${path}`;
}

export function useSSE(url: string | null, options: UseSSEOptions = {}): UseSSEReturn {
    const {
        onConnected,
        onEvent,
        onError,
        baseDelay = 1000,
        maxRetries = 5,
    } = options;

    const [connected, setConnected] = useState(false);
    const [reconnectAttempts, setReconnectAttempts] = useState(0);

    const esRef = useRef<EventSource | null>(null);
    const retriesRef = useRef(0);
    const mountedRef = useRef(true);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const tokenRef = useRef<string | null>(null);

    // Store callbacks in refs to avoid reconnecting when they change
    const onConnectedRef = useRef(onConnected);
    const onEventRef = useRef(onEvent);
    const onErrorRef = useRef(onError);
    onConnectedRef.current = onConnected;
    onEventRef.current = onEvent;
    onErrorRef.current = onError;

    // Use a ref to break the self-reference cycle in connect's setTimeout
    const connectRef = useRef<(() => void) | null>(null);

    const connect = useCallback(async () => {
        if (!mountedRef.current || url === null) return;

        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }

        // Fetch token if we don't have one yet (or on reconnect)
        if (!tokenRef.current) {
            tokenRef.current = await fetchSSEToken();
        }

        const fullUrl = buildSSEUrl(url, tokenRef.current);

        const es = new EventSource(fullUrl);
        esRef.current = es;

        es.onmessage = (event) => {
            if (!mountedRef.current) return;
            try {
                const parsed = JSON.parse(event.data) as { event: string; data: unknown };
                if (parsed.event === 'connected') {
                    setConnected(true);
                    retriesRef.current = 0;
                    setReconnectAttempts(0);
                    onConnectedRef.current?.();
                }
                onEventRef.current?.({ type: parsed.event, data: parsed.data });
            } catch {
                // ignore keepalive comments
            }
        };

        es.onerror = () => {
            if (!mountedRef.current) return;
            setConnected(false);

            if (retriesRef.current < maxRetries) {
                const delay = baseDelay * Math.pow(2, retriesRef.current);
                retriesRef.current += 1;
                setReconnectAttempts(retriesRef.current);
                // Invalidate token on reconnect (might have expired)
                tokenRef.current = null;
                reconnectTimeoutRef.current = setTimeout(() => {
                    connectRef.current?.();
                }, delay);
            } else {
                onErrorRef.current?.(new Event('max_retries'));
            }
        };
    }, [url, baseDelay, maxRetries]);

    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    useEffect(() => {
        mountedRef.current = true;
        if (url !== null) {
            connect();
        }
        return () => {
            mountedRef.current = false;
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (esRef.current) {
                esRef.current.close();
                esRef.current = null;
            }
            setConnected(false);
        };
    }, [connect]);

    return { connected, reconnectAttempts };
}
