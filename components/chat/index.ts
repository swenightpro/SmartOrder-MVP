// ============================================================
// components/chat/index.ts — Barrel export modulo chat
//
// Riesporta ChatPanel, AiStatusDot, FeedbackModal, FeedbackButtons,
// ChatInput e le utility di formatting dal modulo ChatMessage.
// ============================================================

export { default as ChatPanel } from './ChatPanel';
export { default as AiStatusDot } from './AiStatusDot';
export { default as FeedbackModal } from './FeedbackModal';
export { default as FeedbackButtons } from './FeedbackButtons';
export { default as ChatInput } from './ChatInput';
export { formatChatMessage, extractBoldProducts } from './ChatMessage';
