"use client";

interface ConfidenceBadgeProps {
    confidence: number;
}

const GREEN = 0.80;
const YELLOW = 0.50;

export default function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
    const colorClass =
        confidence >= GREEN
            ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
            : confidence >= YELLOW
            ? 'bg-amber-100 text-amber-700 border-amber-200'
            : 'bg-red-100 text-red-700 border-red-200';

    const label =
        confidence >= GREEN ? 'Alta' : confidence >= YELLOW ? 'Media' : 'Bassa';

    return (
        <span
            className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full border font-medium text-[9px] ml-1 align-middle ${colorClass}`}
            title={`Confidenza: ${Math.round(confidence * 100)}%`}
        >
            ● {label}
        </span>
    );
}
