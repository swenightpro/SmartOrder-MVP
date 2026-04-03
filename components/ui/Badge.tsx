interface BadgeProps {
    children: React.ReactNode;
    variant?: 'default' | 'ai' | 'confidence-high' | 'confidence-mid' | 'confidence-low' | 'count';
    className?: string;
    title?: string;
}

const variantClasses: Record<string, string> = {
    default: 'text-[10px] bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] border border-[hsl(234,60%,85%)] px-2 py-0.5 rounded-full font-bold',
    ai: 'text-[8px] font-bold text-violet-500 bg-violet-50 border border-violet-200 px-1 py-0.5 rounded leading-none',
    'confidence-high': 'text-[9px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-200 px-1 py-0.5 rounded',
    'confidence-mid': 'text-[9px] font-bold text-amber-600 bg-amber-50 border border-amber-200 px-1 py-0.5 rounded',
    'confidence-low': 'text-[9px] font-bold text-red-600 bg-red-50 border border-red-200 px-1 py-0.5 rounded',
    count: 'text-[10px] bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] px-2 py-0.5 rounded-full font-bold',
};

export default function Badge({ children, variant = 'default', className = '', title }: BadgeProps) {
    return (
        <span className={`${variantClasses[variant] || variantClasses.default} ${className}`} title={title}>
            {children}
        </span>
    );
}

/** Helper: ritorna il variant del badge confidence in base alla percentuale */
export function confidenceVariant(confidence: number | null | undefined): 'confidence-high' | 'confidence-mid' | 'confidence-low' | null {
    if (confidence == null) return null;
    const pct = Math.round(confidence * 100);
    if (pct >= 80) return 'confidence-high';
    if (pct >= 50) return 'confidence-mid';
    return 'confidence-low';
}
