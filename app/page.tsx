"use client";

import { useState, useEffect, useCallback } from "react";
import type { Client } from "@/types";
import { authService, sessionService, chatService, ticketService } from "@/services";
import { CartProvider, SessionProvider, useCart, useSession } from "@/contexts";
import { ChatPanel } from "@/components/chat";
import { CartPanel } from "@/components/cart";
import { AuthOverlay } from "@/components/auth";
import { OrderHistory } from "@/components/orders";
import { TopBar, MobileTabBar, AssistenzaModal } from "@/components/layout";
import { useSSE } from "@/hooks";

// ── Componente interno che consuma i Context ──────────────────
function AppContent({ selectedClient, onClientChange, onSessionIdChange }: {
  selectedClient: Client | null;
  onClientChange: (c: Client | null) => void;
  onSessionIdChange: (id: number | null) => void;
}) {
  const [activeTab, setActiveTab] = useState<"create" | "history">("create");
  const [refreshKey, setRefreshKey] = useState(0);
  const [showClientSelector, setShowClientSelector] = useState(true);
  const [mobilePanel, setMobilePanel] = useState<"chat" | "cart" | "history" | "assistenza">("chat");
  const [hasOpenTicket, setHasOpenTicket] = useState(false);
  const [showAssistenza, setShowAssistenza] = useState(false);

  const { cart, refreshCart, clearCart } = useCart();
  const { initSession, showNewSessionModal, cancelNewSession, confirmNewSession, setChatMessages, sessionId } = useSession();
  const handleConfirmNewSession = useCallback(async () => {
    await confirmNewSession();
    clearCart();
  }, [confirmNewSession, clearCart]);

  // Carica sessione auth esistente + redirect operatore — eseguito SOLO al mount
  useEffect(() => {
    let cancelled = false;
    const loadSession = async () => {
      try {
        const profile = await authService.getProfile();
        if (cancelled) return;
        if (profile?.role === 'admin') {
          window.location.href = '/operatore';
          return;
        }
        if (profile?.cod_cli && profile?.rag_soc) {
          onClientChange({ cod_cli: Number(profile.cod_cli), rag_soc: profile.rag_soc });
          setShowClientSelector(false);
        } else { setShowClientSelector(true); }
      } catch {
        if (!cancelled) setShowClientSelector(true);
      }
    };
    loadSession();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // esegue solo al mount — non dipende da onClientChange

  // Inizializza carrello e sessione quando il client cambia
  useEffect(() => {
    const setupSessionAndChat = async () => {
      if (selectedClient) {
        refreshCart();
        const sessionId = await initSession();
        onSessionIdChange(sessionId);

        let historyLoaded = false;
        if (sessionId) {
          try {
            const history = await chatService.getMessages(sessionId);
            if (history && history.length > 0) {
              setChatMessages(history);
              historyLoaded = true;
            }
          } catch (e) {
            console.error('Errore fetch storico messaggi:', e);
          }
        }

        if (!historyLoaded) {
          setChatMessages([{ id: 'welcome', role: 'assistant', content: `Ciao ${selectedClient.rag_soc}! Cosa ti serve oggi?` }]);
        }
      } else {
        setChatMessages([]);
        clearCart();
      }
    };

    setupSessionAndChat();
  }, [selectedClient, refreshCart, initSession, setChatMessages, clearCart, onSessionIdChange]);

  const handleOrderSuccess = useCallback(async () => {
    setRefreshKey((k) => k + 1);
    setActiveTab("history");
    setMobilePanel("history");
    clearCart();
    try {
      const newId = await sessionService.create();
      if (newId) { /* sessionId aggiornato dal context */ }
    } catch (e) { console.error('Errore reset sessione dopo ordine:', e); }
    setChatMessages([{ id: 'post-order-' + Date.now(), role: 'assistant', content: `Ordine confermato con successo! 🎉 Vuoi ordinare altro?` }]);
  }, [clearCart, setChatMessages]);

  const handleClientChange = (c: Client | null) => {
    onClientChange(c);
    setActiveTab("create");
    setMobilePanel("chat");
    if (c) setShowClientSelector(false);
  };

  const handleMobileTabChange = (panel: 'chat' | 'cart' | 'history' | 'assistenza') => {
    if (panel === 'assistenza') {
      setShowAssistenza(true);
      return;
    }
    setMobilePanel(panel);
    setActiveTab(panel === 'history' ? 'history' : 'create');
  };

  // Check ticket on session change
  useEffect(() => {
    if (!sessionId) return;
    ticketService.getTicketBySession(sessionId)
      .then(t => setHasOpenTicket(!!t))
      .catch(() => setHasOpenTicket(false));
  }, [sessionId]);

  // SSE: real-time ticket status updates
  useSSE(sessionId ? `/sse/${sessionId}` : null, {
    onEvent: (event) => {
      if (event.type === 'ticket_update') {
        const update = event.data as { status: string };
        if (update.status === 'chiuso') {
          setHasOpenTicket(false);
        } else {
          setHasOpenTicket(true);
        }
      }
    },
  });

  return (
    <main className="h-screen flex flex-col overflow-hidden">
      {showClientSelector && (
        <AuthOverlay
          currentClient={selectedClient}
          onClientChange={handleClientChange}
          onClose={selectedClient ? () => setShowClientSelector(false) : undefined}
        />
      )}

      {/* Modale conferma nuova sessione */}
      {showNewSessionModal && (
        <div
          className="fixed inset-0 z-[300] flex items-center justify-center p-4 animate-fade-in"
          style={{ background: 'rgba(15, 20, 50, 0.55)', backdropFilter: 'blur(4px)' }}
          onClick={cancelNewSession}
        >
          <div
            className="bg-white rounded-3xl shadow-2xl w-full max-w-sm p-6 space-y-4 animate-scale-in"
            onClick={e => e.stopPropagation()}
          >
            <div className="text-center">
              <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-[hsl(234,60%,95%)] flex items-center justify-center">
                <svg className="w-6 h-6 text-[hsl(234,60%,36%)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
              </div>
              <h3 className="text-base font-extrabold text-gray-900">Nuova sessione</h3>
              <p className="text-sm text-gray-500 mt-1">La conversazione attuale e il carrello verranno cancellati. Vuoi procedere?</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={cancelNewSession}
                className="flex-1 py-2.5 rounded-2xl text-sm font-bold border-2 border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
              >
                Annulla
              </button>

              <button
                onClick={handleConfirmNewSession}
                className="flex-1 py-2.5 rounded-2xl text-sm font-bold bg-[hsl(234,60%,36%)] text-white hover:bg-[hsl(234,60%,30%)] transition-all"
              >
                Conferma
              </button>

            </div>
          </div>
        </div>
      )}

      <TopBar onProfileClick={() => setShowClientSelector(true)} onAssistenzaClick={() => setShowAssistenza(true)} hasOpenTicket={hasOpenTicket} />

      {selectedClient && (
        <MobileTabBar activePanel={mobilePanel} cartCount={cart.length} onTabChange={handleMobileTabChange} hasOpenTicket={hasOpenTicket} />
      )}

      {/* Assistenza modal */}
      {showAssistenza && (
        <AssistenzaModal
          sessionId={sessionId}
          onClose={() => setShowAssistenza(false)}
          onTicketChange={() => {
            if (sessionId) {
              ticketService.getTicketBySession(sessionId).then(t => setHasOpenTicket(!!t)).catch(() => setHasOpenTicket(false));
            }
          }}
        />
      )}

      {/* DESKTOP LAYOUT */}
      <div className="hidden md:flex flex-1 overflow-hidden gap-3 p-3">
        <div className="w-[45%] bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <ChatPanel selectedClient={selectedClient} hasOpenTicket={hasOpenTicket} />
        </div>

        <div className="w-[55%] flex flex-col gap-3">
          <div className="flex gap-2 shrink-0">
            <button onClick={() => setActiveTab("create")} disabled={!selectedClient}
              className={`flex-1 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === "create" ? "bg-[hsl(234,60%,36%)] text-white shadow-lg shadow-[hsl(234,60%,36%)]/20" : "bg-white border-2 border-gray-200 text-gray-500 hover:border-[hsl(234,60%,80%)]"}`}>
              Carrello
            </button>
            <button onClick={() => setActiveTab("history")} disabled={!selectedClient}
              className={`flex-1 py-2.5 rounded-xl text-sm font-bold transition-all ${activeTab === "history" ? "bg-[hsl(234,60%,36%)] text-white shadow-lg shadow-[hsl(234,60%,36%)]/20" : "bg-white border-2 border-gray-200 text-gray-500 hover:border-[hsl(234,60%,80%)]"}`}>
              Storico
            </button>
          </div>

          {activeTab === "create" ? (
            selectedClient ? (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 flex-1 overflow-hidden">
                <CartPanel currentClient={selectedClient} onOrderSuccess={handleOrderSuccess} />
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-300 italic text-sm">Seleziona un cliente per iniziare</div>
            )
          ) : (
            <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex-1 overflow-hidden">
              {selectedClient ? (
                <OrderHistory cod_cli={String(selectedClient.cod_cli)} key={`${selectedClient.cod_cli}-${refreshKey}`} />
              ) : (
                <div className="h-full flex items-center justify-center text-gray-300 italic text-sm">Seleziona un cliente</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* MOBILE LAYOUT */}
      <div className="md:hidden flex-1 flex flex-col overflow-hidden">
        {mobilePanel === "chat" && (
          <div className="flex-1 bg-white overflow-hidden">
            <ChatPanel selectedClient={selectedClient} hasOpenTicket={hasOpenTicket} />
          </div>
        )}
        {mobilePanel === "cart" && (
          <div className="flex-1 bg-white overflow-hidden">
            {selectedClient ? (
              <CartPanel currentClient={selectedClient} onOrderSuccess={handleOrderSuccess} isMobile={true} />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-300 italic text-xs px-4 text-center">Seleziona un cliente per iniziare</div>
            )}
          </div>
        )}
        {mobilePanel === "history" && (
          <div className="flex-1 bg-white overflow-hidden p-3">
            {selectedClient ? (
              <OrderHistory cod_cli={String(selectedClient.cod_cli)} key={`${selectedClient.cod_cli}-${refreshKey}`} />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-300 italic text-xs px-4 text-center">Seleziona un cliente</div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

// ── Componente root — inietta i provider ──────────────────────
export default function Home() {
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);

  return (
    <CartProvider codCli={selectedClient?.cod_cli} sessionId={sessionId}>
      <SessionProvider clientName={selectedClient?.rag_soc} onSessionReset={() => {
        // Svuota il carrello nella UI quando viene confermata una nuova sessione
        // clearCart è accessibile qui perché siamo dentro <CartProvider>
      }}>

        <AppContent selectedClient={selectedClient} onClientChange={setSelectedClient} onSessionIdChange={setSessionId} />
      </SessionProvider>
    </CartProvider>
  );
}