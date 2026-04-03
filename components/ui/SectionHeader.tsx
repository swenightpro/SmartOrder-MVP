interface SectionHeaderProps {
    label: string;
    count?: number;
    countLabel?: string;
}

export default function SectionHeader({ label, count, countLabel }: SectionHeaderProps) {
    return (
        <div className="flex items-center gap-2 mb-3">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{label}</span>
            <div className="flex-1 h-px bg-gray-100" />
            {count !== undefined && (
                <span className="text-[10px] bg-[hsl(234,60%,95%)] text-[hsl(234,60%,36%)] px-2 py-0.5 rounded-full font-bold">
                    {countLabel || count}
                </span>
            )}
        </div>
    );
}
