// ============================================================
// components/ui/ConfidenceRing.tsx — Indicatore ad anello AI confidence
//
// Renderizza un anello SVG circolare che mostra il grado di
// confidence (0.0–1.0) dell'AI nella scelta del prodotto.
// Usa colori semantici: blu per alta, ambra per media, rosso per bassa.
// ============================================================

"use client";

interface ConfidenceRingProps {
    /** Confidence value 0.0–1.0 */
    value: number;
    /** Size in pixels (default 36) */
    size?: number;
}

export default function ConfidenceRing({ value, size = 36 }: ConfidenceRingProps) {
    if (value == null) return null;

    const numValue = Number(value);
    const pct = Math.round(numValue * 100);
    const radius = (size - 6) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - numValue);

    // Color based on confidence level
    const color = pct >= 80
        ? 'hsl(234, 60%, 36%)'  // brand blue — high confidence
        : pct >= 50
            ? 'hsl(38, 92%, 50%)'   // amber — medium
            : 'hsl(0, 72%, 51%)';    // red — low

    const bgColor = pct >= 80
        ? 'hsl(234, 60%, 90%)'
        : pct >= 50
            ? 'hsl(38, 92%, 90%)'
            : 'hsl(0, 72%, 90%)';

    return (
        <div className="relative shrink-0" style={{ width: size, height: size }}>
            <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="transform -rotate-90">
                {/* Background ring */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={bgColor}
                    strokeWidth="4"
                />
                {/* Progress ring */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={color}
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    style={{ transition: 'stroke-dashoffset 0.5s ease' }}
                />
            </svg>
            {/* Center text */}
            <div
                className="absolute inset-0 flex items-center justify-center"
                style={{ color }}
            >
                <span className="font-bold leading-none" style={{ fontSize: size * 0.26 }}>
                    {pct}%
                </span>
            </div>
        </div>
    );
}
