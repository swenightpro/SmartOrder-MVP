// ============================================================
// components/auth/AuthOverlay.tsx — Overlay modale di autenticazione
//
// Schermo a tutto schermo che contiene la logica di routing tra
// LoginForm (utente non autenticato) e UserProfilePanel (utente
// autenticato). Pattern Composite: compone i sotto-componenti auth.
// ============================================================

"use client";
import type { Client } from '@/types';
import LoginForm from './LoginForm';
import UserProfilePanel from './UserProfilePanel';


interface AuthOverlayProps {
  onClientChange: (client: Client | null) => void;
  currentClient?: Client | null;
  onClose?: () => void;
}

export default function AuthOverlay({ onClientChange, currentClient, onClose }: AuthOverlayProps) {
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-gray-100 animate-fade-in text-gray-900">
      <div className="absolute top-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-slate-300/30 blur-3xl pointer-events-none" />
      <div className="absolute bottom-[-15%] left-[-10%] w-[400px] h-[400px] rounded-full bg-slate-200/40 blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md mx-4 animate-scale-in">
        {currentClient && onClose && (
          <button onClick={onClose} className="absolute -top-12 right-0 p-2 text-slate-400 hover:text-slate-700 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}

        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden">
          {!currentClient ? (
            <LoginForm onLogin={(c) => onClientChange(c)} />
          ) : (
            <UserProfilePanel
              client={currentClient}
              onLogout={() => onClientChange(null)}
            />
          )}
        </div>
      </div>
    </div>
  );
}