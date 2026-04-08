import json
import re
import logging
from dataclasses import dataclass
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)

_WEAK_KEYWORDS = {
    "si", "sì", "ok", "va", "bene", "e", "o", "di", "da", "in", "con",
    "il", "lo", "la", "i", "gli", "le", "un", "una", "uno",
}

_CONFIRMATION_TOKENS = {
    "si", "sì", "ok", "va bene", "va ben", "confermo", "dai", "quello", "quella"
}


@dataclass
class ConfidenceContext:
    """Contesto necessario per calcolare lo score di confidenza."""
    client_id: int
    products: list[dict]          # risultati da _search_products_for_chat
    order_history: list[dict]     # risultati da get_last_orders
    intent: str                   # da ProductSearchParams.intent
    user_message: str             # messaggio originale (per quantità esplicita)
    search_params_keywords: list[str]  # keywords estratte dal messaggio
    similarity_map: dict[str, float] = None  # mappa cod_art -> similarity (1-distance)
    product_sources: dict[str, str] = None  # cod_art -> match_source ("keyword", "vector", etc.)

    def __post_init__(self):
        if self.similarity_map is None:
            self.similarity_map = {}
        if self.product_sources is None:
            self.product_sources = {}
        # Normalizza i codici articolo già ordinati
        self._ordered_cod_art: set[str] = set()
        for order in self.order_history:
            items = order.get("items") or []
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception:
                    items = []
            for item in (items if isinstance(items, list) else []):
                cod = item.get("cod_art") or item.get("cod_articolo")
                if cod:
                    self._ordered_cod_art.add(cod)

    def was_ordered_before(self, cod_art: str) -> bool:
        return cod_art in self._ordered_cod_art


