"use client";

interface FeedbackButtonsProps {
    feedback: { is_positive: boolean } | null | undefined;
    onPositive: () => void;
    onNegative: () => void;
}

export default function FeedbackButtons({ feedback, onPositive, onNegative }: FeedbackButtonsProps) {
    return (
        <div className="flex items-center gap-0.5 mt-1.5">
            <button
                onClick={onPositive}
                className={`p-1 rounded-lg transition-colors ${feedback?.is_positive === true ? 'bg-emerald-100 text-emerald-600' : 'text-gray-300 hover:text-emerald-500 hover:bg-emerald-50'}`}
                title="Utile"
            >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                </svg>
            </button>
            <button
                onClick={onNegative}
                className={`p-1 rounded-lg transition-colors ${feedback?.is_positive === false ? 'bg-red-100 text-red-500' : 'text-gray-300 hover:text-red-400 hover:bg-red-50'}`}
                title="Non utile"
            >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                </svg>
            </button>
        </div>
    );
}
