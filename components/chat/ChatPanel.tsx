"use client";
import { useState, useRef, useEffect, useCallback } from 'react';
import type { Client, Message, CartEditItem } from '@/types';
import { chatService, feedbackService, cartService, ticketService } from '@/services';
import { useCart, useSession } from '@/contexts';
import { useSSE } from '@/hooks';
import AiStatusDot from './AiStatusDot';
import { default as FeedbackModal } from './FeedbackModal';
import { formatChatMessage, ImageMessageBubble } from './ChatMessage';

interface ChatPanelProps {
  selectedClient: Client | null;
  hasOpenTicket?: boolean;
  ticketStatus?: 'aperto' | 'in_lavorazione' | null;
}

export default function ChatPanel({ selectedClient, hasOpenTicket = false, ticketStatus = null }: ChatPanelProps) {
  const { refreshCart } = useCart();
  const { sessionId, chatMessages: messages, setChatMessages: setMessages, handleNewSession: onNewSession } = useSession();
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [pendingCartEdits, setPendingCartEdits] = useState<CartEditItem[] | null>(null);
  const [feedbackModalMessageId, setFeedbackModalMessageId] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  // Pending in-chat quantity request (replaces product modal)
  const [pendingQuantityRequest, setPendingQuantityRequest] = useState<{
    cod_art: string; name: string; des_um?: string; confidence?: number | null;
  } | null>(null);
  // Ticket mode state
  const [ticketMessages, setTicketMessages] = useState<Message[]>([]);
  // Guard to prevent concurrent image uploads
  const imageUploadInProgressRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  // Fetch ticket messages when ticket opens (persists across page refresh)
  useEffect(() => {
    if (!hasOpenTicket || !sessionId) {
      setTicketMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const ticket = await ticketService.getTicketBySession(sessionId);
        if (cancelled || !ticket) return;
        // Load existing messages from DB so chat persists across refreshes
        const allMessages = await chatService.getMessages(sessionId);
        if (cancelled) return;
        // Filter to only show messages from after the ticket was opened, excluding system messages
        const ticketOpenIdx = allMessages.findIndex(m =>
          m.role === 'assistant' && m.content.includes('operatore è stato allertato')
        );
        const relevantMessages = (ticketOpenIdx >= 0 ? allMessages.slice(ticketOpenIdx + 1) : [])
          .filter(m => !(m.role === 'assistant' && (
            m.content.includes('operatore ha preso in carico') ||
            m.content.includes('operatore ha rilasciato') ||
            m.content.includes('ticket di assistenza è stato chiuso') ||
            m.content.includes('ticket è stato chiuso')
          )));
        setTicketMessages(relevantMessages.map(m => ({
          id: m.id || String(Date.now()),
          dbId: m.dbId,
          role: m.role,
          content: m.content,
        })));
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [hasOpenTicket, sessionId]);

  // SSE: receive operator messages in ticket mode
  useSSE(sessionId ? `/sse/${sessionId}` : null, {
    onEvent: (event) => {
      if (event.type === 'message' && hasOpenTicket) {
        const msg = event.data as { id: number; sender: string; content: string };
        // Only show operator messages (not user own messages, not system messages)
        if (msg.sender !== 'user' && msg.sender !== 'system') {
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

  // Helper: add a message to UI state and persist it to DB in one shot
  const saveAndAddMessage = useCallback(async (content: string, sender: 'ai' | 'system' = 'ai'): Promise<number | undefined> => {
    const tempId = `${Date.now()}-${Math.random()}`;
    setMessages(prev => [...prev, { id: tempId, role: 'assistant', content }]);
    if (!sessionId) return undefined;
    try {
      const msgId = await chatService.saveMessage(sessionId, sender, content);
      if (msgId) {
        setMessages(prev => prev.map(m => m.id === tempId ? { ...m, dbId: msgId } : m));
        return msgId;
      }
    } catch (e) {
      console.error('saveAndAddMessage failed:', e);
    }
    return undefined;
  }, [sessionId, setMessages]);

  // In-chat quantity flow: ask user for quantity inside the chat instead of a modal
  const handleProductClick = useCallback(async (codArt: string, name: string, des_um?: string, confidence?: number | null) => {
    setAddError(null);
    setPendingQuantityRequest({ cod_art: codArt, name, des_um, confidence });
    const unitNote = des_um ? ` (unità di vendita: ${des_um})` : '';
    await saveAndAddMessage(`Quante **${name}** vuoi aggiungere?${unitNote}`);
  }, [saveAndAddMessage]);


  // Delegated click handler for product links rendered via dangerouslySetInnerHTML
  // These always go through the in-chat quantity flow (no modal)
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('product-link')) {
        const codArt = target.getAttribute('data-cod-art') || '';
        const name = target.getAttribute('data-product-name') || target.textContent?.trim() || '';
        handleProductClick(codArt, name);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [handleProductClick]);

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
      } catch {
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
    try {
      const data = await chatService.sendMessage(
        userMessage,
        selectedClient.cod_cli,
        sessionId,
        pendingCartEdits?.length ? pendingCartEdits : undefined,
      );
      console.log('[CHAT] API response:', JSON.stringify(data));
      if (data.success) {
        if (data.user_message_id) {
          setMessages(prev => prev.map(m => m.id === userMsg.id ? { ...m, dbId: data.user_message_id } : m));
        }
        const assistantMsg: Message = {
          id: (Date.now() + 1).toString(),
          dbId: data.ai_message_id || undefined,
          role: 'assistant',
          content: data.response || '',
          intent: data.intent,
          productConfidences: data.product_confidences,
        };
        setMessages(prev => [...prev, assistantMsg]);

        // Handle disambiguation candidates — attach to last assistant message
        if (data.disambiguation_candidates && Array.isArray(data.disambiguation_candidates) && data.disambiguation_candidates.length > 0) {
          const candidates = data.disambiguation_candidates;
          setMessages(prev => {
            const copy = [...prev];
            const lastIdx = copy.length - 1;
            if (lastIdx >= 0 && copy[lastIdx].role === 'assistant') {
              copy[lastIdx] = { ...copy[lastIdx], disambiguationCandidates: candidates };
            }
            return copy;
          });
        }

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
              await saveAndAddMessage('Alcune modifiche al carrello non sono state applicate. Riprova.');
            }
          } catch {
            await saveAndAddMessage('Non sono riuscito ad aggiornare il carrello. Riprova tra poco.');
          }
        } else if (data.edit_confirmed && pendingCartEdits?.length) {
          setPendingCartEdits(null);
        }

        // Product items handling — confidence-aware auto-add
        const productItems = Array.isArray(data.product_items) && data.product_items.length > 0
          ? data.product_items.map((it: { cod_art: string; quantity?: number }) => ({ cod_art: it.cod_art, qta: Number(it.quantity) || 1 }))
          : (data.product_codes || []).map((cod_art: string) => ({ cod_art, qta: 1 }));
        const orderConfirmed = data.order_confirmed === true;

        // Auto-add only high-confidence items (>= 0.50)
        const autoAddItems = productItems.filter(item => {
          const conf = data.product_confidences?.[item.cod_art];
          return conf !== undefined && conf >= 0.50;
        });

        if (orderConfirmed && autoAddItems.length >= 1 && selectedClient) {
          try {
            const failed: string[] = [];
            for (const { cod_art, qta } of autoAddItems) {
              const confidence = data.product_confidences?.[cod_art] ?? null;
              const cartResponse = await cartService.addItem(cod_art, qta, {
                source: 'ai',
                ai_confidence: confidence,
                related_message_id: data.ai_message_id || null,
                sessionId,
              });
              if (!cartResponse.ok) failed.push(cod_art);
            }
            await refreshCart();
            if (failed.length > 0) {
              const errMsg = failed.length === autoAddItems.length
                ? 'Ho provato ad aggiungere i prodotti al carrello, ma al momento non risultano disponibili per te. Prova a chiedere altre opzioni.'
                : `Alcuni prodotti non risultano disponibili e non sono stati aggiunti (codici: ${failed.join(', ')}). Gli altri sono stati inseriti.`;
              await saveAndAddMessage(errMsg);
            }
          } catch {
            const errMsg = 'Non sono riuscito ad aggiornare il carrello. Riprova tra poco.';
            await saveAndAddMessage(errMsg);
          }
        }
      } else {
        await saveAndAddMessage(data.error || 'Errore di connessione. Verifica che il servizio sia attivo.');
      }
    } catch (error) {
      console.error('Error sending message:', error);
      await saveAndAddMessage('Servizio chat non disponibile. Verifica che il servizio Python sia attivo sulla porta 8000.');
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

    // --- Intercept pending quantity request ---
    if (pendingQuantityRequest) {
      const isOnlyNumber = /^\s*\d+\s*$/.test(userMessage);
      if (isOnlyNumber) {
        const qty = parseInt(userMessage, 10);
        const req = pendingQuantityRequest;
        setPendingQuantityRequest(null);
        // Save and show user message
        const userMsgId = `${Date.now()}`;
        setMessages(prev => [...prev, { id: userMsgId, role: 'user', content: userMessage }]);
        if (sessionId) chatService.saveMessage(sessionId, 'user', userMessage).catch(console.error);
        // Add to cart and confirm
        try {
          const res = await cartService.addItem(req.cod_art, qty, {
            source: 'ai',
            ai_confidence: req.confidence ?? null,
            sessionId,
          });
          if (res.ok) {
            refreshCart();
            const unitLabel = req.des_um ? ` (${qty} ${req.des_um.toLowerCase()})` : ` (x${qty})`;
            await saveAndAddMessage(`**${req.name}**${unitLabel} aggiunto al carrello`);
          } else {
            const err = await res.json().catch(() => ({}));
            await saveAndAddMessage(err.detail || 'Errore nell\'aggiungere il prodotto. Riprova.');
          }
        } catch {
          await saveAndAddMessage('Errore di connessione. Riprova tra poco.');
        }
        return;
      }
      // Not a number → clear pending and fall through to normal chat
      setPendingQuantityRequest(null);
    }

    // --- Intercept /add command ---
    const ADD_REGEX = /^\/add\s+(.+?)\s+x_?(\d*)$/;
    const addMatch = userMessage.match(ADD_REGEX);
    if (addMatch) {
      const productName = addMatch[1].trim();
      const qta = addMatch[2] ? parseInt(addMatch[2], 10) : 1;
      if (isNaN(qta) || qta <= 0) {
        setAddError('Inserisci un numero valido');
        setInput(userMessage);
        return;
      }
      try {
        const res = await cartService.addByName(productName, qta, sessionId);
        if (res.ok) {
          refreshCart();
          await saveAndAddMessage(`**${productName}** x${qta} aggiunto al carrello`);
        } else {
          const err = await res.json().catch(() => ({}));
          setAddError(err.detail || 'Errore');
          setInput(userMessage);
        }
      } catch {
        setAddError('Errore di connessione');
        setInput(userMessage);
      }
      return;
    }

    // --- Normal AI chat ---
    await sendMessageContent(userMessage, false);
  };

  // --- Image processing core (shared by file picker, paste and drag & drop) ---
  const processImageFile = async (file: File | Blob) => {
    if (!selectedClient) return;
    if (imageUploadInProgressRef.current) return;
    imageUploadInProgressRef.current = true;

    const fileType = file instanceof File ? file.type : file.type;
    const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/heic'];
    if (!allowed.includes(fileType)) {
      alert('Formato non supportato. Usa JPEG, PNG, WebP o HEIC.');
      return;
    }

    let processedFile: Blob = file;
    if (fileType === 'image/heic') {
      try {
        const heic2any = (await import('heic2any')).default;
        const blob = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.8 });
        processedFile = blob instanceof Blob ? blob : (blob as Blob[])[0];
      } catch {
        alert('Impossibile convertire immagine HEIC. Prova con un altro formato.');
        return;
      }
    }

    if (processedFile.size > 5 * 1024 * 1024) {
      alert("L'immagine supera i 5MB. Riduci la dimensione e riprova.");
      return;
    }

    // Read base64 for immediate display (ImageMessageBubble expects raw base64)
    let imageBlobBase64 = '';
    try {
      imageBlobBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve((reader.result as string).split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(processedFile);
      });
    } catch { /* non-critical */ }
    console.log('[IMAGE DEBUG] file type:', processedFile.type, 'size:', processedFile.size, 'first 20 b64 chars:', imageBlobBase64.substring(0, 20));

    setIsUploadingImage(true);
    try {
      const result = await chatService.uploadImage(processedFile, sessionId);
      if (result.success) {
        // Optimistically add image message
        if (result.user_message_id) {
          setMessages(prev => {
            if (prev.some(m => m.dbId === result.user_message_id)) return prev;
            return [...prev, {
              id: String(result.user_message_id),
              dbId: result.user_message_id,
              role: 'user' as const,
              content: '',
              imageData: imageBlobBase64 || undefined,
            }];
          });
        }
        // Add AI response from handle_message result
        if (result.ai_message_id) {
          setMessages(prev => {
            if (prev.some(m => m.dbId === result.ai_message_id)) return prev;
            return [...prev, {
              id: String(result.ai_message_id),
              dbId: result.ai_message_id,
              role: 'assistant' as const,
              content: result.response || '',
              intent: result.intent,
              productConfidences: result.product_confidences,
            }];
          });
        }

        // Image flow: prefer backend cart sync (authoritative), fallback to client add.
        const productItems = Array.isArray(result.product_items) && result.product_items.length > 0
          ? result.product_items.map((it: { cod_art: string; quantity?: number }) => ({ cod_art: it.cod_art, qta: Number(it.quantity) || 1 }))
          : [];
        const orderConfirmed = result.order_confirmed === true;
        const cartSyncedByServer = result.cart_synced === true;

        if (orderConfirmed && selectedClient) {
          if (cartSyncedByServer) {
            await refreshCart();

            const failed = Array.isArray(result.cart_failed_codes) ? result.cart_failed_codes : [];
            const added = Array.isArray(result.cart_added_codes) ? result.cart_added_codes : [];
            if (failed.length > 0) {
              const errMsg = failed.length === (failed.length + added.length)
                ? 'Ho provato ad aggiungere i prodotti al carrello, ma al momento non risultano disponibili per te. Prova a chiedere altre opzioni.'
                : `Alcuni prodotti non risultano disponibili e non sono stati aggiunti (codici: ${failed.join(', ')}). Gli altri sono stati inseriti.`;
              await saveAndAddMessage(errMsg);
            }
          } else if (productItems.length >= 1) {
            // Fallback compatibility for backend versions that do not sync cart in /chat/image.
            try {
              const failed: string[] = [];
              for (const { cod_art, qta } of productItems) {
                const confidence = result.product_confidences?.[cod_art] ?? null;
                const cartResponse = await cartService.addItem(cod_art, qta, {
                  source: 'ai',
                  ai_confidence: confidence,
                  related_message_id: result.ai_message_id || null,
                  sessionId,
                });
                if (!cartResponse.ok) failed.push(cod_art);
              }
              await refreshCart();

              if (failed.length > 0) {
                const errMsg = failed.length === productItems.length
                  ? 'Ho provato ad aggiungere i prodotti al carrello, ma al momento non risultano disponibili per te. Prova a chiedere altre opzioni.'
                  : `Alcuni prodotti non risultano disponibili e non sono stati aggiunti (codici: ${failed.join(', ')}). Gli altri sono stati inseriti.`;
                await saveAndAddMessage(errMsg);
              }
            } catch {
              await saveAndAddMessage('Non sono riuscito ad aggiornare il carrello. Riprova tra poco.');
            }
          }
        }
      } else {
        alert(result.error || "Non sono riuscito a leggere l'immagine. Riprova.");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Errore upload';
      alert(msg);
    } finally {
      setIsUploadingImage(false);
      imageUploadInProgressRef.current = false;
    }
  };

  // --- File picker handler ---
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    await processImageFile(file);
  };

  // --- Paste (Ctrl+V) handler ---
  useEffect(() => {
    const handlePaste = async (e: ClipboardEvent) => {
      if (!selectedClient) return;
      const items = Array.from(e.clipboardData?.items || []);
      const imageItem = items.find(item => item.type.startsWith('image/'));
      if (!imageItem) return;
      e.preventDefault();
      const file = imageItem.getAsFile();
      if (file) await processImageFile(file);
    };
    document.addEventListener('paste', handlePaste);
    return () => document.removeEventListener('paste', handlePaste);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClient, sessionId]);

  // --- Drag & Drop handlers ---
  const handleDragOver = (e: React.DragEvent) => {
    if (!selectedClient) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    // Only clear when leaving the component entirely (not a child element)
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (!selectedClient || isUploadingImage) return;
    const file = Array.from(e.dataTransfer.files).find(f => f.type.startsWith('image/'));
    if (file) await processImageFile(file);
  };

  // =========================
  // RENDER
  // =========================
  return (
    <div
      className={`flex flex-col h-full w-full overflow-hidden transition-opacity duration-300 ${!selectedClient ? 'opacity-50 pointer-events-none' : 'opacity-100'} relative`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag & drop overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center bg-[hsl(234,60%,36%)]/10 backdrop-blur-[1px] border-2 border-dashed border-[hsl(234,60%,50%)] rounded-xl pointer-events-none">
          <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="hsl(234,60%,40%)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          <p className="mt-3 text-sm font-semibold text-[hsl(234,60%,35%)]">Rilascia per inviare l&apos;immagine</p>
        </div>
      )}

      {/* Image upload loading indicator */}
      {isUploadingImage && (
        <div className="shrink-0 bg-gradient-to-r from-[hsl(234,60%,97%)] via-[hsl(234,60%,94%)] to-[hsl(234,60%,97%)] border-b border-[hsl(234,60%,85%)] px-4 py-4 animate-fade-in">
          <div className="flex flex-col items-center gap-3">
            {/* Large spinning wheel above text */}
            <div className="relative w-14 h-14">
              <div className="absolute inset-0 rounded-full border-[4px] border-[hsl(234,60%,88%)] opacity-40" />
              <div className="absolute inset-0 rounded-full border-[4px] border-t-[hsl(234,60%,50%)] border-r-transparent border-b-transparent border-l-transparent animate-spin shadow-sm" />
              <div className="absolute inset-[5px] rounded-full border-[2.5px] border-[hsl(234,60%,75%)] border-t-transparent border-r-transparent border-b-transparent animate-spin shadow-sm" style={{ animationDirection: 'reverse', animationDuration: '0.7s' }} />
            </div>

            <div className="flex flex-col items-center gap-1">
              <p className="text-sm text-[hsl(234,60%,20%)] font-semibold">Elaboro l&apos;immagine...</p>
              <p className="text-xs text-[hsl(234,60%,45%)]">Un momento, per favore</p>
            </div>

            {/* Animated bar below text */}
            <div className="w-48 h-1.5 bg-[hsl(234,60%,90%)] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: '100%',
                  background: 'linear-gradient(90deg, hsl(234,60%,40%) 0%, hsl(234,60%,60%) 50%, hsl(234,60%,40%) 100%)',
                  backgroundSize: '200% 100%',
                  animation: 'imageUploadShimmer 1.4s ease-in-out infinite',
                }}
              />
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes imageUploadShimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>

      {/* Pending quantity indicator — subtle hint below the AI question bubble */}
      {pendingQuantityRequest && (
        <div className="shrink-0 px-4 py-2 bg-[hsl(234,60%,97%)] border-b border-[hsl(234,60%,88%)] flex items-center gap-2 text-xs text-[hsl(234,60%,40%)]">
          <span className="w-1.5 h-1.5 rounded-full bg-[hsl(234,60%,50%)] animate-pulse" />
          In attesa della quantità per <strong className="font-semibold">{pendingQuantityRequest.name}</strong>
          <button
            onClick={() => setPendingQuantityRequest(null)}
            className="ml-auto text-gray-400 hover:text-gray-600 text-[10px] font-medium"
          >
            Annulla
          </button>
        </div>
      )}

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
        <AiStatusDot hasOpenTicket={hasOpenTicket} ticketStatus={ticketStatus} />
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
              {m.imageData ? (
                <ImageMessageBubble imageData={m.imageData} isOperator={false} />
              ) : (
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
              )}

              {/* Disambiguation buttons — shown when backend detected multiple candidates */}
              {!m.imageData && m.role === 'assistant' && m.disambiguationCandidates && m.disambiguationCandidates.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2 ml-0">
                  {m.disambiguationCandidates.map((candidate) => (
                    <button
                      key={candidate.cod_art}
                      onClick={async () => {
                        if (!selectedClient) return;
                        try {
                          await cartService.addItem(candidate.cod_art, candidate.quantity || 1, {
                            source: 'ai',
                            ai_confidence: null,
                            related_message_id: m.dbId || null,
                            sessionId,
                          });
                          refreshCart();
                          // Remove disambiguation candidates from message after selection
                          setMessages(prev => prev.map(msg =>
                            msg.id === m.id
                              ? { ...msg, disambiguationCandidates: [] }
                              : msg
                          ));
                        } catch {
                          // silently ignore — item not available
                        }
                      }}
                      className="inline-flex items-center text-xs px-3 py-1.5 rounded-full border border-amber-400 bg-amber-50 text-amber-700 hover:bg-amber-100 hover:border-amber-500 transition-colors font-medium"
                      title={`Codice: ${candidate.cod_art}`}
                    >
                      {candidate.name}
                      {candidate.des_um ? <span className="ml-1 opacity-60">({candidate.des_um})</span> : null}
                    </button>
                  ))}
                </div>
              )}

              {/* Feedback buttons for AI messages */}
              {!m.imageData && m.role === 'assistant' && m.dbId && (
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
        {addError && (
          <p className="text-xs text-red-500 mt-1 px-1">{addError}</p>
        )}
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
              onChange={(e) => { setInput(e.target.value); setAddError(null); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSend();
                  inputRef.current?.blur();
                }
              }}
              placeholder={
                !selectedClient
                  ? "Seleziona cliente..."
                  : pendingQuantityRequest
                    ? "Inserisci la quantità..."
                    : "Scrivi un messaggio..."
              }
              className="flex-1 bg-gray-50 rounded-2xl px-4 text-sm outline-none focus:bg-white transition-all text-gray-900 border-2 border-transparent focus:border-[hsl(234,60%,80%)] disabled:cursor-not-allowed placeholder:text-gray-400 disabled:bg-gray-100"
            />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/heic"
              capture="environment"
              className="hidden"
              onChange={handleImageUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={!selectedClient || isLoading}
              className="w-12 h-12 rounded-2xl shadow-sm flex items-center justify-center transition-all active:scale-95 bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:bg-gray-100 disabled:text-gray-300"
              title="Invia foto"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
            </button>
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