class ConfidenceScorer:
    """Calcola confidence score basato su segnali strutturali.

    I pesi sono configurabili in config.py (Settings.signal_weights).
    """

    def __init__(self):
        s = get_settings()
        self._weights = s.signal_weights
        self._low_confidence_threshold = s.low_confidence_threshold

    def score(self, context: ConfidenceContext) -> dict[str, float]:
        """Calcola confidence score per ogni prodotto.

        Returns:
            dict mapping cod_art -> confidence score [0.0, 1.0]
        """
        # [CONF] Log del contesto iniziale — chi ha ordinato cosa, keywords, intent
        ordered_codes = list(context._ordered_cod_art)[:20]
        logger.info(
            f"[CONF] context_start | "
            f"client={context.client_id} | intent={context.intent} | "
            f"keywords={context.search_params_keywords} | "
            f"products_count={len(context.products)} | "
            f"history_count={len(context.order_history)} | "
            f"ordered_before={ordered_codes}"
        )

        # [CONF] Log delle sorgenti di match per ogni prodotto
        for p in context.products:
            cod = p.get("cod_art", "")
            src = context.product_sources.get(cod) or p.get("match_source", "unknown")
            sim = context.similarity_map.get(cod)
            sim_str = f"{sim:.3f}" if sim is not None else "N/A"
            logger.debug(
                f"[CONF] product_source | cod_art={cod} | "
                f"source={src} | similarity={sim_str} | "
                f"des_art={p.get('des_art', '')}"
            )

        results = {}
        for product in context.products:
            cod_art = product.get("cod_art", "")
            if not cod_art:
                continue

            # [CONF] Calcola ogni segnale singolo
            s_history = self._signal_history(context, cod_art)
            s_similarity = self._signal_similarity(context, cod_art)
            s_match = self._signal_match_type(context, cod_art, product)
            s_intent = self._signal_intent_type(context.intent)
            s_qty = self._signal_quantity(context)

            # [CONF] Log del calcolo dettagliato con pesi
            confidence = (
                self._weights["history_match"] * s_history
                + self._weights["similarity"] * s_similarity
                + self._weights["match_type"] * s_match
                + self._weights["intent_type"] * s_intent
                + self._weights["quantity_explicit"] * s_qty
            )

            confidence = max(0.0, min(1.0, confidence))
            results[cod_art] = confidence

            logger.info(
                f"[CONF] score_result | "
                f"cod_art={cod_art} | des_art={product.get('des_art', '')} | "
                f"signals={{"
                f"history={s_history:.2f}(w={self._weights['history_match']}), "
                f"similarity={s_similarity:.2f}(w={self._weights['similarity']}), "
                f"match={s_match:.2f}(w={self._weights['match_type']}), "
                f"intent={s_intent:.2f}(w={self._weights['intent_type']}), "
                f"qty={s_qty:.2f}(w={self._weights['quantity_explicit']})"
                f"}} | "
                f"raw_sum={self._weights['history_match']*s_history + self._weights['similarity']*s_similarity + self._weights['match_type']*s_match + self._weights['intent_type']*s_intent + self._weights['quantity_explicit']*s_qty:.3f} | "
                f"confidence={confidence:.3f}"
            )

        # [CONF] Riepilogo finale di tutti i prodotti con confidence scores
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        logger.info(
            f"[CONF] score_summary | client={context.client_id} | intent={context.intent} | "
            f"ranked={[(cod, f'{conf:.3f}') for cod, conf in sorted_results]}"
        )

        return results

    @property
    def low_confidence_threshold(self) -> float:
        """Soglia sotto la quale mostrare warning UX."""
        return self._low_confidence_threshold

    # -------------------------------------------------------------------------
    # Segnali individuali
    # -------------------------------------------------------------------------

    def _signal_history(self, context: ConfidenceContext, cod_art: str) -> float:
        """Segnale storico ordini: 1.0 se il cliente lo ha già ordinato, 0.5 altrimenti."""
        ordered = context.was_ordered_before(cod_art)
        logger.debug(
            f"[CONF] signal_history | cod_art={cod_art} | "
            f"ordered_before={ordered} | score={'1.0' if ordered else '0.5 (fallback)'}"
        )
        return 1.0 if ordered else 0.5

    def _signal_similarity(self, context: ConfidenceContext, cod_art: str) -> float:
        """Segnale similarity vettoriale: 1-distance, oppure 0.3 base se non disponibile.

        Usa la similarity_map passata da ConversationService (la lista products è già
        strippata del campo similarity prima di arrivare qui). Il fallback a 0.3
        (invece di 0.5) è conservativo: in assenza di embeddings non abbiamo evidenza
        semantica, quindi scoraggiamo l'auto-add piuttosto che rischiare falsi positivi.
        """
        sim = context.similarity_map.get(cod_art)
        if sim is not None:
            score = max(0.0, min(1.0, 1.0 - float(sim)))
            logger.debug(
                f"[CONF] signal_similarity | cod_art={cod_art} | "
                f"cosine_dist={sim:.4f} | 1-dist={1.0-float(sim):.4f} | score={score:.4f}"
            )
            return score
        fallback = 0.55 if context.intent in {"CONFIRMATION", "CLARIFICATION"} else 0.3
        logger.debug(
            f"[CONF] signal_similarity | cod_art={cod_art} | "
            f"cosine_dist=N/A (no embeddings) | score={fallback:.2f} (fallback intent-aware)"
        )
        return fallback

    def _signal_match_type(self, context: ConfidenceContext, cod_art: str, product: dict) -> float:
        """Segnale tipo di match: keyword authoritative > cod_art esatto > keyword match > fuzzy."""
        msg_lower = context.user_message.lower()
        source = context.product_sources.get(cod_art) or product.get("match_source")
        des_art = product.get("des_art", "").lower()

        meaningful_keywords = []
        for kw in context.search_params_keywords:
            kw_norm = (kw or "").strip().lower()
            if not kw_norm:
                continue
            if kw_norm in _WEAK_KEYWORDS:
                continue
            if len(kw_norm) < 3:
                continue
            meaningful_keywords.append(kw_norm)

        # 1. Authoritative keyword match (ILIKE found it) — highest priority
        if source == "keyword":
            logger.debug(
                f"[CONF] signal_match_type | cod_art={cod_art} | des_art={product.get('des_art', '')} | "
                f"source={source} | path=1_authoritative_keyword | score=1.0"
            )
            return 1.0

        # 1b. Code-guided selection: prodotto già selezionato/proposto a monte
        if source == "code":
            logger.debug(
                f"[CONF] signal_match_type | cod_art={cod_art} | des_art={product.get('des_art', '')} | "
                f"source={source} | path=1b_code_guided | score=0.90"
            )
            return 0.9

        # 2. Exact cod_art in message
        if re.search(rf'\b{re.escape(cod_art)}\b', msg_lower, re.IGNORECASE):
            logger.debug(
                f"[CONF] signal_match_type | cod_art={cod_art} | des_art={product.get('des_art', '')} | "
                f"source={source} | path=2_exact_cod_art_in_msg | score=1.0"
            )
            return 1.0

        # 3. Keyword match on des_art
        for kw in meaningful_keywords:
            if kw in des_art or des_art in kw:
                logger.debug(
                    f"[CONF] signal_match_type | cod_art={cod_art} | des_art={product.get('des_art', '')} | "
                    f"source={source} | path=3_des_art_keyword_match | "
                    f"matched_kw='{kw}' in des_art='{des_art[:50]}' | score=0.8"
                )
                return 0.8

        # 4. Keyword contains cod_art
        for kw in meaningful_keywords:
            if re.search(rf'\b{re.escape(kw)}\b', cod_art, re.IGNORECASE):
                logger.debug(
                    f"[CONF] signal_match_type | cod_art={cod_art} | des_art={product.get('des_art', '')} | "
                    f"source={source} | path=4_kw_in_cod_art | "
                    f"matched_kw='{kw}' in cod_art='{cod_art}' | score=0.8"
                )
                return 0.8

        logger.debug(
            f"[CONF] signal_match_type | cod_art={cod_art} | des_art={product.get('des_art', '')} | "
            f"source={source} | path=5_fuzzy_fallback | score=0.5"
        )
        return 0.5  # fuzzy/generico

    def _signal_intent_type(self, intent: str) -> float:
        """Segnale tipo di intent: CONFIRMATION/REORDER più sicuri."""
        high = {"CONFIRMATION", "REORDER"}
        medium = {"SPECIFIC", "EDIT"}
        low = {"ADVICE"}

        if intent in high:
            logger.debug(
                f"[CONF] signal_intent_type | intent={intent} | tier=high(CONFIRMATION/REORDER) | score=1.0"
            )
            return 1.0
        if intent in medium:
            logger.debug(
                f"[CONF] signal_intent_type | intent={intent} | tier=medium(SPECIFIC/EDIT) | score=0.7"
            )
            return 0.7
        if intent in low:
            logger.debug(
                f"[CONF] signal_intent_type | intent={intent} | tier=low(ADVICE) | score=0.5"
            )
            return 0.5
        logger.debug(
            f"[CONF] signal_intent_type | intent={intent} | tier=default | score=0.5"
        )
        return 0.5  # default

    def _signal_quantity(self, context: ConfidenceContext) -> float:
        """Segnale quantità esplicita: se l'utente specifica un numero, più sicuro."""
        explicit_patterns = [
            (r'\b\d+\s*(?:pezzi?|bottiglie?|lattine?|fusti?|confezioni?|pacchi?|u\.?\s*a\.?|unità?|caffe?|birre?|coca|acque?)\b', 'numeric_with_unit'),
            (r'\b(una?|due|tree|tre|quattro|cinque|sei|sette|otto|nove|dieci|mezzo|un)\b[^\n]*?(?:bottiglia|latta|fusto|pacchi|confezione)', 'word_with_unit'),
            (r'\b(una?|due|tree|tre|quattro)\s+caffe\b', 'coffee_quantity'),
            (r'\bmezzo\b', 'half_keyword'),
            (r'\bun\s+chilo\b', 'one_kilo'),
            (r'\buna?\s+(?:bottiglia|latta|pacchi)\b', 'a_bottle_can'),
        ]
        user_message = context.user_message
        msg_lower = user_message.lower()
        for pattern, label in explicit_patterns:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                logger.debug(
                    f"[CONF] signal_quantity | msg='{user_message[:80]}' | "
                    f"matched_pattern={label} | pattern='{pattern}' | score=1.0"
                )
                return 1.0

        # Cerca numeri generici nel messaggio
        if re.search(r'\b\d+\b', user_message):
            logger.debug(
                f"[CONF] signal_quantity | msg='{user_message[:80]}' | "
                f"matched_pattern=generic_number | score=1.0"
            )
            return 1.0

        # Conferme brevi ereditano spesso una quantità già proposta nel turno precedente.
        compact_msg = re.sub(r"\s+", " ", msg_lower).strip()
        has_confirmation_phrase = any(
            re.search(rf"\b{re.escape(tok)}\b", compact_msg)
            for tok in _CONFIRMATION_TOKENS
        )
        if context.intent in {"CONFIRMATION", "CLARIFICATION"} and has_confirmation_phrase:
            logger.debug(
                f"[CONF] signal_quantity | msg='{user_message[:80]}' | "
                f"matched_pattern=short_confirmation_intent | score=0.9"
            )
            return 0.9

        logger.debug(
            f"[CONF] signal_quantity | msg='{user_message[:80]}' | "
            f"matched_pattern=none | score=0.6 (default, qty not explicit)"
        )
        return 0.6  # quantità non specificata, default
