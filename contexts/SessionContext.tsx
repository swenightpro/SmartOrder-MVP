// ============================================================
// contexts/SessionContext.tsx — Provider globale per sessione chat e messaggi
//
// Design Pattern: Dependency Injection (React Context)
// Centralizza la gestione di: sessione corrente, messaggi chat,
// e la logica di nuova sessione (modale di conferma incluso).
// I componenti consumano il contesto tramite l'hook useSession().
//
// Dipendenze: sessionService, cartService (Facade pattern)
// ============================================================

"use client";

import { createContext, useContext, useState, useCallback, type ReactNode, type Dispatch, type SetStateAction } from 'react';
import type { Message } from '@/types';
import { sessionService, cartService } from '@/services';

interface SessionContextValue {
    sessionId: number | null;
    chatMessages: Message[];
    setChatMessages: Dispatch<SetStateAction<Message[]>>;
    initSession: () => Promise<number | null>;
    showNewSessionModal: boolean;
    handleNewSession: () => void;
    confirmNewSession: () => Promise<void>;
    cancelNewSession: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession(): SessionContextValue {
    const ctx = useContext(SessionContext);
    if (!ctx) throw new Error('useSession deve essere usato dentro un <SessionProvider>');
    return ctx;
}

interface SessionProviderProps {
    children: ReactNode;
    clientName?: string;
    onSessionReset?: () => void;
}

export function SessionProvider({ children, clientName, onSessionReset }: SessionProviderProps) {
    const [sessionId, setSessionId] = useState<number | null>(null);
    const [chatMessages, setChatMessages] = useState<Message[]>([]);
    const [showNewSessionModal, setShowNewSessionModal] = useState(false);

    const initSession = useCallback(async () => {
        const existing = await sessionService.getActive();
        if (existing) { setSessionId(existing); return existing; }
        const created = await sessionService.create();
        if (created) { setSessionId(created); return created; }
        return null;
    }, []);

    const handleNewSession = useCallback(() => {
        setShowNewSessionModal(true);
    }, []);

    const cancelNewSession = useCallback(() => {
        setShowNewSessionModal(false);
    }, []);

    const confirmNewSession = useCallback(async () => {
        setShowNewSessionModal(false);

        // Svuota il carrello corrente
        if (sessionId) {
            try {
                const items = await cartService.getCart();
                for (const item of items) {
                    await cartService.removeItem(item.id);
                }
            } catch (e) { console.error('Errore svuotamento carrello:', e); }
        }

        // Crea una nuova sessione
        try {
            const newId = await sessionService.create();
            if (newId) setSessionId(newId);
        } catch (e) { console.error('Errore creazione nuova sessione:', e); }

        setChatMessages([{
            id: 'welcome-' + Date.now(),
            role: 'assistant',
            content: `Ciao ${clientName || ''}! Nuova sessione iniziata. Cosa ti serve?`
        }]);

        // Notifica il parent (page.tsx) per svuotare lo stato UI del carrello
        onSessionReset?.();
    }, [sessionId, clientName, onSessionReset]);

    return (
        <SessionContext.Provider value={{
            sessionId, chatMessages, setChatMessages,
            initSession, showNewSessionModal,
            handleNewSession, confirmNewSession, cancelNewSession,
        }}>
            {children}
        </SessionContext.Provider>
    );
}
