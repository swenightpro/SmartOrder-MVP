"use client";
import { useEffect } from 'react';

interface ModalProps {
    children: React.ReactNode;
    onClose: () => void;
    maxWidth?: string;
}

export default function Modal({ children, onClose, maxWidth = 'max-w-4xl' }: ModalProps) {
    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);

    return (
        <div
            className="fixed inset-0 z-[200] flex items-center justify-center p-4 animate-fade-in"
            style={{ background: 'rgba(15, 20, 50, 0.55)', backdropFilter: 'blur(4px)' }}
            onClick={onClose}
        >
            <div
                className={`relative bg-white rounded-3xl shadow-2xl w-full ${maxWidth} max-h-[90vh] flex flex-col overflow-hidden animate-scale-in`}
                onClick={e => e.stopPropagation()}
            >
                {children}
            </div>
        </div>
    );
}
