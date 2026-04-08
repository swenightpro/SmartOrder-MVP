"use client";

import ConfidenceBadge from './ConfidenceBadge';

interface QuickAddButtonProps {
    cod_art: string;
    name: string;
    confidence?: number;
    onAdd: (cod_art: string, name: string) => void;
}

export default function QuickAddButton({ cod_art, name, confidence, onAdd }: QuickAddButtonProps) {
    return (
        <button
            onClick={() => onAdd(cod_art, name)}
            className="inline-flex items-center text-xs px-3 py-1.5 rounded-full border border-[hsl(234,60%,70%)] bg-[hsl(234,60%,96%)] text-[hsl(234,60%,30%)] hover:bg-[hsl(234,60%,90%)] hover:border-[hsl(234,60%,60%)] transition-colors font-medium"
        >
            {name}
            {confidence !== undefined && <ConfidenceBadge confidence={confidence} />}
        </button>
    );
}
