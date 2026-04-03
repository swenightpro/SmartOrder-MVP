import FeedbackButtons from './FeedbackButtons';

/** Formattazione markdown semplice per messaggi chat */
export function formatChatMessage(text: string): string {
    if (!text) return "";
    const escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    return escaped
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br />");
}

/** Estrae nomi prodotto in grassetto dal testo */
export function extractBoldProducts(text: string): string[] {
    const matches: string[] = [];
    const regex = /\*\*([^*]+)\*\*/g;
    let match;
    while ((match = regex.exec(text)) !== null) {
        const name = match[1].trim();
        if (name.length > 2 && !name.includes('ordine') && !name.includes('carrello')) {
            matches.push(name);
        }
    }
    return matches;
}

interface ChatMessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
    feedback?: { is_positive: boolean } | null;
    onFeedbackPositive?: () => void;
    onFeedbackNegative?: () => void;
    suggestedProducts?: { name: string; cod_art?: string }[];
    onProductClick?: (codArt: string) => void;
}

export default function ChatMessageBubble({
    role,
    content,
    feedback,
    onFeedbackPositive,
    onFeedbackNegative,
}: ChatMessageBubbleProps) {
    const isUser = role === 'user';

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div className="max-w-[85%]">
                <div
                    className={`px-3 py-2 text-[13px] leading-relaxed shadow-sm rounded-xl ${isUser
                        ? 'bg-gradient-to-br from-[hsl(234,62%,30%)] to-[hsl(234,55%,40%)] text-white rounded-br-sm'
                        : 'bg-white text-gray-700 border border-gray-100 rounded-bl-sm'
                        }`}
                >
                    {isUser ? (
                        content
                    ) : (
                        <span
                            className="break-words [&_strong]:font-semibold"
                            dangerouslySetInnerHTML={{ __html: formatChatMessage(content) }}
                        />
                    )}
                </div>

                {/* Feedback buttons */}
                {!isUser && onFeedbackPositive && onFeedbackNegative && (
                    <FeedbackButtons
                        feedback={feedback}
                        onPositive={onFeedbackPositive}
                        onNegative={onFeedbackNegative}
                    />
                )}
            </div>
        </div>
    );
}
