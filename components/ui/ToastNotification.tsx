"use client";
import { createContext, useContext, useState, useCallback, useEffect } from 'react';

interface Toast {
    id: number;
    message: string;
    type: 'success' | 'error';
}

interface ToastContextValue {
    showToast: (message: string, type?: 'success' | 'error') => void;
}

const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });

export function useToast() {
    return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const [nextId, setNextId] = useState(1);

    const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
        const id = nextId;
        setNextId(n => n + 1);
        setToasts(prev => [...prev, { id, message, type }]);
    }, [nextId]);

    const dismiss = useCallback((id: number) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
                {toasts.map(toast => (
                    <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
                ))}
            </div>
        </ToastContext.Provider>
    );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
    useEffect(() => {
        const timer = setTimeout(() => onDismiss(toast.id), 8000);
        return () => clearTimeout(timer);
    }, [toast.id, onDismiss]);

    const isError = toast.type === 'error';

    return (
        <div
            className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg border max-w-sm animate-slide-in ${
                isError
                    ? 'bg-red-50 border-red-200 text-red-800'
                    : 'bg-green-50 border-green-200 text-green-800'
            }`}
        >
            <span className={`mt-0.5 shrink-0 ${isError ? 'text-red-500' : 'text-green-500'}`}>
                {isError ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                )}
            </span>
            <p className="text-sm font-medium flex-1 leading-snug">{toast.message}</p>
            <button
                onClick={() => onDismiss(toast.id)}
                className={`shrink-0 ml-1 p-0.5 rounded ${isError ? 'hover:bg-red-100 text-red-400' : 'hover:bg-green-100 text-green-400'} transition-colors`}
            >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                    <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
                </svg>
            </button>
        </div>
    );
}
