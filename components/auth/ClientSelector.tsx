"use client";
import { useState, useEffect } from 'react';
import { buildApiUrl } from '@/lib/apiClient';

export interface Client {
    cod_cli: number;
    rag_soc: string;
}

interface ClientSelectorProps {
    onClientChange: (client: Client | null) => void;
    currentClient?: Client | null;
    isOverlay?: boolean;
}

export default function ClientSelector({ onClientChange, currentClient, isOverlay = false }: ClientSelectorProps) {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<Client[]>([]);
    const [selected, setSelected] = useState<Client | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (currentClient) {
            setSelected(currentClient);
            setQuery(currentClient.rag_soc);
        } else {
            setSelected(null);
            setQuery('');
        }
    }, [currentClient]);

    useEffect(() => {
        if (selected) {
            setResults([]);
            return;
        }

        const timer = setTimeout(() => {
            if (query.length > 0) {
                setLoading(true);
                fetch(buildApiUrl(`/clients/search?q=${encodeURIComponent(query)}`), {
                    credentials: 'include',
                })
                    .then(res => res.json())
                    .then(data => {
                        setResults(Array.isArray(data) ? data : []);
                        setLoading(false);
                    })
                    .catch(() => {
                        setResults([]);
                        setLoading(false);
                    });
            } else {
                setResults([]);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [query, selected]);

    const handleSelect = (client: Client) => {
        setSelected(client);
        setQuery(client.rag_soc);
        setResults([]);
        onClientChange(client);
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setQuery(e.target.value);

        if (selected) {
            setSelected(null);
            onClientChange(null);
        }
    };

    return (
        <div className={`w-full relative ${isOverlay ? 'pr-14' : ''}`}>
            <div className="relative w-full">
                {isOverlay && (
                    <label className="absolute -top-2 left-3 bg-white px-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest z-10 pointer-events-none">
                        Identifica Cliente
                    </label>
                )}

                <div className="relative flex items-center w-full">
                    <input
                        type="text"
                        value={query}
                        onChange={handleInputChange}
                        onFocus={() => {
                            if (query.length > 0 && !selected) {
                                setLoading(true);
                                fetch(buildApiUrl(`/clients/search?q=${encodeURIComponent(query)}`), {
                                    credentials: 'include',
                                })
                                    .then(res => res.json())
                                    .then(data => {
                                        setResults(Array.isArray(data) ? data : []);
                                        setLoading(false);
                                    })
                                    .catch(() => {
                                        setResults([]);
                                        setLoading(false);
                                    });
                            }
                        }}
                        onBlur={() => {
                            setTimeout(() => setResults([]), 200);
                        }}
                        placeholder="Es: Ragione Sociale o Codice..."
                        className={`w-full px-4 py-3.5 rounded-2xl text-[14px] transition-all outline-none border bg-white text-gray-800 placeholder-gray-400 ${selected
                            ? 'border-[hsl(234,60%,50%)] outline-[hsl(234,60%,50%)] ring-[hsl(234,60%,50%)] font-bold text-[hsl(234,60%,30%)] pr-[44px]'
                            : 'border-gray-200 ring-offset-0 hover:border-gray-300 focus:border-[#60a5fa] shadow-sm'
                            }`}
                    />

                    {!selected && !loading && (
                        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                            <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                    )}

                    {loading && (
                        <div className="absolute right-4 top-1/2 -translate-y-1/2">
                            <div className="w-4 h-4 border-2 border-transparent border-t-[#3b82f6] rounded-full animate-spin"></div>
                        </div>
                    )}
                </div>
                {results.length > 0 && !selected && (
                    <div className="absolute w-full mt-2 bg-white rounded-[16px] overflow-hidden shadow-[0_4px_24px_rgba(0,0,0,0.12)] z-[250] border border-gray-100 flex flex-col">
                        <div className="max-h-[220px] overflow-y-auto divide-y divide-[#f8fafc] pr-1 styled-scroll">
                            {results.map((c) => (
                                <div
                                    key={c.cod_cli}
                                    onMouseDown={() => handleSelect(c)}
                                    className="px-5 py-4 hover:bg-gray-50 cursor-pointer flex justify-between items-center transition-colors"
                                >
                                    <span className="text-[15px] font-medium text-slate-700">
                                        {c.rag_soc.toUpperCase()}
                                    </span>
                                    <span className="ml-3 text-[12px] font-mono bg-[#f1f5f9] px-[10px] py-[4px] rounded-[6px] text-gray-500 shrink-0">
                                        {c.cod_cli}
                                    </span>
                                </div>
                            ))}
                        </div>
                        <style jsx>{`
                          .styled-scroll::-webkit-scrollbar {
                            width: 6px;
                          }
                          .styled-scroll::-webkit-scrollbar-track {
                            background: transparent;
                            margin-top: 8px;
                            margin-bottom: 8px;
                          }
                          .styled-scroll::-webkit-scrollbar-thumb {
                            background: #64748b; /* Il grigio scuro visibile nel PoC */
                            border-radius: 10px;
                          }
                          .styled-scroll::-webkit-scrollbar-thumb:hover {
                            background: #475569;
                          }
                        `}</style>
                    </div>
                )}
            </div>
        </div>
    );
}
