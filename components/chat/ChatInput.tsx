// ============================================================
// components/chat/ChatInput.tsx — Barra di input messaggio e registrazione vocale
//
// Campo testo con pulsante invio e toggle registrazione audio.
// Gestisce il MediaRecorder per la cattura vocale e la
// visualizzazione dell'onda audio durante la registrazione.
// ============================================================

"use client";
import { useState, useRef } from 'react';

interface ChatInputProps {
    onSend: (message: string) => void;
    onVoiceBlob: (blob: Blob) => void;
    disabled?: boolean;
}

export default function ChatInput({ onSend, onVoiceBlob, disabled = false }: ChatInputProps) {
    const [input, setInput] = useState('');
    const [isRecording, setIsRecording] = useState(false);
    const [recordingTime, setRecordingTime] = useState(0);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const handleSend = () => {
        const trimmed = input.trim();
        if (!trimmed) return;
        setInput('');
        onSend(trimmed);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            chunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
            mediaRecorder.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                stream.getTracks().forEach(t => t.stop());
                if (blob.size > 0) onVoiceBlob(blob);
            };

            mediaRecorderRef.current = mediaRecorder;
            mediaRecorder.start();
            setIsRecording(true);
            setRecordingTime(0);
            timerRef.current = setInterval(() => setRecordingTime(t => t + 1), 1000);
        } catch {
            // Mic not available
        }
    };

    const stopRecording = (save: boolean) => {
        if (timerRef.current) clearInterval(timerRef.current);
        if (mediaRecorderRef.current?.state === 'recording') {
            if (!save) mediaRecorderRef.current.ondataavailable = null;
            mediaRecorderRef.current.stop();
        }
        setIsRecording(false);
        setRecordingTime(0);
    };

    const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

    return (
        <div className="shrink-0 border-t border-gray-100 px-3 py-2.5">
            {isRecording ? (
                <div className="flex items-center gap-3 animate-scale-in">
                    <div className="flex items-center gap-2 flex-1">
                        <span className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" />
                        <span className="text-xs font-bold text-red-500">{formatTime(recordingTime)}</span>
                        <span className="text-[10px] text-gray-400">Registrazione in corso...</span>
                    </div>
                    <button onClick={() => stopRecording(false)} className="w-9 h-9 flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-colors">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                    <button onClick={() => stopRecording(true)} className="w-9 h-9 flex items-center justify-center text-white bg-[hsl(234,60%,36%)] rounded-xl hover:bg-[hsl(234,60%,30%)] transition-colors shadow-sm">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12" />
                        </svg>
                    </button>
                </div>
            ) : (
                <div className="flex items-end gap-2">
                    <button onClick={startRecording} disabled={disabled} className="shrink-0 w-9 h-9 flex items-center justify-center text-gray-400 hover:text-[hsl(234,60%,36%)] hover:bg-[hsl(234,60%,95%)] rounded-xl transition-colors disabled:opacity-40">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" />
                            <line x1="8" y1="23" x2="16" y2="23" />
                        </svg>
                    </button>
                    <textarea
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={disabled}
                        placeholder="Scrivi un messaggio..."
                        rows={1}
                        className="flex-1 resize-none outline-none text-sm text-gray-800 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 max-h-24 focus:border-[hsl(234,60%,50%)] focus:bg-white transition-colors placeholder:text-gray-400 disabled:opacity-50"
                    />
                    <button onClick={handleSend} disabled={disabled || !input.trim()} className="shrink-0 w-9 h-9 flex items-center justify-center text-white bg-[hsl(234,60%,36%)] rounded-xl hover:bg-[hsl(234,60%,30%)] transition-colors shadow-sm disabled:opacity-40 active:scale-95">
                        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    </button>
                </div>
            )}
        </div>
    );
}
