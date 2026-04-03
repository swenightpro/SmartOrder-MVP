"use client";
import { useState } from 'react';

interface FeedbackModalProps {
    onSubmit: (reason: string | null, comment: string) => void;
    onClose: () => void;
}

const REASONS = [
    'Risposta non pertinente',
    'Prodotto sbagliato',
    'Quantità errata',
    'Informazioni mancanti',
    'Altro',
];

export default function FeedbackModal({ onSubmit, onClose }: FeedbackModalProps) {
    const [selectedReason, setSelectedReason] = useState<string | null>(null);
    const [comment, setComment] = useState('');

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-fade-in"
            style={{ background: 'rgba(15,20,50,0.4)', backdropFilter: 'blur(3px)' }}
            onClick={onClose}
        >
            <div
                className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-5 space-y-4 animate-scale-in"
                onClick={e => e.stopPropagation()}
            >
                <h3 className="text-sm font-bold text-gray-900">Perché non è stato utile?</h3>

                <div className="space-y-1.5">
                    {REASONS.map(r => (
                        <button
                            key={r}
                            onClick={() => setSelectedReason(r === selectedReason ? null : r)}
                            className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium transition-all border ${selectedReason === r
                                ? 'bg-[hsl(234,60%,95%)] border-[hsl(234,60%,70%)] text-[hsl(234,60%,36%)]'
                                : 'bg-white border-gray-100 text-gray-600 hover:bg-gray-50'
                                }`}
                        >
                            {r}
                        </button>
                    ))}
                </div>

                <textarea
                    placeholder="Commento opzionale..."
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-xl text-xs text-gray-700 resize-none h-16 outline-none focus:border-[hsl(234,60%,50%)]"
                />

                <div className="flex gap-2">
                    <button onClick={onClose} className="flex-1 py-2 text-xs font-bold text-gray-500 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors">
                        Annulla
                    </button>
                    <button
                        onClick={() => onSubmit(selectedReason, comment)}
                        className="flex-1 py-2 text-xs font-bold text-white bg-red-500 rounded-xl hover:bg-red-600 transition-colors"
                    >
                        Invia feedback
                    </button>
                </div>
            </div>
        </div>
    );
}
