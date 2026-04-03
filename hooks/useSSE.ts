import { useEffect, useRef, useCallback, useState } from 'react';

export type SSEEventType = 'message' | 'ticket_update' | 'cart_update' | 'connected';

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

    const connect = useCallback(() => {
        if (!mountedRef.current || url === null) return;

        if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
        }

        // Connect directly to FastAPI (bypass Next.js proxy to avoid response buffering)
        const fullUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${url}`;

        const es = new EventSource(fullUrl, { withCredentials: true });
        esRef.current = es;

        es.addEventListener('connected', () => {
            if (!mountedRef.current) return;
            setConnected(true);
            retriesRef.current = 0;
            setReconnectAttempts(0);
            onConnected?.();
        });

        es.onmessage = (event) => {
            if (!mountedRef.current) return;
            try {
                const parsed = JSON.parse(event.data) as { event: string; data: unknown };
                onEvent?.({ type: parsed.event, data: parsed.data });
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
                reconnectTimeoutRef.current = setTimeout(() => {
                    if (mountedRef.current) connect();
                }, delay);
            } else {
                onError?.(new Event('max_retries'));
            }
        };
    }, [url, onConnected, onEvent, onError, baseDelay, maxRetries]);

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
