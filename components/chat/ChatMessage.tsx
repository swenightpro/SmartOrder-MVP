import type { ProductLink } from '@/types';
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

/** Renderizza il contenuto con i nomi prodotto in grassetto sostituiti da link cliccabili */
export function renderProductLinks(content: string, productLinks: ProductLink[]): string {
    if (!productLinks || productLinks.length === 0) {
        return formatChatMessage(content);
    }
    const escaped = content
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    let result = escaped;
    productLinks.forEach(({ name, cod_art }) => {
        const escapedName = name
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
        const safeCodArt = String(cod_art).replace(/"/g, "&quot;");
        const linkHtml = `<a class="product-link cursor-pointer underline text-blue-600" data-product-name="${escapedName}" data-cod-art="${safeCodArt}" title="Clicca per aggiungere al carrello">${escapedName}</a>`;
        result = result.replace(`<strong>${escapedName}</strong>`, linkHtml);
    });
    return result.replace(/\n/g, "<br />");
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
    productLinks?: ProductLink[];
    onProductClick?: (name: string, codArt: string) => void;
}

export function ImageMessageBubble({
    imageData,
    ocrText,
    isOperator = false,
}: {
    imageData: string;
    ocrText?: string;
    isOperator?: boolean;
}) {
    return (
        <div className="flex justify-end">
            <div className="max-w-[70%]">
                <div className="relative rounded-2xl overflow-hidden shadow-sm">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                        src={`data:image/jpeg;base64,${imageData}`}
                        alt="Foto inviata"
                        className="w-full max-h-80 object-contain bg-gray-100"
                        style={{ borderRadius: 'inherit' }}
                    />
                </div>
                {isOperator && ocrText && (
                    <div className="mt-1.5 px-2.5 py-1.5 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-700">
                        <span className="font-semibold">OCR: </span>
                        {ocrText}
                    </div>
                )}
                {!isOperator && (
                    <div className="mt-1 px-2 py-0.5 text-[10px] text-gray-400 text-right">
                        Foto
                    </div>
                )}
            </div>
        </div>
    );
}

export default function ChatMessageBubble({
    role,
    content,
    feedback,
    onFeedbackPositive,
    onFeedbackNegative,
    productLinks,
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
                            dangerouslySetInnerHTML={{ __html: renderProductLinks(content, productLinks || []) }}
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
