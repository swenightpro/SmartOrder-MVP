"use client";
import { useState, useRef, useEffect, useCallback } from 'react';
import type { Client, Message, SuggestedProduct, CartEditItem } from '@/types';
import { chatService, feedbackService, cartService, ticketService } from '@/services';
import { useCart, useSession } from '@/contexts';
import { useSSE } from '@/hooks';
import AiStatusDot from './AiStatusDot';
import { default as FeedbackModal } from './FeedbackModal';
import { formatChatMessage, extractBoldProducts } from './ChatMessage';

interface ChatPanelProps {
  selectedClient: Client | null;
  hasOpenTicket?: boolean;
}

export default function ChatPanel({ selectedClient, hasOpenTicket = false }: ChatPanelProps) {
  const { refreshCart } = useCart();
  const { sessionId, chatMessages: messages, setChatMessages: setMessages, handleNewSession: onNewSession } = useSession();
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingCartEdits, setPendingCartEdits] = useState<CartEditItem[] | null>(null);
  const [feedbackModalMessageId, setFeedbackModalMessageId] = useState<string | null>(null);
  // Ticket mode state
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [ticketMessages, setTicketMessages] = useState<Message[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const pendingVoiceSendRef = useRef(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const volumeHistory = useRef<number[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, ticketMessages]);

  // Fetch ticket ID when ticket opens
  useEffect(() => {
    if (!hasOpenTicket || !sessionId) {
      setTicketId(null);
      setTicketMessages([]);
      return;
    }
    ticketService.getTicketBySession(sessionId)
      .then(ticket => {
        if (ticket) {
          setTicketId(ticket.id);
          setTicketMessages([]);
        }
      })
      .catch(() => {});
  }, [hasOpenTicket, sessionId]);

  // SSE: receive operator messages in ticket mode
  useSSE(sessionId ? `/sse/${sessionId}` : null, {
    onEvent: (event) => {
      if (event.type === 'message' && hasOpenTicket) {
        const msg = event.data as { id: number; sender: string; content: string };
        // Only show operator/assistant messages (not user own messages)
        if (msg.sender !== 'user') {
          setTicketMessages(prev => {
            if (prev.some(m => m.id === String(msg.id))) return prev;
            return [...prev, { id: String(msg.id), role: 'assistant', content: msg.content }];
          });
        }
      }
    },
  });

  // Audio Visualizer
  useEffect(() => {
    if (!isRecording || !canvasRef.current || !analyserRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const barWidth = 2;
    const gap = 2;
    const maxBars = Math.ceil(rect.width / (barWidth + gap));
    const buffer = new Uint8Array(analyserRef.current.frequencyBinCount);
    let tick = 0;
    const render = () => {
      tick++;
      if (tick % 3 === 0) {
        analyserRef.current!.getByteFrequencyData(buffer);
        let sum = 0;
        const range = Math.floor(buffer.length / 2);
        for (let i = 0; i < range; i++) sum += buffer[i];
        const avg = sum / range;
        volumeHistory.current.push(avg);
        if (volumeHistory.current.length > maxBars + 4) volumeHistory.current.shift();
      }
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.fillStyle = 'hsl(234, 60%, 36%)';
      const history = volumeHistory.current;
      for (let i = 0; i < history.length; i++) {
        const val = history[history.length - 1 - i] || 0;
        let h = (val / 255) * rect.height * 1.5;
        h = Math.max(2, Math.min(h, rect.height));
        const x = rect.width - (i * (barWidth + gap)) - barWidth;
        const y = (rect.height - h) / 2;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, y, barWidth, h, 4);
        else ctx.rect(x, y, barWidth, h);
        ctx.fill();
      }
      animationRef.current = requestAnimationFrame(render);
    };
    render();
    return () => { if (animationRef.current) cancelAnimationFrame(animationRef.current); };
  }, [isRecording]);

  // Cleanup globale microfono se smonto il componente
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach(track => track.stop());
    };
  }, []);

  // --- Recording ---
  const startRecording = async () => {
    if (!selectedClient) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, autoGainControl: true, noiseSuppression: true }
      });
      streamRef.current = stream;
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      volumeHistory.current = [];
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        ctx.close();
        stream.getTracks().forEach(t => t.stop());
        if (pendingVoiceSendRef.current && audioChunksRef.current.length > 0) {
          const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          pendingVoiceSendRef.current = false;
          sendVoiceBlob(blob);
        }
      };
      mediaRecorder.current = recorder;
      recorder.start(1000);
      setIsRecording(true);
    } catch {
      alert("Impossibile accedere al microfono");
    }
  };

  const stopRecording = (save: boolean) => {
    if (!mediaRecorder.current) return;
    if (save) pendingVoiceSendRef.current = true;
    mediaRecorder.current.stop();
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    setIsRecording(false);
  };

  // --- Feedback ---
  const handleFeedback = useCallback(async (messageId: string, dbId: number | undefined, isPositive: boolean, reason?: string | null, comment?: string) => {
    if (!dbId) return;
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, feedback: { is_positive: isPositive } } : m));
    try {
      await feedbackService.submit(dbId, isPositive, reason, comment);
    } catch (e) {
      console.error('Errore invio feedback:', e);
    }
  }, [setMessages]);

  const removeFeedback = useCallback(async (messageId: string, dbId: number | undefined) => {
    if (!dbId) return;
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, feedback: null } : m));
    try {
      await feedbackService.delete(dbId);
    } catch (e) {
      console.error('Errore rimozione feedback:', e);
    }
  }, [setMessages]);

  // --- Send message ---
  const sendMessageContent = async (userMessage: string, isVoice = false) => {
    if (!selectedClient) return;
    const displayContent = isVoice ? `🎙️ ${userMessage}` : userMessage;

    // --- Ticket mode: send to operator ---
    if (hasOpenTicket && sessionId) {
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: displayContent };
      setTicketMessages(prev => [...prev, userMsg]);
      setIsLoading(true);
      try {
        await ticketService.sendCustomerMessage(sessionId, userMessage);
        // Operator response comes via SSE - added to ticketMessages
      } catch (e) {
        setTicketMessages(prev => prev.filter(m => m.id !== userMsg.id));
        setIsLoading(false);
        return;
      }
      setIsLoading(false);
      return;
    }

    // --- Normal AI chat ---
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: displayContent };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);
    const history = [...messages, { role: 'user' as const, content: displayContent }].slice(-10).map((m) => ({ role: m.role, content: m.content }));
    try {
      const data = await chatService.sendMessage(
        userMessage,
        selectedClient.cod_cli,
        history,
        sessionId,
        pendingCartEdits?.length ? pendingCartEdits : undefined,
      );
      if (data.success) {
        if (data.user_message_id) {
          setMessages(prev => prev.map(m => m.id === userMsg.id ? { ...m, dbId: data.user_message_id } : m));
        }
        const assistantMsg: Message = {
          id: (Date.now() + 1).toString(),
          dbId: data.ai_message_id || undefined,
          role: 'assistant',
          content: data.response || '',
        };
        setMessages(prev => [...prev, assistantMsg]);

        // Cart edits handling
        const cartEdits = Array.isArray(data.cart_edits) ? data.cart_edits : [];
        if (cartEdits.length > 0 && !data.edit_confirmed) {
          setPendingCartEdits(cartEdits as CartEditItem[]);
        } else if (cartEdits.length > 0 && data.edit_confirmed) {
          setPendingCartEdits(null);
          try {
            const failed: string[] = [];
            for (const edit of cartEdits as CartEditItem[]) {
              if (edit.action === 'remove') {
                const res = await cartService.removeItem(edit.cart_item_id);
                if (!res.ok) failed.push(String(edit.cart_item_id));
              } else if (edit.action === 'set_quantity' && edit.new_quantity != null) {
                const res = await cartService.updateQty(edit.cart_item_id, edit.new_quantity);
                if (!res.ok) failed.push(String(edit.cart_item_id));
              }
            }
            refreshCart();
            if (failed.length > 0) {
              setMessages(prev => [...prev, { id: (Date.now() + 2).toString(), role: 'assistant', content: 'Alcune modifiche al carrello non sono state applicate. Riprova.' }]);
            }
          } catch {
            setMessages(prev => [...prev, { id: (Date.now() + 2).toString(), role: 'assistant', content: 'Non sono riuscito ad aggiornare il carrello. Riprova tra poco.' }]);
          }
        } else if (data.edit_confirmed && pendingCartEdits?.length) {
          setPendingCartEdits(null);
        }

        // Product items handling
        const productItems = Array.isArray(data.product_items) && data.product_items.length > 0
          ? data.product_items.map((it: { cod_art: string; quantity?: number }) => ({ cod_art: it.cod_art, qta: Number(it.quantity) || 1 }))
          : (data.product_codes || []).map((cod_art: string) => ({ cod_art, qta: 1 }));
        const orderConfirmed = data.order_confirmed === true;

        let suggestedProducts: SuggestedProduct[] = [];
        if (!orderConfirmed && data.response) {
          const boldNames = extractBoldProducts(data.response);
          if (boldNames.length > 0) {
            suggestedProducts = boldNames.map((name) => ({ name }));
          }
        }

        if (orderConfirmed && productItems.length >= 1 && selectedClient) {
          try {
            const failed: string[] = [];
            for (const { cod_art, qta } of productItems) {
              const confidence = data.product_confidences?.[cod_art] ?? null;
              const cartResponse = await cartService.addItem(cod_art, qta, {
                source: 'ai',
                ai_confidence: confidence,
                related_message_id: data.ai_message_id || null,
              });
              if (!cartResponse.ok) failed.push(cod_art);
            }
            refreshCart();
            if (failed.length > 0) {
              const followUp: Message = {
                id: (Date.now() + 2).toString(),
                role: 'assistant',
                content: failed.length === productItems.length
                  ? 'Ho provato ad aggiungere i prodotti al carrello, ma al momento non risultano disponibili per te. Prova a chiedere altre opzioni.'
                  : `Alcuni prodotti non risultano al momento disponibili e non sono stati aggiunti al carrello (codici: ${failed.join(', ')}). Gli altri sono stati inseriti.`,
              };
              setMessages(prev => [...prev, followUp]);
            }
          } catch {
            setMessages(prev => [...prev, { id: (Date.now() + 2).toString(), role: 'assistant', content: 'Non sono riuscito ad aggiornare il carrello. Riprova tra poco.' }]);
          }
        } else if (suggestedProducts.length > 0) {
          setMessages(prev => {
            const copy = [...prev];
            const lastIdx = copy.length - 1;
            if (lastIdx >= 0 && copy[lastIdx].role === 'assistant') {
              copy[lastIdx] = { ...copy[lastIdx], suggestedProducts };
            }
            return copy;
          });
        }
      } else {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: data.error || 'Errore di connessione. Verifica che il servizio sia attivo.' }]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'assistant', content: 'Servizio chat non disponibile. Verifica che il servizio Python sia attivo sulla porta 8000.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const sendVoiceBlob = async (blob: Blob) => {
    if (!selectedClient) return;
    setIsLoading(true);
    try {
      const text = await chatService.transcribe(blob);
      if (!text) {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: '🎙️ (nessun testo riconosciuto)' }, { id: (Date.now() + 1).toString(), role: 'assistant', content: 'Non ho capito nulla dall\'audio. Puoi ripetere o scrivere?' }]);
        return;
      }
      await sendMessageContent(text, true);
    } catch (e) {
      console.error('Transcribe error:', e);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: 'Impossibile trascrivere l\'audio. Verifica il microfono e riprova.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !selectedClient) return;
    const userMessage = input.trim();
    setInput('');
    await sendMessageContent(userMessage, false);
  };

  // =========================
  // RENDER
  // =========================
  return (
    <div className={`flex flex-col h-full w-full overflow-hidden transition-opacity duration-300 ${!selectedClient ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>

      {/* Feedback modal */}
      {feedbackModalMessageId && (() => {
        const msg = messages.find(m => m.id === feedbackModalMessageId);
        if (!msg) return null;
        return (
          <FeedbackModal
            onSubmit={(reason, comment) => {
              handleFeedback(msg.id, msg.dbId, false, reason, comment);
              setFeedbackModalMessageId(null);
            }}
            onClose={() => setFeedbackModalMessageId(null)}
          />
        );
      })()}

      {/* Header */}
      <div className="shrink-0 px-4 py-2.5 border-b border-gray-100 flex items-center gap-3">
        <AiStatusDot />
        <div className="flex-1" />
        {selectedClient && (
          <button
            onClick={onNewSession}
            disabled={hasOpenTicket}
            title={hasOpenTicket ? 'Chiudi prima il ticket di assistenza per avviare una nuova sessione' : undefined}
            className="text-[10px] font-bold text-[hsl(234,60%,36%)] bg-[hsl(234,60%,96%)] border border-[hsl(234,60%,85%)] px-2.5 py-1 rounded-full hover:bg-[hsl(234,60%,92%)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Nuova sessione
          </button>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 custom-scrollbar" style={{ background: 'linear-gradient(to bottom, hsl(230, 25%, 97%), hsl(230, 20%, 95%))' }}>
        {!selectedClient ? (
          <div className="h-full flex items-center justify-center text-center p-8">
            <p className="text-gray-400 italic text-sm">Identifica un cliente per iniziare</p>
          </div>
        ) : hasOpenTicket ? (
          // Ticket mode: show conversation with operator
          <>
            {/* Ticket banner */}
            <div className="flex items-center justify-center gap-2 mb-3 px-3 py-2 bg-[hsl(234,60%,96%)] border border-[hsl(234,60%,88%)] rounded-xl">
              <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              <p className="text-[11px] font-bold text-[hsl(234,60%,36%)]">Chatta con l&apos;operatore</p>
            </div>
            {ticketMessages.length === 0 && (
              <div className="flex items-center justify-center h-24 text-gray-400 italic text-sm">
                Inizia la conversazione...
              </div>
            )}
            {ticketMessages.map((m, idx) => (
              <div key={m.id}>
                <div className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`} style={{ animationDelay: `${idx * 30}ms` }}>
                  <div className={`max-w-[82%] px-4 py-3 text-[14px] leading-relaxed shadow-sm ${m.role === 'user'
                    ? 'bg-gradient-to-br from-[hsl(234,62%,30%)] to-[hsl(234,55%,40%)] text-white rounded-2xl rounded-br-md'
                    : 'bg-white text-gray-800 border border-gray-100 rounded-2xl rounded-bl-md'
                    }`}>
                    {m.role === "assistant" ? (
                      <span className="break-words [&_strong]:font-semibold" dangerouslySetInnerHTML={{ __html: formatChatMessage(m.content) }} />
                    ) : (
                      m.content
                    )}
                  </div>
                </div>
              </div>
            ))}
          </>
        ) : (
          // Normal AI chat mode
          messages.map((m, idx) => (
            <div key={m.id}>
              <div className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`} style={{ animationDelay: `${idx * 30}ms` }}>
                <div className={`max-w-[82%] px-4 py-3 text-[14px] leading-relaxed shadow-sm ${m.role === 'user'
                  ? 'bg-gradient-to-br from-[hsl(234,62%,30%)] to-[hsl(234,55%,40%)] text-white rounded-2xl rounded-br-md'
                  : 'bg-white text-gray-800 border border-gray-100 rounded-2xl rounded-bl-md'
                  }`}>
                  {m.role === "assistant" ? (
                    <span className="break-words [&_strong]:font-semibold" dangerouslySetInnerHTML={{ __html: formatChatMessage(m.content) }} />
                  ) : (
                    m.content
                  )}
                </div>
              </div>

              {/* Feedback buttons for AI messages */}
              {m.role === 'assistant' && m.dbId && (
                <div className="flex items-center gap-1 mt-1 ml-0">
                  <button
                    onClick={() => {
                      if (m.feedback?.is_positive === true) removeFeedback(m.id, m.dbId);
                      else if (!m.feedback) handleFeedback(m.id, m.dbId, true);
                    }}
                    className={`p-1 rounded-md transition-all ${m.feedback?.is_positive === true
                      ? 'text-emerald-500 hover:text-emerald-300'
                      : m.feedback ? 'text-gray-200 cursor-default' : 'text-gray-300 hover:text-emerald-400 hover:bg-emerald-50'
                      }`}
                    title={m.feedback?.is_positive === true ? 'Rimuovi feedback' : 'Risposta utile'}
                  >
                    <svg className="w-3.5 h-3.5" fill={m.feedback?.is_positive === true ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                    </svg>
                  </button>
                  <button
                    onClick={() => {
                      if (m.feedback?.is_positive === false) removeFeedback(m.id, m.dbId);
                      else if (!m.feedback) setFeedbackModalMessageId(m.id);
                    }}
                    className={`p-1 rounded-md transition-all ${m.feedback?.is_positive === false
                      ? 'text-red-500 hover:text-red-300'
                      : m.feedback ? 'text-gray-200 cursor-default' : 'text-gray-300 hover:text-red-400 hover:bg-red-50'
                      }`}
                    title={m.feedback?.is_positive === false ? 'Rimuovi feedback' : 'Segnala problema'}
                  >
                    <svg className="w-3.5 h-3.5" fill={m.feedback?.is_positive === false ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex justify-start animate-fade-in">
            <div className="bg-white text-gray-800 border border-gray-100 rounded-2xl rounded-bl-md px-5 py-3.5 max-w-[82%]">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 bg-[hsl(234,60%,36%)] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-[hsl(234,60%,36%)] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-[hsl(234,60%,36%)] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 p-3 bg-white border-t border-gray-100">
        {isRecording ? (
          <div className="h-12 bg-[hsl(234,60%,97%)] rounded-2xl border-2 border-[hsl(234,60%,80%)] flex items-center px-3 animate-fade-in">
            <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse mr-3 shrink-0" />
            <div className="flex-1 h-full overflow-hidden flex items-center">
              <canvas ref={canvasRef} className="w-full h-7" />
            </div>
            <div className="flex gap-1.5 ml-2 shrink-0">
              <button onClick={() => stopRecording(false)} className="w-9 h-9 flex items-center justify-center text-gray-400 hover:bg-gray-100 rounded-xl transition-colors text-sm font-bold">✕</button>
              <button onClick={() => stopRecording(true)} className="w-9 h-9 flex items-center justify-center bg-[hsl(234,60%,36%)] text-white rounded-xl hover:bg-[hsl(234,60%,30%)] transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2 h-12">
            <input
              ref={inputRef}
              type="text"
              disabled={!selectedClient}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSend();
                  inputRef.current?.blur();
                }
              }}
              placeholder={selectedClient ? "Scrivi un messaggio..." : "Seleziona cliente..."}
              className="flex-1 bg-gray-50 rounded-2xl px-4 text-sm outline-none focus:bg-white transition-all text-gray-900 border-2 border-transparent focus:border-[hsl(234,60%,80%)] disabled:cursor-not-allowed placeholder:text-gray-400 disabled:bg-gray-100"
            />
            <button
              onClick={() => {
                if (input.trim()) {
                  handleSend();
                  inputRef.current?.blur();
                } else {
                  startRecording();
                }
              }}
              disabled={(!selectedClient && !input.trim()) || isLoading}
              className={`w-12 h-12 rounded-2xl shadow-sm flex items-center justify-center transition-all active:scale-95 ${input.trim()
                ? 'bg-[hsl(234,60%,36%)] text-white hover:bg-[hsl(234,60%,30%)]'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                } disabled:bg-gray-100 disabled:text-gray-300`}
            >
              {input.trim() ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}