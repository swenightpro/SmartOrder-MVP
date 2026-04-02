// ============================================================
// components/ui/QuantityStepper.tsx — Stepper numerico riutilizzabile
//
// Componente atomico con pulsanti +/− e campo numerico editabile.
// Usato sia in ProductCard (aggiunta) che in CartItemRow (modifica).
// ============================================================

"use client";

interface QuantityStepperProps {
    value: number;
    onChange: (newValue: number) => void;
    min?: number;
    disabled?: boolean;
    compact?: boolean;
}

export default function QuantityStepper({ value, onChange, min = 1, disabled = false, compact = false }: QuantityStepperProps) {
    const size = compact ? 'w-7 h-7' : 'w-7 h-7';
    const inputSize = compact ? 'w-12 h-7' : 'w-12 h-7';

    return (
        <div className="flex items-center gap-1">
            <button
                onClick={() => onChange(Math.max(min, value - 1))}
                disabled={disabled}
                className={`${size} flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-red-50 hover:border-red-200 hover:text-red-500 transition-all text-sm font-bold disabled:opacity-40`}
            >
                −
            </button>
            <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={value}
                onChange={(e) => {
                    const v = parseInt(e.target.value) || 0;
                    onChange(Math.max(0, v));
                }}
                disabled={disabled}
                className={`${inputSize} text-center border-2 border-gray-200 rounded-lg text-sm font-bold text-gray-800 bg-white outline-none focus:border-[hsl(234,60%,50%)] [appearance:textfield] disabled:opacity-40`}
            />
            <button
                onClick={() => onChange(value + 1)}
                disabled={disabled}
                className={`${size} flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-600 transition-all text-sm font-bold disabled:opacity-40`}
            >
                +
            </button>
        </div>
    );
}
