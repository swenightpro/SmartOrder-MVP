import re
import json
import math
import logging
from typing import IO, Literal, Optional, Tuple

from openai import OpenAI
from pydantic import BaseModel, Field

from config import get_settings
from ports.i_ai_client import IAIClient
from ports.i_session_manager import ISessionManager
from services.sse_broadcaster import OPERATOR_CHANNEL
from services.confidence_scorer import ConfidenceScorer, ConfidenceContext
from adapters.postgres_adapter import PostgresAdapter

logger = logging.getLogger(__name__)

_UNIT_WORDS = {
    "bottiglia", "bottiglie", "lattina", "lattine", "fusto", "fusti",
    "confezione", "confezioni", "pacco", "pacchi", "cassa", "casse",
    "cartone", "cartoni", "collo", "colli", "pezzo", "pezzi",
    "unita", "unità", "kg", "etto", "grammi", "litro", "litri", "ml", "chilo",
}

_GENERIC_STOPWORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "una", "uno",
    "di", "del", "dello", "della", "dei", "degli", "delle",
    "a", "ad", "al", "allo", "alla", "ai", "agli", "alle",
    "da", "dal", "dallo", "dalla", "dai", "dagli", "dalle",
    "in", "con", "su", "per", "tra", "fra", "e", "o",
    "mi", "ti", "ci", "vi", "dammi", "aggiungi", "voglio", "prendo", "vorrei",
    "si", "sì", "ok", "va", "bene",
}

_GREETING_WORDS = {
    "ciao", "salve", "buongiorno", "buonasera", "buondi", "ehi", "hey", "hola",
}

_AFFIRMATIVE_WORDS = {
    "si", "sì", "ok", "confermo", "perfetto", "yes", "certo", "va", "bene",
}


# ---------------------------------------------------------------------------
# Pydantic models — structured output OpenAI
# ---------------------------------------------------------------------------

class ProductSearchParams(BaseModel):
    intent: str = "SPECIFIC"
    keywords: list[str] = Field(default_factory=list)
    expanded_categories: list[str] = Field(default_factory=list)
    limit: int = 10


class IntentItem(BaseModel):
    intent: Literal["ORDER", "CLARIFICATION", "ADVICE", "CONFIRMATION", "CART_EDIT", "REORDER"]
    keywords: list[str] = Field(default_factory=list)
    reference: str = ""   # descrizione leggibile di cosa riguarda l'intent


class MultiIntentClassification(BaseModel):
    intents: list[IntentItem] = Field(default_factory=list)


class ProductItem(BaseModel):
    cod_art: str
    quantity: float = 1
    confidence: float = 0.9


class CartEdit(BaseModel):
    cart_item_id: int
    action: str                    # "remove" | "set_quantity" | "reduce_by"
    new_quantity: Optional[float] = None
    reduce_by: Optional[float] = None  # alternativa a set_quantity: sottrai N dalla qty attuale


class BusinessDecisionResponse(BaseModel):
    message: str = ""
    product_items: list[ProductItem] = Field(default_factory=list)
    order_confirmed: bool = False
    cart_edits: list[CartEdit] = Field(default_factory=list)
    edit_confirmed: bool = False


# ---------------------------------------------------------------------------
# Metadata schema salvato su ogni messaggio AI
# ---------------------------------------------------------------------------

def _build_ai_metadata(
    intents: list[str],
    action: str,
    products_proposed: list[dict],
    products_added: list[dict],
    question_asked: Optional[str] = None,
) -> dict:
    """Costruisce il dizionario metadata da serializzare su chat_messages."""
    meta: dict = {
        "intents": intents,
        "action": action,
        # action ∈ {ORDER_ADDED, PROPOSED, ASKED_CLARIFICATION,
        #            ASKED_CONFIRMATION, UNIT_CONVERSION_PROPOSED,
        #            EDIT_APPLIED, ADVICE_GIVEN, REORDER_ADDED}
    }
    if products_proposed:
        meta["products_proposed"] = products_proposed
    if products_added:
        meta["products_added"] = products_added
    if question_asked:
        meta["question_asked"] = question_asked
    return meta


class ConversationService:
    """Servizio applicativo per il flusso conversazionale."""

    def __init__(self, db: PostgresAdapter, ai_client: IAIClient, broadcaster=None):
        self._db = db
        self._ai_client = ai_client
        self._broadcaster = broadcaster
        self._scorer = ConfidenceScorer()
        self._last_similarity_map: dict[str, float] = {}
        s = get_settings()
        self._openai = OpenAI(api_key=s.openai_api_key)
        self._model_fast = s.ai_model_mini
        self._model_smart = s.ai_model

    # =======================================================================
    # Use cases delegati
    # =======================================================================

    def get_active_session(self, user_id: int) -> Optional[dict]:
        return self._db.get_active_session(user_id)

    def create_session(self, user_id: int) -> dict:
        return self._db.create_session(user_id)

    def get_messages(self, session_id: int) -> list[dict]:
        rows = self._db.get_messages(session_id)
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
            if r.get("metadata") and isinstance(r["metadata"], str):
                try:
                    r["metadata"] = json.loads(r["metadata"])
                except Exception:
                    pass
        return rows

    def get_messages_for_user(self, session_id: int, user_id: int) -> list[dict]:
        rows = self._db.get_messages_with_user_feedback(session_id, user_id)
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
            if r.get("metadata") and isinstance(r["metadata"], str):
                try:
                    r["metadata"] = json.loads(r["metadata"])
                except Exception:
                    pass
        return rows

    async def transcribe_audio(self, audio_file: IO[bytes], filename: str) -> str:
        return await self._ai_client.transcribe_audio(audio_file, filename)

    def save_message_to_session(self, session_id: int, sender: str, content: str) -> int:
        return self._db.save_message(session_id, sender, content)

    # =======================================================================
    # Chat AI — Orchestrazione principale
    # =======================================================================

    async def handle_message(
        self,
        message: str,
        client_id: int,
        session_id: Optional[int] = None,
        # history è accettato per backward-compat (chat_image) ma IGNORATO:
        # il backend legge sempre dal DB.
        history: Optional[list[dict]] = None,
        pending_cart_edits: Optional[list] = None,
    ) -> dict:
        logger.info(f"[MSG] start | client={client_id} | session={session_id} | msg='{message}'")

        # ---------------------------------------------------------------
        # 1. LOAD CONTEXT dal DB
        # ---------------------------------------------------------------
        full_history = self._load_history_from_db(session_id)
        cart = self._db.get_cart_by_client(client_id, session_id)
        order_history = self._db.get_last_orders(client_id, limit=15)

        # ---------------------------------------------------------------
        # Shortcut: "il solito" — gestito prima dell'intent classification
        # ---------------------------------------------------------------
        message_lower = message.lower().strip()
        usual_phrases = [
            "il solito", "come sempre", "quello di prima", "lo stesso", "come al solito",
            "come l'altra volta", "l'ultimo", "ultimo ordinato", "l'ultima volta"
        ]
        if any(phrase in message_lower for phrase in usual_phrases):
            result = self._handle_usual_request(client_id)
            if session_id:
                user_msg_id = self._db.save_message(session_id, "user", message)
                ai_msg_id = self._db.save_message(
                    session_id, "ai", result.get("message", ""),
                    json.dumps(_build_ai_metadata(
                        intents=["REORDER"],
                        action="REORDER_ADDED" if result.get("order_confirmed") else "PROPOSED",
                        products_proposed=[],
                        products_added=[
                            {"cod_art": it["cod_art"], "quantity": it["quantity"]}
                            for it in (result.get("product_items") or [])
                        ],
                    ))
                )
                result["user_message_id"] = user_msg_id
                result["ai_message_id"] = ai_msg_id
                await self._emit_messages(session_id, user_msg_id, message, ai_msg_id, result["message"])
            return result

        # Shortcut: saluti/conversazione leggera — non avviare ricerca prodotti.
        if self._is_greeting_message(message):
            greet_msg = "Ciao! Dimmi pure cosa vuoi ordinare."
            return await self._save_and_return(
                session_id,
                message,
                greet_msg,
                {
                    "success": True,
                    "response": greet_msg,
                    "message": greet_msg,
                    "order_confirmed": False,
                    "product_items": None,
                    "cart_edits": None,
                    "edit_confirmed": False,
                },
                intents=["ADVICE"],
                action="PROPOSED",
            )

        # ---------------------------------------------------------------
        # 2. CLASSIFY INTENTS (mini, con contesto)
        # ---------------------------------------------------------------
        classification = self._classify_intents(message, full_history, cart)
        intents = classification.intents or [IntentItem(intent="ORDER", keywords=[message])]
        logger.info(f"[MSG] intents={[(i.intent, i.keywords) for i in intents]}")

        primary_intent = intents[0].intent
        explicit_multi_order = self._is_explicit_multi_product_order(primary_intent, intents[0], message)

        # CART_EDIT senza carrello → risposta diretta
        if all(i.intent == "CART_EDIT" for i in intents) and not cart:
            empty_msg = "Il carrello è vuoto, non c'è nulla da modificare. Vuoi aggiungere qualcosa?"
            return await self._save_and_return(session_id, message, empty_msg, {
                "success": True, "response": empty_msg, "message": empty_msg,
                "order_confirmed": False, "cart_edits": None, "edit_confirmed": False,
            }, intents=["CART_EDIT"], action="PROPOSED")

        # ---------------------------------------------------------------
        # 3. BUILD INTENT CONTEXTS (no AI)
        # ---------------------------------------------------------------
        intent_contexts = [
            self._build_intent_context(
                intent_item,
                client_id,
                full_history,
                cart,
                user_message=message,
            )
            for intent_item in intents
        ]

        # Pool prodotti unificato per confidence scorer + hallucination recovery
        all_products: list[dict] = []
        seen_codes: set[str] = set()
        for ctx in intent_contexts:
            for p in ctx.get("products", []):
                if p.get("cod_art") not in seen_codes:
                    all_products.append(p)
                    seen_codes.add(p["cod_art"])

        # ---------------------------------------------------------------
        # 4. BUSINESS DECISION (smart, singola call)
        # ---------------------------------------------------------------
        decision = self._make_business_decision(
            user_message=message,
            intent_contexts=intent_contexts,
            full_history=full_history,
            cart=cart,
            order_history=order_history,
            pending_cart_edits=pending_cart_edits,
        )

        # Intent primario per le regole di post-processing
        raw_items = list(decision.product_items or [])
        order_confirmed = decision.order_confirmed

        # Override intent ADVICE → non aggiungere mai
        if primary_intent == "ADVICE":
            raw_items = []
            order_confirmed = False

        # Override intent CART_EDIT → gestito tramite cart_edits, non product_items
        if primary_intent == "CART_EDIT":
            raw_items = []
            order_confirmed = False

        # ---------------------------------------------------------------
        # 5. POST-PROCESS
        # ---------------------------------------------------------------

        # 5a. Hallucination recovery (invariato dalla versione precedente)
        raw_items, all_products, decision = self._recover_from_hallucinations(
            decision, raw_items, all_products, client_id
        )

        filtered_items = [it for it in raw_items if it.cod_art in {p["cod_art"] for p in all_products}]
        dropped = [it.cod_art for it in raw_items if it.cod_art not in {p["cod_art"] for p in all_products}]
        if dropped:
            logger.warning(f"Prodotti rimossi (non in catalogo): {dropped}")

        order_confirmed = order_confirmed and len(filtered_items) > 0

        # 5b. Coherence check (ORDER) e fallback CLARIFICATION
        if primary_intent == "ORDER" and filtered_items:
            filtered_items, order_confirmed = self._ensure_message_output_coherence(
                decision.message or "",
                all_products,
                filtered_items,
                order_confirmed,
                user_intent_confirmation=False,
                run_coherence_check=True,
                client_id=client_id,
            )

        # 5b-bis. CLARIFICATION fallback: GPT-4.1 a volte scrive "Ho aggiunto X" nel message
        # ma lascia product_items=[] nel JSON. Se il messaggio dice "aggiunto" e non ci sono
        # item, prova a estrarre il prodotto dal testo.
        if primary_intent == "CLARIFICATION" and not filtered_items and all_products:
            msg_lower = (decision.message or "").lower()
            if any(w in msg_lower for w in ["aggiunto", "ho aggiunto", "inserito", "aggiungo"]):
                extracted, _ = self._ensure_message_output_coherence(
                    decision.message or "",
                    all_products,
                    [],
                    True,   # forziamo order_confirmed=True per tentare l'estrazione
                    user_intent_confirmation=True,
                    run_coherence_check=False,
                    client_id=client_id,
                )
                if extracted:
                    filtered_items = extracted
                    order_confirmed = True
                    logger.info(f"[CLARIF] fallback extraction: {[it.cod_art for it in extracted]}")

        # 5b-ter. CLARIFICATION multi-prodotto con risposta confermativa breve:
        # conferma TUTTI i prodotti pendenti (non solo il primo) con quantità note.
        clarification_ctx = next(
            (ctx for ctx in intent_contexts if ctx.get("intent") == "CLARIFICATION"),
            None,
        )
        if (
            primary_intent == "CLARIFICATION"
            and clarification_ctx
            and self._is_confirmation_like_reply(message)
            and not self._extract_meaningful_tokens(message)
        ):
            pending_products = clarification_ctx.get("products") or []
            if len([p for p in pending_products if p.get("cod_art")]) >= 2:
                last_ai_content = next(
                    (
                        (msg.get("content") or "")
                        for msg in reversed(full_history)
                        if msg.get("sender") == "ai"
                    ),
                    "",
                )
                qty_from_prompt = self._extract_pending_quantities_from_ai_message(
                    last_ai_content,
                    pending_products,
                )

                # Safety gate: forza multi-add solo con evidenza esplicita di quantità
                # per almeno 2 prodotti nel messaggio AI precedente.
                explicit_qty_codes = {
                    p.get("cod_art")
                    for p in pending_products
                    if p.get("cod_art") and p.get("cod_art") in qty_from_prompt
                }
                if len(explicit_qty_codes) < 2:
                    logger.warning(
                        "[CLARIF] skip forced multi-product confirmation: insufficient explicit multi-qty evidence (%d)",
                        len(explicit_qty_codes),
                    )
                    pending_products = []

                forced_items: list[ProductItem] = []
                seen_codes: set[str] = set()
                for p in pending_products:
                    cod = p.get("cod_art")
                    if not cod or cod in seen_codes:
                        continue
                    qty = qty_from_prompt.get(cod)
                    if qty is None:
                        qty = self._coerce_positive_quantity(p.get("quantity"), 1.0)
                    forced_items.append(ProductItem(cod_art=cod, quantity=qty, confidence=0.95))
                    seen_codes.add(cod)

                if forced_items:
                    filtered_items = forced_items
                    order_confirmed = True
                    explicit_multi_order = True

                    lines = []
                    for it in forced_items:
                        name = next(
                            (
                                p.get("des_art", "")
                                for p in all_products
                                if p.get("cod_art") == it.cod_art
                            ),
                            it.cod_art,
                        )
                        qty_txt = (
                            str(int(it.quantity))
                            if float(it.quantity).is_integer()
                            else str(it.quantity).replace(".", ",")
                        )
                        lines.append(f"- **{name}** ({qty_txt})")

                    if lines:
                        decision.message = "Perfetto, ho aggiunto al carrello:\n" + "\n".join(lines)
                    logger.info(
                        "[CLARIF] multi-product confirmation forced: %s",
                        [(it.cod_art, it.quantity) for it in forced_items],
                    )

        # 5c. Confidence scorer
        if filtered_items and all_products:
            product_sources = {
                p["cod_art"]: p.get("match_source", "")
                for p in all_products if p.get("cod_art")
            }
            scorer_context = ConfidenceContext(
                client_id=client_id,
                products=all_products,
                order_history=order_history,
                intent=primary_intent,
                user_message=message,
                search_params_keywords=intents[0].keywords or [],
                similarity_map=self._last_similarity_map,
                product_sources=product_sources,
            )
            confidence_scores = self._scorer.score(scorer_context)
            for item in filtered_items:
                item.confidence = confidence_scores.get(item.cod_art, 0.5)
            logger.info(f"[CONF] {[(it.cod_art, f'{it.confidence:.3f}') for it in filtered_items]}")

        # 5d. Gap threshold (ORDER / CONFIRMATION / REORDER)
        gap_ambiguity = False
        s = get_settings()
        GAP_THRESHOLD = s.gap_confidence_threshold
        if (
            primary_intent in ("ORDER", "CONFIRMATION", "REORDER")
            and len(filtered_items) >= 2
            and not (primary_intent == "ORDER" and explicit_multi_order)
        ):
            sorted_items = sorted(filtered_items, key=lambda x: x.confidence, reverse=True)
            top1, top2 = sorted_items[0], sorted_items[1]
            gap = top1.confidence - top2.confidence
            if gap < GAP_THRESHOLD:
                order_confirmed = False
                gap_ambiguity = True
                names = [
                    next((p.get("des_art", "") for p in all_products if p["cod_art"] == it.cod_art), it.cod_art)
                    for it in [top1, top2]
                ]
                decision.message = (
                    f"Non sono sicuro di quale intendi. "
                    f"Propongo: **{names[0]}** o **{names[1]}**. Quale preferisci?"
                )
                logger.info(f"[CONF] gap={gap:.3f} < {GAP_THRESHOLD} → disambiguazione")
        elif primary_intent == "ORDER" and explicit_multi_order and len(filtered_items) >= 2:
            logger.info("[CONF] explicit multi-product ORDER detected → skip global gap disambiguation")

        # 5e. Multi-product pruning (ORDER con 2+ prodotti → tieni solo il migliore)
        if (
            primary_intent == "ORDER"
            and len(filtered_items) > 1
            and not gap_ambiguity
            and not explicit_multi_order
        ):
            max_conf = max(it.confidence for it in filtered_items)
            best = [it for it in filtered_items if abs(it.confidence - max_conf) < 1e-9]
            if len(best) == 1:
                filtered_items = best
            else:
                order_confirmed = False  # pareggio → proponi

        # 5f. Confidence gate: se tutto sotto 0.50 → non aggiungere
        if primary_intent in ("ORDER", "CONFIRMATION") and filtered_items:
            if all(it.confidence < 0.50 for it in filtered_items):
                order_confirmed = False
                product_names = [
                    next((p.get("des_art", "") for p in all_products if p["cod_art"] == it.cod_art), it.cod_art)
                    for it in filtered_items
                ]
                decision.message = (
                    f"Non sono sicuro di quale prodotto intendi. "
                    f"Propongo: {', '.join(f'**{n}**' for n in product_names)}. "
                    f"Scegli quello giusto per aggiungerlo al carrello."
                )

        # 5g. Validazione a posteriori unità di misura (quantity > 0)
        if filtered_items and order_confirmed:
            filtered_items = [it for it in filtered_items if it.quantity > 0]
            if not filtered_items:
                order_confirmed = False

        # 5h. Validazione programmatica CART_EDIT
        cart_edits_out = None
        edit_confirmed_out = decision.edit_confirmed
        if decision.cart_edits:
            validated_edits, edit_issues = self._validate_cart_edits(decision.cart_edits, cart)
            cart_edits_out = [e.model_dump() for e in validated_edits]
            if edit_issues:
                issue_note = " ".join(edit_issues)
                decision.message = (decision.message + " " + issue_note).strip() if decision.message else issue_note
                if not validated_edits:
                    edit_confirmed_out = False

        # ---------------------------------------------------------------
        # 6. Determina action per metadata
        # ---------------------------------------------------------------
        action = self._determine_action(
            primary_intent=primary_intent,
            order_confirmed=order_confirmed,
            filtered_items=filtered_items,
            decision=decision,
            gap_ambiguity=gap_ambiguity,
        )

        # ---------------------------------------------------------------
        # Prepara output prodotti
        # ---------------------------------------------------------------
        product_items_out = None if gap_ambiguity else (
            [{"cod_art": it.cod_art, "quantity": it.quantity} for it in filtered_items]
            if filtered_items else None
        )
        # product_codes: solo quando l'ordine è confermato (usato dal frontend per il cart add)
        product_codes_out = (
            [it.cod_art for it in filtered_items]
            if filtered_items and order_confirmed and not gap_ambiguity
            else None
        )

        # product_codes_with_names: rimosso — i bottoni di proposta erano fonte di errori
        product_codes_with_names = None

        # confidence: solo per gli item confermati (usato per il ConfidenceRing nel carrello)
        product_confidences_out: Optional[dict] = (
            {it.cod_art: it.confidence for it in filtered_items} if filtered_items else None
        )

        # ---------------------------------------------------------------
        # 6. SAVE + SSE
        # ---------------------------------------------------------------
        products_added = [
            {"cod_art": it.cod_art, "quantity": it.quantity}
            for it in filtered_items
        ] if order_confirmed and filtered_items else []

        # Capisce se l'AI ha fatto una domanda aperta (supporta domande multiple)
        question_lines = self._extract_questions_from_message(decision.message or "")
        question_asked = "\n".join(question_lines) if question_lines else None

        # products_proposed: prodotti candidati per il turno successivo.
        # Nota: anche quando order_confirmed=True può rimanere una domanda aperta
        # (es. aggiunto il primo articolo + richiesta di scelta sul secondo).
        products_proposed = []
        selected_codes = {it.cod_art for it in filtered_items}
        pending_candidates = [
            p for p in all_products
            if p.get("cod_art") and p.get("cod_art") not in selected_codes
        ]
        pending_qty_map = self._extract_pending_quantities_from_ai_message(
            decision.message or "",
            pending_candidates,
        )

        # 1) Per CLARIFICATION/CONFIRMATION usa i prodotti dell'intent context
        for ctx in intent_contexts:
            if ctx["intent"] in ("CLARIFICATION", "CONFIRMATION") and ctx.get("products"):
                products_proposed = [
                    {
                        "cod_art": p.get("cod_art", ""),
                        "des_art": p.get("des_art", ""),
                        "quantity": self._coerce_positive_quantity(p.get("quantity"), 1.0),
                    }
                    for p in ctx["products"]
                ]
                break

        # 2) Se c'è una domanda aperta, proponi i candidati pendenti pertinenti alla domanda
        if not products_proposed and question_asked and pending_candidates:
            q_tokens = self._extract_meaningful_tokens(" ".join(question_lines) if question_lines else question_asked)
            user_tokens = self._extract_meaningful_tokens(message)
            match_tokens = q_tokens or user_tokens
            question_matched = [
                p for p in pending_candidates
                if self._keywords_match_product(match_tokens, p)
            ] if match_tokens else []

            # Se la domanda e' solo quantitativa (es. "Posso ordinare 6 cartoni?")
            # usa il prodotto citato nella risposta AI, non il fallback sui primi candidati.
            if not question_matched and decision.message:
                bold_names = self._extract_product_like_bold_names(decision.message)
                if bold_names:
                    question_matched = self._match_products_from_names(
                        bold_names,
                        pending_candidates,
                        client_id,
                    )

            source = question_matched if question_matched else pending_candidates
            products_proposed = [
                {
                    "cod_art": p.get("cod_art", ""),
                    "des_art": p.get("des_art", ""),
                    "quantity": pending_qty_map.get(
                        p.get("cod_art", ""),
                        self._coerce_positive_quantity(p.get("quantity"), 1.0),
                    ),
                }
                for p in source[:6]
            ]

        # 3) Fallback classico: solo quando l'ordine non è confermato
        if not products_proposed and not order_confirmed:
            if filtered_items:
                products_proposed = [
                    {
                        "cod_art": it.cod_art,
                        "des_art": next(
                            (p.get("des_art", "") for p in all_products if p["cod_art"] == it.cod_art), ""
                        ),
                        "quantity": it.quantity,
                    }
                    for it in filtered_items[:6]
                ]
            elif all_products:
                fallback_source = all_products
                if question_asked:
                    q_tokens = self._extract_meaningful_tokens(
                        " ".join(question_lines) if question_lines else question_asked
                    )
                    user_tokens = self._extract_meaningful_tokens(message)
                    match_tokens = q_tokens or user_tokens
                    if match_tokens:
                        fallback_source = [
                            p for p in all_products
                            if self._keywords_match_product(match_tokens, p)
                        ]

                products_proposed = [
                    {"cod_art": p["cod_art"], "des_art": p.get("des_art", ""), "quantity": 1}
                    for p in fallback_source[:6]
                ]

        # Se non abbiamo confermato l'ordine, evita messaggi che dichiarano falsamente
        # l'aggiunta al carrello.
        if not order_confirmed:
            decision.message = self._rewrite_false_addition_message(
                decision.message or "",
                products_proposed,
            )
            question_lines = self._extract_questions_from_message(decision.message or "")
            question_asked = "\n".join(question_lines) if question_lines else None

        ai_metadata = _build_ai_metadata(
            intents=[i.intent for i in intents],
            action=action,
            products_proposed=products_proposed,
            products_added=products_added,
            question_asked=question_asked,
        )

        user_message_id = None
        ai_message_id = None
        if session_id:
            user_message_id = self._db.save_message(session_id, "user", message)
            ai_message_id = self._db.save_message(
                session_id, "ai", decision.message or "",
                json.dumps(ai_metadata)
            )
            await self._emit_messages(
                session_id, user_message_id, message, ai_message_id, decision.message or "",
                has_cart_changes=bool(filtered_items and order_confirmed) or bool(decision.cart_edits),
            )

        logger.info(
            f"[MSG] done | intents={[i.intent for i in intents]} | action={action} | "
            f"order_confirmed={order_confirmed} | "
            f"items={[(it.cod_art, it.quantity) for it in filtered_items]}"
        )

        return {
            "success": True,
            "response": decision.message,
            "message": decision.message,
            "user_message_id": user_message_id,
            "ai_message_id": ai_message_id,
            "product_items": product_items_out,
            "product_codes": product_codes_out,
            "product_codes_with_names": product_codes_with_names,
            "product_confidences": product_confidences_out,
            "intent": primary_intent,
            "order_confirmed": order_confirmed,
            "cart_edits": cart_edits_out,
            "edit_confirmed": edit_confirmed_out,
            "disambiguation_candidates": None,  # gestita via gap_ambiguity nel messaggio
        }

    # =======================================================================
    # Private — Load history dal DB
    # =======================================================================

    def _load_history_from_db(self, session_id: Optional[int]) -> list[dict]:
        """Carica storia completa dal DB con metadata deserializzati."""
        if not session_id:
            return []
        rows = self._db.get_messages(session_id)
        result = []
        for r in rows:
            entry = dict(r)
            entry["created_at"] = str(entry.get("created_at", ""))
            # image_data è già base64 da get_messages — rimuovi per non appesantire il contesto AI
            entry.pop("image_data", None)
            # Deserializza metadata se stringa
            if entry.get("metadata") and isinstance(entry["metadata"], str):
                try:
                    entry["metadata"] = json.loads(entry["metadata"])
                except Exception:
                    entry["metadata"] = {}
            elif not entry.get("metadata"):
                entry["metadata"] = {}
            result.append(entry)
        return result

    def _get_last_ai_metadata(self, full_history: list[dict]) -> dict:
        """Ritorna il metadata dell'ultimo messaggio AI (sender='ai')."""
        for msg in reversed(full_history):
            if msg.get("sender") == "ai":
                return msg.get("metadata") or {}
        return {}

    # =======================================================================
    # Private — Intent classification con contesto
    # =======================================================================

    def _classify_intents(
        self,
        message: str,
        full_history: list[dict],
        cart: list[dict],
    ) -> MultiIntentClassification:
        """Classifica TUTTI gli intenti nel messaggio usando contesto completo."""
        try:
            # Ultimi 10 messaggi per il classifier (non servono tutti i 50)
            recent = full_history[-10:] if full_history else []
            history_text = self._format_history_for_classifier(recent)
            cart_text = self._format_cart_for_classifier(cart)

            # Legge metadata dell'ultimo msg AI per guidare la disambiguazione
            last_ai_meta = self._get_last_ai_metadata(full_history)
            meta_hint = ""
            if last_ai_meta:
                action = last_ai_meta.get("action", "")
                q = last_ai_meta.get("question_asked", "")
                proposed = last_ai_meta.get("products_proposed", [])
                if q and proposed:
                    q_tokens = self._extract_meaningful_tokens(q)
                    if q_tokens:
                        proposed = [
                            p for p in proposed
                            if self._keywords_match_product(q_tokens, p)
                        ]
                proposed_names = ", ".join(p.get("des_art", p.get("cod_art", "")) for p in proposed[:4])
                if action in ("ASKED_CLARIFICATION", "ADVICE_GIVEN"):
                    if proposed_names:
                        meta_hint = (
                            f"\nNOTA: L'ultimo messaggio AI ha proposto/chiesto tra: {proposed_names}. "
                            f"Se il messaggio corrente risponde scegliendo uno di questi → CLARIFICATION."
                        )
                    elif q:
                        meta_hint = (
                            f"\nNOTA: L'ultimo messaggio AI ha fatto la domanda: \"{q}\". "
                            f"Se il messaggio corrente risponde a questa domanda → CLARIFICATION."
                        )
                elif action in ("PROPOSED", "ASKED_CONFIRMATION", "UNIT_CONVERSION_PROPOSED"):
                    if proposed_names:
                        meta_hint = (
                            f"\nNOTA: L'ultimo messaggio AI ha proposto: {proposed_names}. "
                            f"Se il messaggio corrente è una conferma ('sì', 'ok', ecc.) → CONFIRMATION. "
                            f"Se cita o sceglie uno dei prodotti proposti (anche con quantità) → CLARIFICATION."
                        )
                    elif q:
                        meta_hint = (
                            f"\nNOTA: L'ultimo messaggio AI ha fatto la domanda: \"{q}\". "
                            f"Se il messaggio corrente risponde alla domanda → CLARIFICATION."
                        )

            system = f"""Sei un assistente B2B per ordini bar/ristoro. Analizza il messaggio e identifica TUTTI gli intenti presenti nell'ordine in cui appaiono.

INTENTI POSSIBILI:
- ORDER: il cliente vuole aggiungere un nuovo prodotto al carrello (non ancora presente). Formulazioni: "voglio X", "aggiungi X", "prendo X", "dammi X", "2 coca", ecc.
- CLARIFICATION: il cliente sta RISPONDENDO a una domanda che l'AI ha appena fatto, scegliendo tra opzioni già proposte. NON fare nuova ricerca prodotti.
- ADVICE: chiede un consiglio generico ("cosa mi consigli?", "qualcosa di fresco", ecc.)
- CONFIRMATION: conferma esplicita di un'azione proposta ("sì", "ok", "confermo", "va bene", "aggiungila", "la prima", "quella", ecc.)
- CART_EDIT: vuole modificare o rimuovere qualcosa GIÀ A CARRELLO ("togli", "rimuovi", "cambia la quantità", ecc.)
- REORDER: vuole riordinare qualcosa di già ordinato in passato

REGOLE:
- Un messaggio può avere più intent (es. "Aggiungi 2 coca e togli la fanta" → ORDER + CART_EDIT)
- Distingui ORDER da CLARIFICATION guardando se l'AI ha appena fatto una domanda
- "la prima", "quella piccola", "l'altra" dopo una proposta AI → CLARIFICATION (non ORDER)
- Se il messaggio è solo un numero (es. "3") e c'è una proposta AI pendente → CONFIRMATION
- Se il messaggio chiede solo un consiglio generico (es. "qualcosa di fresco", "per l'estate", "cosa mi consigli"), classifica ADVICE anche se contiene verbi come "dammi".
{meta_hint}"""

            user_prompt = f"""Messaggio: "{message}"

Ultimi messaggi:
{history_text}

Carrello attuale:
{cart_text}

Identifica tutti gli intenti nel messaggio."""

            response = self._openai.beta.chat.completions.parse(
                model=self._model_fast,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=MultiIntentClassification,
                #temperature=0.0,
            )
            result = response.choices[0].message.parsed
            result.intents = self._normalize_intents(result.intents or [])
            if not result.intents:
                result.intents = [IntentItem(intent="ORDER", keywords=[message])]
            return result

        except Exception as e:
            logger.error(f"Errore classify_intents: {e}")
            return MultiIntentClassification(intents=[IntentItem(intent="ORDER", keywords=[message])])

    def _format_history_for_classifier(self, recent: list[dict]) -> str:
        """Formatta ultimi messaggi per il classifier (conciso)."""
        lines = []
        for msg in recent:
            sender = msg.get("sender", "")
            role = "Cliente" if sender == "user" else "AI"
            content = msg.get("content") or msg.get("ocr_text") or ""
            if not content:
                continue
            meta = msg.get("metadata") or {}
            meta_str = ""
            if sender == "ai" and meta.get("action"):
                meta_str = f" [action={meta['action']}]"
                if meta.get("question_asked"):
                    q_compact = str(meta["question_asked"]).replace("\n", " | ")
                    meta_str += f" [domanda: {q_compact}]"
                if meta.get("products_proposed"):
                    names = ", ".join(
                        p.get("des_art", p.get("cod_art", ""))
                        for p in meta["products_proposed"][:3]
                    )
                    meta_str += f" [proposti: {names}]"
            lines.append(f"[{role}]{meta_str}: {content[:200]}")
        return "\n".join(lines) if lines else "(nessuno)"

    def _is_generic_order_intent(self, intent_item: IntentItem) -> bool:
        if intent_item.intent != "ORDER":
            return False
        raw = " ".join(intent_item.keywords or []).strip().lower()
        if not raw:
            return True
        meaningful = self._extract_meaningful_tokens(raw)
        return len(meaningful) == 0

    def _normalize_intents(self, intents: list[IntentItem]) -> list[IntentItem]:
        """Rimuove ORDER spurii quando il messaggio è chiaramente ADVICE."""
        if not intents:
            return intents

        has_advice = any(i.intent == "ADVICE" for i in intents)
        if not has_advice:
            return intents

        filtered: list[IntentItem] = []
        dropped = 0
        for i in intents:
            if i.intent == "ORDER" and self._is_generic_order_intent(i):
                dropped += 1
                continue
            filtered.append(i)

        if dropped > 0:
            logger.info(f"Intent normalization: removed {dropped} generic ORDER intent(s) with ADVICE present")

        return filtered or intents

    def _format_cart_for_classifier(self, cart: list[dict]) -> str:
        if not cart:
            return "(carrello vuoto)"
        return "\n".join(
            f"- ID:{c['id']} {c.get('des_art', c['cod_art'])} qta={c['qta']}"
            for c in cart[:10]
        )

    def _is_explicit_multi_product_order(
        self,
        primary_intent: str,
        intent_item: IntentItem,
        user_message: str,
    ) -> bool:
        """Rileva ordini multi-prodotto espliciti (es. più righe con quantità + prodotto).

        Serve per evitare disambiguazioni globali tra prodotti che in realtà sono
        richieste indipendenti nello stesso messaggio.
        """
        if primary_intent != "ORDER":
            return False

        meaningful_keywords = [
            kw for kw in (intent_item.keywords or [])
            if self._extract_meaningful_tokens(kw)
        ]
        if len(meaningful_keywords) >= 2:
            return True

        lines = [ln.strip() for ln in (user_message or "").splitlines() if ln.strip()]
        explicit_lines = 0
        for ln in lines:
            has_qty = bool(re.search(r"\b\d+\b", ln))
            tokens = self._extract_meaningful_tokens(ln)
            if has_qty and len(tokens) >= 2:
                explicit_lines += 1

        return explicit_lines >= 2

    # =======================================================================
    # Private — Build intent context (per ogni intent)
    # =======================================================================

    def _build_intent_context(
        self,
        intent_item: IntentItem,
        client_id: int,
        full_history: list[dict],
        cart: list[dict],
        user_message: str = "",
    ) -> dict:
        """Costruisce il contesto specifico per un singolo intent."""
        intent = intent_item.intent

        if intent == "ORDER":
            params = ProductSearchParams(intent="SPECIFIC", keywords=intent_item.keywords, limit=10)
            products = self._search_products_for_chat(client_id, params)
            products = self._merge_recent_proposed_products(
                products=products,
                keywords=intent_item.keywords,
                client_id=client_id,
                full_history=full_history,
            )
            return {"intent": intent, "products": products, "keywords": intent_item.keywords}

        elif intent == "CLARIFICATION":
            # I prodotti sono quelli proposti dall'AI nel msg precedente
            last_meta = self._get_last_ai_metadata(full_history)
            proposed = last_meta.get("products_proposed", [])
            last_ai_content = next(
                (
                    (msg.get("content") or "")
                    for msg in reversed(full_history)
                    if msg.get("sender") == "ai"
                ),
                "",
            )
            # Arricchisci con dati DB se mancano
            enriched = []
            for p in proposed:
                cod = p.get("cod_art")
                if cod:
                    full = self._db.find_product_by_code(cod, client_id)
                    if full:
                        merged = dict(full)
                        if p.get("quantity") is not None:
                            merged["quantity"] = p.get("quantity")
                        enriched.append(merged)
                    else:
                        enriched.append(p)
                else:
                    enriched.append(p)

            clarification_keywords = [kw for kw in (intent_item.keywords or []) if kw]
            if not clarification_keywords and user_message:
                clarification_keywords = [user_message]
            question_asked = (last_meta.get("question_asked") or "")
            question_segments = self._split_questions_text(question_asked)
            question_text = " ".join(question_segments) if question_segments else question_asked

            # Se la domanda precedente contiene nomi prodotto in chiaro, uniscili al contesto
            # (caso tipico: products_proposed incompleto ma domanda con 2 articoli).
            question_product_names = self._extract_product_like_bold_names(question_text)
            if question_product_names:
                from_question = self._match_products_from_names(
                    question_product_names,
                    enriched,
                    client_id,
                )
                if from_question:
                    merged_by_code: dict[str, dict] = {}
                    for p in enriched + from_question:
                        cod = p.get("cod_art")
                        if cod and cod not in merged_by_code:
                            merged_by_code[cod] = p
                    enriched = list(merged_by_code.values())

            normalized_kw = [kw.strip().lower() for kw in clarification_keywords if kw.strip()]
            confirmation_like = bool(normalized_kw) and all(kw in _AFFIRMATIVE_WORDS for kw in normalized_kw)
            q_lower = question_text.lower()
            asks_quantity = bool(re.search(r"\b(quanti|quante|quantita|quantità)\b", q_lower))
            asks_quantity = asks_quantity or (
                "posso ordinare" in q_lower
                and bool(re.search(r"\b(carton|casse|fusti|bottigl|colli|pezzi)\w*\b", q_lower))
            )
            quantity_only_reply = asks_quantity and (
                self._is_quantity_only_reply(user_message) or confirmation_like
            )

            if clarification_keywords and not quantity_only_reply:
                narrowed = [
                    p for p in enriched
                    if any(self._keywords_match_product([kw], p) for kw in clarification_keywords)
                ]

                if narrowed:
                    enriched = narrowed
                else:
                    # Recovery ampio solo su input semplici; evita derive con messaggi
                    # multi-prodotto/quantita (es. "uliveto quantita 10 e san benedetto 10").
                    allow_broad_recovery = (
                        len(clarification_keywords) <= 1
                        and not any(re.search(r"\d", kw) for kw in clarification_keywords)
                    )
                    if allow_broad_recovery:
                        recovered = self._search_products_for_chat(
                            client_id,
                            ProductSearchParams(intent="SPECIFIC", keywords=clarification_keywords, limit=10),
                        )
                        if recovered:
                            logger.warning(
                                "[CLARIF] metadata options stale/non matching, recovered via keyword search: %s",
                                clarification_keywords,
                            )
                            enriched = recovered

            if quantity_only_reply and enriched:
                # Domanda di sola quantità (es. "quanti cartoni?"): resta ancorato
                # al prodotto già proposto, senza ricerca keyword su numeri.
                allowed_codes = {p.get("cod_art") for p in enriched if p.get("cod_art")}
                bold_names = self._extract_product_like_bold_names(last_ai_content)
                recovered_from_ai_msg_raw = self._match_products_from_names(
                    bold_names,
                    enriched,
                    client_id,
                )
                recovered_from_ai_msg = [
                    p for p in recovered_from_ai_msg_raw if p.get("cod_art") in allowed_codes
                ]

                if recovered_from_ai_msg:
                    enriched = recovered_from_ai_msg
                elif recovered_from_ai_msg_raw:
                    # Metadati proposti stale: usa comunque il prodotto citato nella domanda AI.
                    logger.warning(
                        "[CLARIF] quantity-only reply with stale metadata, using AI-question matched product(s): %s",
                        [p.get("cod_art") for p in recovered_from_ai_msg_raw if p.get("cod_art")],
                    )
                    enriched = recovered_from_ai_msg_raw
                else:
                    in_assort = [p for p in enriched if not p.get("not_in_assortment")]
                    if in_assort:
                        enriched = in_assort

            if confirmation_like and last_ai_content:
                bold_names = self._extract_product_like_bold_names(last_ai_content)
                recovered_from_ai_msg = self._match_products_from_names(
                    bold_names,
                    enriched,
                    client_id,
                )

                if recovered_from_ai_msg:
                    logger.warning(
                        "[CLARIF] recovered options from last AI message content for confirmation-like reply"
                    )
                    enriched = recovered_from_ai_msg
                elif (not clarification_keywords or confirmation_like) and not enriched:
                    # Evita di usare opzioni stale/non correlate quando il cliente dice solo "si".
                    enriched = []

            return {
                "intent": intent,
                "products": enriched,
                "question_asked": last_meta.get("question_asked", ""),
            }

        elif intent == "CONFIRMATION":
            last_meta = self._get_last_ai_metadata(full_history)
            proposed = last_meta.get("products_proposed", [])
            enriched = []
            for p in proposed:
                cod = p.get("cod_art")
                if cod:
                    full = self._db.find_product_by_code(cod, client_id)
                    if full:
                        merged = dict(full)
                        if p.get("quantity") is not None:
                            merged["quantity"] = p.get("quantity")
                        enriched.append(merged)
                    else:
                        enriched.append(p)
                else:
                    enriched.append(p)
            return {
                "intent": intent,
                "products": enriched,
                "pending_action": last_meta.get("action", ""),
                "pending_products": proposed,
            }

        elif intent == "ADVICE":
            keywords = intent_item.keywords
            params = ProductSearchParams(intent="ADVICE", keywords=keywords, expanded_categories=keywords, limit=10)
            products = self._search_products_for_chat(client_id, params)
            return {"intent": intent, "products": products, "keywords": keywords}

        elif intent == "CART_EDIT":
            return {"intent": intent, "products": [], "cart": cart, "reference": intent_item.reference}

        elif intent == "REORDER":
            keywords = intent_item.keywords
            params = ProductSearchParams(intent="REORDER", keywords=keywords, limit=10)
            products = self._search_products_for_chat(client_id, params)
            return {"intent": intent, "products": products, "keywords": keywords}

        return {"intent": intent, "products": []}

    def _extract_meaningful_tokens(self, text: str) -> list[str]:
        if not text:
            return []
        raw_tokens = re.findall(r"[a-zA-Z0-9']+", text.lower())
        cleaned: list[str] = []
        for tok in raw_tokens:
            tok = tok.strip("'")
            if not tok:
                continue
            if tok.isdigit():
                if len(tok) >= 3:
                    cleaned.append(tok)
                continue
            if tok in _UNIT_WORDS or tok in _GENERIC_STOPWORDS:
                continue
            if len(tok) < 3:
                continue
            cleaned.append(tok)

        # Preserva ordine e rimuove duplicati
        return list(dict.fromkeys(cleaned))

    def _is_greeting_message(self, message: str) -> bool:
        if not message:
            return False
        tokens = self._extract_meaningful_tokens(message)
        if not tokens:
            return False
        if len(tokens) > 3:
            return False
        return all(tok in _GREETING_WORDS for tok in tokens)

    def _is_quantity_only_reply(self, message: str) -> bool:
        if not message:
            return False
        if not re.search(r"\b\d+(?:[.,]\d+)?\b", message):
            return False

        filler_words = {
            "voglio", "vorrei", "dammi", "ordinare", "ordina", "di", "del", "della", "dei", "delle", "da",
        }
        words = [w.strip("'") for w in re.findall(r"[a-zA-Z']+", message.lower()) if w.strip("'")]
        meaningful = [w for w in words if w not in filler_words]
        if not meaningful:
            return True
        return all(w in _UNIT_WORDS for w in meaningful)

    def _extract_product_like_bold_names(self, text: str) -> list[str]:
        if not text:
            return []
        candidates = []
        for m in re.findall(r"\*\*(.+?)\*\*", text):
            name = m.strip()
            if not name or len(name) < 5:
                continue
            tokens = self._extract_meaningful_tokens(name)
            # Scarta unita/quantita (es. "6 cartoni", "CARTONE", "20 bottiglie").
            if len(tokens) < 2:
                continue
            candidates.append(name)
        return list(dict.fromkeys(candidates))

    def _match_products_from_names(
        self,
        names: list[str],
        candidates: list[dict],
        client_id: int,
    ) -> list[dict]:
        if not names:
            return []

        candidate_map = {p.get("cod_art"): p for p in candidates if p.get("cod_art")}
        matched: list[dict] = []
        seen: set[str] = set()

        for name in names[:4]:
            # 1) Match sui candidati gia' disponibili
            for p in candidates:
                cod = p.get("cod_art")
                if not cod or cod in seen:
                    continue
                if self._keywords_match_product([name], p):
                    matched.append(p)
                    seen.add(cod)
                    break
            else:
                # 2) Fallback DB con filtro assortimento, poi re-map su candidate map
                found = self._db.find_product_by_name(name, client_id)
                if not found:
                    continue
                cod = found.get("cod_art")
                if not cod or cod in seen:
                    continue
                if candidate_map and cod in candidate_map:
                    matched.append(candidate_map[cod])
                else:
                    matched.append(found)
                seen.add(cod)

        return matched

    def _keywords_match_product(self, keywords: list[str], product: dict) -> bool:
        joined_keywords = " ".join(keywords or []).lower()
        cod = str(product.get("cod_art") or "").lower()
        if cod and re.search(rf"\b{re.escape(cod)}\b", joined_keywords):
            return True

        kw_tokens = set(self._extract_meaningful_tokens(joined_keywords))
        if not kw_tokens:
            return False

        product_text = f"{product.get('des_art', '')} {product.get('cod_art', '')}"
        product_tokens = set(self._extract_meaningful_tokens(product_text))
        overlap = kw_tokens & product_tokens
        if not overlap:
            return False

        if len(kw_tokens) == 1:
            token = next(iter(kw_tokens))
            # Evita match deboli su token troppo corti/generici (es. "vap")
            return len(token) > 3 or token.isdigit()

        return len(overlap) >= min(2, len(kw_tokens))

    def _merge_recent_proposed_products(
        self,
        products: list[dict],
        keywords: list[str],
        client_id: int,
        full_history: list[dict],
    ) -> list[dict]:
        last_meta = self._get_last_ai_metadata(full_history)
        proposed = last_meta.get("products_proposed", []) if last_meta else []
        if not proposed:
            return products

        matched_proposed: list[dict] = []
        for p in proposed:
            cod = p.get("cod_art")
            if not cod:
                continue
            full = self._db.find_product_by_code(cod, client_id)
            candidate = full if full else p
            if self._keywords_match_product(keywords, candidate):
                matched_proposed.append(candidate)

        if not matched_proposed:
            return products

        merged: list[dict] = []
        seen: set[str] = set()
        for p in matched_proposed + products:
            cod = p.get("cod_art")
            if not cod or cod in seen:
                continue
            merged.append(p)
            seen.add(cod)

        logger.info(
            f"ORDER context merged with recent proposals: +{len(matched_proposed)} matched for {keywords}"
        )
        return merged[:20]

    # =======================================================================
    # Private — Business decision (singola call, multi-intent)
    # =======================================================================

    def _make_business_decision(
        self,
        user_message: str,
        intent_contexts: list[dict],
        full_history: list[dict],
        cart: list[dict],
        order_history: list[dict],
        pending_cart_edits: Optional[list] = None,
    ) -> BusinessDecisionResponse:
        try:
            system_prompt = self._get_system_prompt()

            # --- Sezione intenti ---
            intents_block = self._build_intents_block(intent_contexts)

            # --- Contesto carrello ---
            cart_text = "\n".join([
                f"- ID:{c['id']} | COD:{c['cod_art']} | {c.get('des_art', '')} | qta:{c['qta']}"
                for c in cart
            ]) if cart else "(carrello vuoto)"

            # --- Storia completa (ultimi 50 msg con metadata) ---
            history_text = self._format_history_for_decision(full_history[-50:])

            # --- Storico ordini ---
            order_history_json = json.dumps({
                "orders": [
                    {"id": h.get("id"), "data_ord": str(h.get("data_ord", "")), "items": h.get("items") or []}
                    for h in order_history
                ]
            }, ensure_ascii=False)

            # --- Pending cart edits (backward compat) ---
            pending_block = ""
            if pending_cart_edits:
                pending_repr = "\n".join([f"- {e}" for e in pending_cart_edits])
                pending_block = f"\n--- MODIFICHE CARRELLO IN SOSPESO ---\n{pending_repr}\n"

            user_prompt = f"""--- INTENTI RILEVATI E PRODOTTI DISPONIBILI ---
{intents_block}

--- CARRELLO ATTUALE ---
{cart_text}

--- CRONOLOGIA CONVERSAZIONE (con metadata) ---
{history_text}

--- STORICO ORDINI RECENTI ---
{order_history_json}
{pending_block}

Messaggio del cliente: "{user_message}"

Gestisci TUTTI gli intenti nell'ordine in cui sono elencati. Produci un'unica risposta coerente."""

            response = self._openai.beta.chat.completions.parse(
                model=self._model_smart,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=BusinessDecisionResponse,
                #temperature=0.1,
            )
            return response.choices[0].message.parsed

        except Exception as e:
            logger.error(f"Errore business decision: {e}", exc_info=True)
            return BusinessDecisionResponse(
                message="Scusa, ho un piccolo problema tecnico. Puoi ripetermi cosa ti serve?",
                product_items=[],
                order_confirmed=False,
            )

    def _build_intents_block(self, intent_contexts: list[dict]) -> str:
        """Costruisce il blocco testuale degli intent con i rispettivi prodotti."""
        parts = []
        for i, ctx in enumerate(intent_contexts, 1):
            intent = ctx["intent"]
            products = ctx.get("products", [])

            product_lines = []
            for p in products[:20]:
                line = (
                    f"  - COD:{p['cod_art']} | {p.get('des_art', '')} | UM:{p.get('des_um', '')}"
                    + (f" | {p.get('pezzi_conf', 1)} {p.get('des_tipo_um', 'pezzi')} per {p.get('des_um', 'unità')}"
                       if p.get('pezzi_conf', 1) not in (None, 0, 1) else "")
                )
                if p.get("not_in_assortment"):
                    line += " ⚠️ NON IN ASSORTIMENTO"
                product_lines.append(line)
            products_text = "\n".join(product_lines) if product_lines else "  (nessun prodotto trovato)"

            if intent == "CLARIFICATION":
                q = ctx.get("question_asked", "")
                parts.append(
                    f"[Intent {i}: CLARIFICATION]\n"
                    f"Il cliente risponde alla domanda dell'AI: \"{q}\"\n"
                    f"Opzioni tra cui scegliere:\n{products_text}"
                )
            elif intent == "CONFIRMATION":
                pending = ctx.get("pending_action", "")
                parts.append(
                    f"[Intent {i}: CONFIRMATION]\n"
                    f"Il cliente conferma l'azione precedente ({pending}).\n"
                    f"Prodotti proposti in precedenza:\n{products_text}"
                )
            elif intent == "CART_EDIT":
                cart = ctx.get("cart", [])
                cart_text = "\n".join([
                    f"  - ID:{c['id']} | COD:{c['cod_art']} | {c.get('des_art', '')} | qta:{c['qta']}"
                    for c in cart
                ]) if cart else "  (carrello vuoto)"
                ref = ctx.get("reference", "")
                parts.append(
                    f"[Intent {i}: CART_EDIT] {ref}\n"
                    f"Articoli nel carrello (usa gli ID per cart_edits):\n{cart_text}\n"
                    f"Azioni disponibili: remove | set_quantity (new_quantity=N) | reduce_by (reduce_by=N)\n"
                    f"Per 'togli N pezzi' usa reduce_by=N. Per 'mettimi N' usa set_quantity. Per 'togli tutto' usa remove."
                )
            elif intent == "ADVICE":
                kw = ", ".join(ctx.get("keywords", []))
                parts.append(
                    f"[Intent {i}: ADVICE] Categoria: {kw}\n"
                    f"Prodotti suggeribili:\n{products_text}"
                )
            else:
                kw = ", ".join(ctx.get("keywords", []))
                parts.append(
                    f"[Intent {i}: {intent}] Keywords: {kw}\n"
                    f"Prodotti trovati:\n{products_text}"
                )
        return "\n\n".join(parts)

    def _format_history_for_decision(self, history: list[dict]) -> str:
        """Formatta la storia per il modello smart, inclusi metadata."""
        lines = []
        for msg in history:
            sender = msg.get("sender", "")
            role = "Cliente" if sender == "user" else "AI"
            content = msg.get("content") or ""
            ocr = msg.get("ocr_text") or ""
            if not content and ocr:
                content = f"[IMMAGINE OCR: {ocr}]"
            if not content:
                continue
            meta = msg.get("metadata") or {}
            meta_str = ""
            if meta.get("action"):
                meta_str = f" [action={meta['action']}]"
            if meta.get("products_proposed"):
                names = ", ".join(
                    p.get("des_art", p.get("cod_art", ""))
                    for p in meta["products_proposed"][:3]
                )
                meta_str += f" [proposti: {names}]"
            if meta.get("question_asked"):
                meta_str += f" [domanda: {meta['question_asked']}]"
            lines.append(f"[{role}]{meta_str}: {content[:300]}")
        return "\n".join(lines) if lines else "(nessun messaggio)"

    # =======================================================================
    # Private — Validazione CART_EDIT
    # =======================================================================

    def _validate_cart_edits(
        self,
        cart_edits: list[CartEdit],
        cart: list[dict],
    ) -> Tuple[list[CartEdit], list[str]]:
        """Valida programmaticamente le modifiche al carrello."""
        cart_map = {item["id"]: item for item in cart}
        validated: list[CartEdit] = []
        issues: list[str] = []

        for edit in cart_edits:
            item = cart_map.get(edit.cart_item_id)
            if not item:
                issues.append(
                    f"L'articolo ID {edit.cart_item_id} non è più nel carrello."
                )
                continue

            name = item.get("des_art") or item.get("cod_art", "")
            current_qty = float(item.get("qta", 1))

            if edit.action == "remove":
                validated.append(edit)

            elif edit.action == "reduce_by":
                # "togli N" — sottrai N dalla quantità attuale
                n = edit.reduce_by
                if n is None or n <= 0:
                    issues.append(f"Quantità da sottrarre non valida per **{name}**.")
                    continue
                new_qty = current_qty - n
                if new_qty <= 0:
                    # Riduzione totale → remove
                    validated.append(CartEdit(cart_item_id=edit.cart_item_id, action="remove"))
                else:
                    validated.append(CartEdit(
                        cart_item_id=edit.cart_item_id,
                        action="set_quantity",
                        new_quantity=new_qty,
                    ))

            elif edit.action == "set_quantity":
                new_qty = edit.new_quantity
                if new_qty is None or new_qty < 0:
                    issues.append(f"Quantità non valida per **{name}**.")
                    continue
                if new_qty == 0:
                    validated.append(CartEdit(cart_item_id=edit.cart_item_id, action="remove"))
                else:
                    validated.append(edit)

            else:
                issues.append(f"Azione sconosciuta '{edit.action}' per **{name}**.")

        return validated, issues

    # =======================================================================
    # Private — "il solito"
    # =======================================================================

    def _handle_usual_request(self, client_id: int) -> dict:
        order_history = self._db.get_order_history_flat(client_id, limit=10)
        available = set(self._db.get_available_cod_art(client_id))

        for item in order_history:
            if item["cod_art"] in available:
                scorer_context = ConfidenceContext(
                    client_id=client_id,
                    products=[item],
                    order_history=order_history,
                    intent="REORDER",
                    user_message="il solito",
                    search_params_keywords=[],
                )
                conf = self._scorer.score(scorer_context).get(item["cod_art"], 0.5)
                msg = f"Come sempre, ho aggiunto {item.get('des_art') or item['cod_art']} al tuo ordine."
                return {
                    "success": True,
                    "response": msg,
                    "message": msg,
                    "product_items": [{"cod_art": item["cod_art"], "quantity": 1}],
                    "product_codes": [item["cod_art"]],
                    "product_confidences": {item["cod_art"]: conf},
                    "intent": "REORDER",
                    "order_confirmed": True,
                }

        if order_history:
            msg = "Al momento non ho disponibile il prodotto che ordini di solito. Vuoi che ti proponga altre opzioni?"
        else:
            msg = "Non ho trovato ordini precedenti. Puoi specificare quale prodotto vuoi?"
        return {"success": True, "response": msg, "message": msg, "order_confirmed": False}

    # =======================================================================
    # Private — Ricerca prodotti (invariata)
    # =======================================================================

    def _enrich_with_assortment_check(self, results: list[dict], client_id: int, keywords: list[str]) -> list[dict]:
        """Flag products that exist in catalog but not in client's assortment."""
        if not results or len(results) > 5:
            return results
        result_codes = {r["cod_art"] for r in results}
        catalog_results = self._db.search_products_keyword_no_asscli(keywords, limit=20)
        catalog_codes = {r["cod_art"] for r in catalog_results}
        not_in_assortment = catalog_codes - result_codes

        if not_in_assortment:
            for r in catalog_results:
                if r["cod_art"] in not_in_assortment:
                    r["not_in_assortment"] = True
                    logger.info(f"Product {r['cod_art']} in catalog but not in client {client_id}'s assortment")
            # Append catalog products that aren't in results
            for r in catalog_results:
                if r["cod_art"] not in result_codes:
                    results.append(r)
        return results

    def _search_products_for_chat(self, client_id: int, params) -> list[dict]:
        keywords = params.keywords or []
        if not keywords:
            return []
        if re.match(r'^\s*\d+\s*$', " ".join(keywords)):
            return []

        ilike_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if re.match(r'^\d+$', kw_lower):
                continue
            if kw_lower in _UNIT_WORDS or kw_lower in _GENERIC_STOPWORDS:
                continue
            ilike_keywords.append(kw)

        if not ilike_keywords:
            return []

        ilike_results = self._db.search_products_keyword(ilike_keywords, client_id, limit=20)
        logger.info(f"ILIKE: {len(ilike_results)} results for {ilike_keywords}")

        # Heuristic fallback mirato: acqua frizzante/gassata + mezzo litro.
        # Evita che il vector fallback proponga prodotti casuali quando la richiesta e chiara.
        joined_input = " ".join(keywords).lower()
        asks_water = "acqua" in joined_input
        asks_sparkling = any(x in joined_input for x in ("frizz", "gassat"))
        asks_half_liter = any(x in joined_input for x in (
            "mezzo litro", "mezza litro", "0.5", "0,5", "50cl", "500ml"
        ))

        if not ilike_results and asks_water and asks_sparkling:
            heuristic_keywords = ["acqua", "gassata"]
            if asks_half_liter:
                heuristic_keywords.append("050")
            ilike_results = self._db.search_products_keyword(heuristic_keywords, client_id, limit=20)
            if ilike_results:
                logger.info(
                    "ILIKE water heuristic: %d results for %s",
                    len(ilike_results),
                    heuristic_keywords,
                )
                ilike_keywords = heuristic_keywords

        if not ilike_results and asks_water:
            ilike_results = self._db.search_products_keyword(["acqua"], client_id, limit=20)
            if ilike_results:
                logger.info("ILIKE water fallback: %d results for ['acqua']", len(ilike_results))
                ilike_keywords = ["acqua"]

        # Fallback tokenizzato: gestisce frasi naturali tipo "succo al pompelmo"
        # quando il match frase-esatta non trova nulla.
        if not ilike_results:
            token_keywords: list[str] = []
            for kw in ilike_keywords:
                token_keywords.extend(self._extract_meaningful_tokens(kw))
            token_keywords = list(dict.fromkeys(token_keywords))
            if token_keywords:
                ilike_results = self._db.search_products_keyword(token_keywords, client_id, limit=20)
                logger.info(
                    f"ILIKE token fallback: {len(ilike_results)} results for tokens={token_keywords}"
                )
                if ilike_results:
                    ilike_keywords = token_keywords

        # Check if products exist in catalog but NOT in client's assortment
        # This helps the AI give better answers when a product exists but isn't in the assortment
        if len(ilike_results) <= 3:
            catalog_results = self._db.search_products_keyword_no_asscli(ilike_keywords, limit=20)
            ilike_codes = {r["cod_art"] for r in ilike_results}
            catalog_codes = {r["cod_art"] for r in catalog_results}
            not_in_assortment = catalog_codes - ilike_codes

            if not_in_assortment:
                # Flag products that exist in catalog but not in client's assortment
                for r in catalog_results:
                    if r["cod_art"] in not_in_assortment:
                        r["not_in_assortment"] = True
                        logger.info(f"Product {r['cod_art']} exists in catalog but not in client {client_id}'s assortment")

                # Merge: show both assortimented and non-assortimented products
                # Put assortimented products first, then not-in-assortment ones
                merged = list(ilike_results)
                for r in catalog_results:
                    if r["cod_art"] not in ilike_codes:
                        merged.append(r)

                logger.info(f"Search with catalog fallback: {len(merged)} total ({len(not_in_assortment)} not in assortment)")
                # Return merged results early — vector search won't help since it also
                # uses the asscli filter and would miss the catalog products
                return merged

        if len(ilike_results) == 1:
            return ilike_results

        # Vector search (disambiguation o fallback)
        search_text = " ".join(filter(None, [
            " ".join(params.keywords or []),
            " ".join(getattr(params, "expanded_categories", None) or []),
        ])).strip()

        if not search_text:
            return ilike_results if ilike_results else []

        query_clean = re.sub(r'\b(\d+)\b', '', search_text)
        for uw in _UNIT_WORDS:
            query_clean = re.sub(r'\b' + re.escape(uw) + r'\b', '', query_clean, flags=re.IGNORECASE)
        query_clean = re.sub(r'\s+', ' ', query_clean).strip()
        if not query_clean:
            return ilike_results if ilike_results else []

        if self._db.has_embeddings():
            try:
                embedding = self._ai_client.generate_embedding(query_clean)
                vector_results = self._db.search_products_vector(embedding, client_id, limit=20)
                self._last_similarity_map = {
                    r["cod_art"]: r["similarity"]
                    for r in vector_results if r.get("similarity") is not None
                }
                for r in vector_results:
                    r.pop("similarity", None)

                if not vector_results:
                    return self._enrich_with_assortment_check(
                        ilike_results if ilike_results else [], client_id, ilike_keywords
                    )

                if len(ilike_results) >= 2:
                    VECTOR_GATE = 0.50
                    ilike_set = {p["cod_art"] for p in ilike_results}
                    matched = next(
                        (vr for vr in vector_results
                         if vr["cod_art"] in ilike_set
                         and self._last_similarity_map.get(vr["cod_art"], 999) < VECTOR_GATE),
                        None
                    )
                    if matched:
                        rest = [r for r in vector_results if r["cod_art"] != matched["cod_art"]]
                        return self._enrich_with_assortment_check(
                            [matched] + rest, client_id, ilike_keywords
                        )
                    else:
                        ilike_map = {p["cod_art"]: p for p in ilike_results}
                        for vr in vector_results:
                            if vr["cod_art"] in ilike_map:
                                ilike_map[vr["cod_art"]]["match_source"] = "vector"
                        merged = list(ilike_map.values()) + [
                            r for r in vector_results if r["cod_art"] not in ilike_set
                        ]
                        return self._enrich_with_assortment_check(
                            merged, client_id, ilike_keywords
                        )

                return self._enrich_with_assortment_check(
                    vector_results, client_id, ilike_keywords
                )

            except Exception as e:
                logger.warning(f"Vector search fallita: {e}")
                try:
                    return self._enrich_with_assortment_check(
                        self._db.search_products_for_ai(query_clean, client_id, limit=20) or ilike_results,
                        client_id, ilike_keywords
                    )
                except Exception:
                    return self._enrich_with_assortment_check(
                        ilike_results, client_id, ilike_keywords
                    )

        return self._enrich_with_assortment_check(
            self._db.search_products_for_ai(query_clean, client_id, limit=20) or ilike_results,
            client_id, ilike_keywords
        )

    # =======================================================================
    # Private — Hallucination recovery (invariata)
    # =======================================================================

    def _recover_from_hallucinations(
        self,
        decision: BusinessDecisionResponse,
        raw_items: list[ProductItem],
        all_products: list[dict],
        client_id: int,
    ) -> Tuple[list[ProductItem], list[dict], BusinessDecisionResponse]:
        allowed_set = {p["cod_art"] for p in all_products}
        recovery_notes: list[str] = []

        resolved: list[ProductItem] = []
        for item in raw_items:
            cod = item.cod_art

            # Codice troppo lungo → probabilmente nome prodotto
            if len(cod) > 10:
                found = self._db.find_product_by_name(cod, client_id)
                if found and found["cod_art"] not in {r.cod_art for r in resolved}:
                    resolved.append(ProductItem(cod_art=found["cod_art"], quantity=item.quantity, confidence=item.confidence))
                    if found["cod_art"] not in allowed_set:
                        all_products.append(found)
                        allowed_set.add(found["cod_art"])
                    continue
                fuzzy = self._db.find_products_by_name_fuzzy(cod, client_id, limit=5)
                if len(fuzzy) == 1:
                    f = fuzzy[0]
                    resolved.append(ProductItem(cod_art=f["cod_art"], quantity=item.quantity, confidence=item.confidence))
                    if f["cod_art"] not in allowed_set:
                        all_products.append(f)
                        allowed_set.add(f["cod_art"])
                    recovery_notes.append(f"{f['des_art']}")
                    continue
                # 0 o 2+ → scarta (o già gestito via gap threshold come disambiguazione)
                logger.warning(f"Hallucination (nome): '{cod}' → {len(fuzzy)} fuzzy match, scartato")
                continue

            # Codice corto non in catalogo → fuzzy recovery
            if cod not in allowed_set:
                prod = self._db.find_product_by_code(cod, client_id)
                if prod:
                    resolved.append(item)
                    all_products.append(prod)
                    allowed_set.add(cod)
                    continue
                fuzzy = self._db.find_products_by_name_fuzzy(cod, client_id, limit=1)
                if fuzzy:
                    f = fuzzy[0]
                    resolved.append(ProductItem(cod_art=f["cod_art"], quantity=item.quantity, confidence=item.confidence))
                    all_products.append(f)
                    allowed_set.add(f["cod_art"])
                    recovery_notes.append(f"{f['des_art']}")
                    logger.info(f"Hallucination recovery: {cod} → {f['cod_art']}")
                else:
                    logger.warning(f"Hallucination: {cod} non trovato, scartato")
                continue

            resolved.append(item)

        if recovery_notes:
            note = f"Ho interpretato e trovato: {', '.join(recovery_notes[:3])}."
            decision.message = (decision.message + " " + note).strip() if decision.message else note

        return resolved, all_products, decision

    # =======================================================================
    # Private — Coerenza messaggio (invariata)
    # =======================================================================

    def _ensure_message_output_coherence(
        self,
        assistant_message: str,
        products: list[dict],
        current_items: list[ProductItem],
        current_order_confirmed: bool,
        user_intent_confirmation: bool,
        client_id: int,
        run_coherence_check: bool = False,
    ) -> Tuple[list[ProductItem], bool]:
        if not assistant_message or not products:
            return current_items, current_order_confirmed

        msg_clean = re.sub(r"\*\*", "", assistant_message)
        msg_upper = msg_clean.upper()
        extracted_with_pos = []
        seen_cod: set[str] = set()

        for p in products:
            cod = p.get("cod_art", "")
            des = p.get("des_art", "")
            if not cod or cod in seen_cod:
                continue
            best_pos = -1
            qty = 1.0

            m = re.search(r"\b" + re.escape(cod) + r"\b", assistant_message, re.IGNORECASE)
            if m:
                best_pos = m.start()
                qty = self._parse_quantity_near(assistant_message, cod, des)
            else:
                words = des.split()
                stems = [
                    (des[:50] if len(des) > 50 else des).strip(),
                    (des[:35] if len(des) > 35 else des).strip(),
                    (des[:20] if len(des) > 20 else des).strip(),
                ]
                if len(words) >= 2:
                    stems.append(" ".join(words[:2]))
                if len(words) >= 3:
                    stems.append(" ".join(words[:3]))
                for candidate in stems:
                    if not candidate or len(candidate) < 8:
                        continue
                    pos = msg_upper.find(candidate.upper())
                    if pos != -1:
                        best_pos = pos
                        qty = self._parse_quantity_near(assistant_message, cod, candidate)
                        break

            if best_pos >= 0:
                seen_cod.add(cod)
                extracted_with_pos.append((cod, qty, best_pos))

        extracted_with_pos.sort(key=lambda x: x[2])
        extracted = [(c, q) for c, q, _ in extracted_with_pos]

        if not extracted:
            return current_items, current_order_confirmed

        if run_coherence_check and current_items:
            extracted_codes = {c for c, _ in extracted}
            corrected = [it for it in current_items if it.cod_art in extracted_codes]
            if len(corrected) != len(current_items):
                return corrected, current_order_confirmed and len(corrected) > 0

        if len(current_items) == 0 and user_intent_confirmation and current_order_confirmed:
            scorer_context = ConfidenceContext(
                client_id=client_id,
                products=products,
                order_history=[],
                intent="CONFIRMATION",
                user_message=assistant_message,
                search_params_keywords=[],
            )
            confidence_scores = self._scorer.score(scorer_context)
            items = [
                ProductItem(cod_art=c, quantity=q, confidence=confidence_scores.get(c, 0.5))
                for c, q in extracted
            ]
            return items, True

        return current_items, current_order_confirmed

    # =======================================================================
    # Private — Utility
    # =======================================================================

    @staticmethod
    def _parse_quantity_near(message: str, cod_art: str, des_art: str) -> float:
        msg_upper = message.upper()
        ciascuno = re.search(r"(\d+)\s*ciascuno|ciascuno\s*(?:con)?\s*(\d+)", message, re.IGNORECASE)
        if ciascuno:
            n = int(ciascuno.group(1) or ciascuno.group(2) or 1)
            if n >= 1:
                return float(n)
        for needle in [cod_art, (des_art[:30] if des_art else ""), des_art]:
            if not needle:
                continue
            pos = msg_upper.find(needle.upper())
            if pos == -1:
                continue
            segment = message[max(0, pos - 30):pos]
            m = re.search(
                r"(\d+)\s*(?:bottiglie?|unità|pezzi|fusti|lattine?|×|x)?\s*$",
                segment, re.IGNORECASE
            )
            if m:
                return max(0.001, float(int(m.group(1))))
        return 1.0

    @staticmethod
    def _rewrite_false_addition_message(message: str, products_proposed: list[dict]) -> str:
        if not message:
            return message

        msg_lower = message.lower()
        claims_added = any(
            token in msg_lower
            for token in ("ho aggiunto", "ho inserito", "aggiungo", "inserisco")
        )
        is_negated = any(
            token in msg_lower
            for token in ("non ho aggiunto", "non posso aggiungere", "non posso inserire")
        )

        if not claims_added or is_negated:
            return message

        names = [p.get("des_art", "") for p in products_proposed if p.get("des_art")][:4]
        if names:
            options = "\n".join(f"- **{n}**" for n in names)
            return (
                "Per completare l'aggiunta, indicami quale prodotto vuoi inserire:\n"
                f"{options}"
            )

        return "Per completare l'aggiunta, indicami il prodotto esatto che vuoi nel carrello."

    def _determine_action(
        self,
        primary_intent: str,
        order_confirmed: bool,
        filtered_items: list[ProductItem],
        decision: BusinessDecisionResponse,
        gap_ambiguity: bool,
    ) -> str:
        if primary_intent == "CART_EDIT":
            return "EDIT_APPLIED" if decision.edit_confirmed else "PROPOSED"
        if primary_intent == "ADVICE":
            msg = decision.message or ""
            # Se l'AI ha proposto prodotti con una domanda → trattalo come ASKED_CLARIFICATION
            # così il turno successivo riceve il meta_hint corretto
            if "?" in msg and any(w in msg.lower() for w in ["quale", "preferis", "vuoi", "posso", "scegli", "opzione"]):
                return "ASKED_CLARIFICATION"
            return "ADVICE_GIVEN"
        if primary_intent == "REORDER":
            return "REORDER_ADDED" if order_confirmed else "PROPOSED"
        if gap_ambiguity:
            return "ASKED_CLARIFICATION"
        if order_confirmed and filtered_items:
            return "ORDER_ADDED"
        if filtered_items:
            # Controlla se la risposta contiene una domanda
            msg = decision.message or ""
            if "?" in msg:
                if any(w in msg.lower() for w in ["quale", "preferis", "scegli", "vuoi"]):
                    return "ASKED_CLARIFICATION"
                return "ASKED_CONFIRMATION"
            return "PROPOSED"
        return "PROPOSED"

    def _extract_question_from_message(self, message: str) -> Optional[str]:
        """Estrae le domande dal messaggio AI e le concatena in ordine."""
        questions = self._extract_questions_from_message(message)
        if not questions:
            return None
        return "\n".join(questions)

    def _extract_questions_from_message(self, message: str) -> list[str]:
        if "?" not in message:
            return []

        questions: list[str] = []
        for chunk in re.findall(r"[^?]*\?", message, flags=re.DOTALL):
            q = re.sub(r"\s+", " ", chunk).strip()
            if not q:
                continue
            questions.append(q)
        return list(dict.fromkeys(questions))

    def _split_questions_text(self, text: str) -> list[str]:
        if not text:
            return []
        extracted = self._extract_questions_from_message(text)
        if extracted:
            return extracted
        return [text.strip()] if text.strip() else []

    @staticmethod
    def _coerce_positive_quantity(value, default: float = 1.0) -> float:
        try:
            if value is None:
                return default
            if isinstance(value, str):
                value = value.replace(",", ".")
            qty = float(value)
            if qty > 0:
                return qty
        except Exception:
            pass
        return default

    def _extract_pending_quantities_from_ai_message(
        self,
        message: str,
        candidates: list[dict],
    ) -> dict[str, float]:
        if not message or not candidates:
            return {}

        qty_map: dict[str, float] = {}
        for p in candidates:
            cod = p.get("cod_art")
            if not cod or cod in qty_map:
                continue
            qty = self._extract_explicit_quantity_for_product(
                message,
                cod,
                p.get("des_art", ""),
            )
            if qty is not None:
                qty_map[cod] = qty
        return qty_map

    def _extract_explicit_quantity_for_product(
        self,
        message: str,
        cod_art: str,
        des_art: str,
    ) -> Optional[float]:
        unit_re = r"(?:carton\w*|casse?|fusti?|bottigl\w*|colli?|pezzi?|unit[àa]?|lattin\w*)"
        needles = [cod_art, des_art, (des_art[:35] if des_art else ""), (des_art[:20] if des_art else "")]
        seen_needles: set[str] = set()

        for needle in needles:
            if not needle:
                continue
            key = needle.strip().lower()
            if not key or key in seen_needles:
                continue
            seen_needles.add(key)

            for m in re.finditer(re.escape(needle), message, re.IGNORECASE):
                before = message[max(0, m.start() - 70):m.start()]
                after = message[m.end():min(len(message), m.end() + 35)]

                before_unit = list(re.finditer(rf"(\d+(?:[.,]\d+)?)\s*{unit_re}", before, re.IGNORECASE))
                if before_unit:
                    qty = self._coerce_positive_quantity(before_unit[-1].group(1), -1.0)
                    if qty > 0:
                        return qty

                before_verb = list(
                    re.finditer(
                        r"(?:ordinare|aggiungere|inserire|mettere)\s+(\d+(?:[.,]\d+)?)",
                        before,
                        re.IGNORECASE,
                    )
                )
                if before_verb:
                    qty = self._coerce_positive_quantity(before_verb[-1].group(1), -1.0)
                    if qty > 0:
                        return qty

                after_x = re.search(r"(?:x|×)\s*(\d+(?:[.,]\d+)?)", after, re.IGNORECASE)
                if after_x:
                    qty = self._coerce_positive_quantity(after_x.group(1), -1.0)
                    if qty > 0:
                        return qty

        return None

    def _is_confirmation_like_reply(self, message: str) -> bool:
        if not message:
            return False

        text = message.lower().replace("'", " ")
        negations = {"no", "non", "annulla", "stop", "aspetta"}
        tokens = re.findall(r"[a-zà-ù0-9]+", text)
        if not tokens:
            return False
        if any(tok in negations for tok in tokens):
            return False

        has_affirmative = any(tok in _AFFIRMATIVE_WORDS for tok in tokens)
        if not has_affirmative:
            return False

        allowed_fillers = {"e", "ed", "poi", "subito", "pure"}
        for tok in tokens:
            if tok in _AFFIRMATIVE_WORDS or tok in _UNIT_WORDS or tok in allowed_fillers:
                continue
            if re.fullmatch(r"\d+(?:[.,]\d+)?", tok):
                continue
            return False

        return True

    async def _save_and_return(
        self,
        session_id: Optional[int],
        user_message: str,
        ai_message: str,
        result: dict,
        intents: list[str],
        action: str,
    ) -> dict:
        """Salva messaggi e ritorna risultato per i casi di early return."""
        if session_id:
            user_msg_id = self._db.save_message(session_id, "user", user_message)
            ai_msg_id = self._db.save_message(
                session_id, "ai", ai_message,
                json.dumps(_build_ai_metadata(intents=intents, action=action,
                                               products_proposed=[], products_added=[]))
            )
            result["user_message_id"] = user_msg_id
            result["ai_message_id"] = ai_msg_id
            await self._emit_messages(session_id, user_msg_id, user_message, ai_msg_id, ai_message)
        return result

    async def _emit_messages(
        self,
        session_id: int,
        user_msg_id: int,
        user_content: str,
        ai_msg_id: Optional[int],
        ai_content: str,
        has_cart_changes: bool = False,
    ) -> None:
        if not self._broadcaster:
            return
        await self._broadcaster.emit(session_id, "message", {
            "id": user_msg_id, "sender": "user", "content": user_content,
        })
        await self._broadcaster.emit(OPERATOR_CHANNEL, "message", {
            "id": user_msg_id, "sender": "user", "content": user_content, "session_id": session_id,
        })
        if ai_msg_id:
            await self._broadcaster.emit(session_id, "message", {
                "id": ai_msg_id, "sender": "ai", "content": ai_content,
            })
        if has_cart_changes:
            await self._broadcaster.emit(session_id, "cart_update", {})

    # =======================================================================
    # Private — System prompt
    # =======================================================================

    def _get_system_prompt(self) -> str:
        return """# Ruolo
Assistente ordini B2B (bar/ristoro). Aiuta il cliente a ordinare nel suo interesse.

# Regola fondamentale
Aggiungi al carrello (order_confirmed=True, product_items compilati) **solo quando hai la certezza assoluta** del prodotto e della quantità. In caso di dubbio, proponi e chiedi conferma.

# Gestione multi-intent
Il cliente può esprimere più richieste in un singolo messaggio. Gestiscile **tutte** nell'ordine in cui appaiono nella sezione "INTENTI RILEVATI". Produci un'unica risposta che le indirizza una per una senza dimenticarne nessuna.

# Intent CLARIFICATION
Quando l'intent è CLARIFICATION, il cliente sta scegliendo tra le opzioni che l'AI aveva già proposto (vedi metadata della cronologia). **Non fare nuova ricerca**: scegli SOLO tra i prodotti elencati nella sezione "Opzioni tra cui scegliere" dell'intent. Ignora completamente i prodotti trovati altrove.

# Intent CONFIRMATION
Il cliente sta confermando l'azione proposta in precedenza. Leggi "Prodotti proposti in precedenza" nell'intent context e confermali con order_confirmed=True.
**REGOLA CRITICA**: Quando aggiungi un prodotto dopo una conferma, scrivi UNA sola frase del tipo "Ho aggiunto **{prodotto}** al carrello." NON menzionare ordini precedenti, NON fare riferimento ad altre conferme. Solo l'aggiunta corrente.

# Intent CART_EDIT
Usa gli ID nella sezione "Articoli nel carrello" per compilare cart_edits.

Regole per scegliere l'azione:
- `remove`: rimuove l'intero articolo. Usalo SOLO se il cliente dice "togli tutto", "rimuovi", "elimina" senza specificare una quantità parziale.
- `set_quantity`: imposta la quantità a un valore specifico. Usalo per tutti gli altri casi.

Casi comuni e come gestirli:
- "togli 50 grappe" con 100 a carrello → reduce_by, reduce_by=50
- "portami da 100 a 30" → set_quantity, new_quantity=30
- "mettimi 30 grappe" → set_quantity, new_quantity=30
- "aggiungi 20 alla grappa" (già a carrello) → set_quantity, new_quantity=quantità_attuale+20
- "togli la grappa" / "rimuovi tutto" / "elimina" → remove
- set_quantity a 0 equivale a rimozione completa

**REGOLA CRITICA**: quando il cliente dice "togli N" o "riduci di N" usa SEMPRE reduce_by con reduce_by=N. Non usare remove quando c'è una quantità esplicita da sottrarre.

# Regola conversione unità di misura
Se l'utente chiede in unità interne (des_tipo_um, es. "bottiglie", "colli") ma il prodotto si vende in unità esterne (des_um, es. "casse", "cartoni"):
- NON aggiungere subito al carrello
- Proponi con formula: "**{prodotto}** viene venduto/a in {des_um} da {pezzi_conf} {des_tipo_um}. Posso ordinare {ceil(richiesta/pezzi_conf)} {des_um}?"
- Arrotonda SEMPRE per eccesso (ceiling)
- Se la quantità richiesta è inferiore a pezzi_conf (es. "un collo" su un prodotto venduto a casse da 16), spiega che il minimo è 1 {des_um} e chiedi se vuole procedere
- Se l'utente conferma → aggiungi con la quantità convertita in des_um

**IMPORTANTE**: quando il cliente dice "un collo", "due litri", "tre bottiglie" o simili, NON cercare un prodotto chiamato "collo"/"litro"/"bottiglia". Si tratta di unità di misura che si riferiscono al prodotto già discusso nel messaggio precedente.

# Regola anti-allucinazione
- Usa SOLO codici presenti nella sezione prodotti del relativo intent
- **Se un prodotto è nell'elenco dei prodotti disponibili per l'intent, è disponibile. Non dire MAI che non è disponibile o che non è nell'elenco**
- Se il cliente menziona un prodotto che è stato discusso nelle ultime battute (anche se non è nella ricerca corrente), cercalo in CRONOLOGIA CONVERSAZIONE e usalo
- Se hai dubbi su quale prodotto scegliere tra due simili → proponi entrambi con una domanda chiara

# Prodotti NON IN ASSORTIMENTO
Alcuni prodotti possono apparire con il flag "⚠️ NON IN ASSORTIMENTO". Questo significa che il prodotto esiste nel catalogo generale ma **non fa parte dell'assortimento di questo cliente**.
- Se il cliente chiede un prodotto contrassegnato come "NON IN ASSORTIMENTO", **NON aggiungere al carrello** e informa il cliente che quel prodotto non è disponibile nel suo assortimento
- **NON dire "il prodotto non esiste" o "non è disponibile nel catalogo"** — di' invece che "non è presente nel tuo assortimento"
- Se ci sono prodotti simili che SONO nell'assortimento, proponi quelli come alternativa
- Se il cliente insiste, suggerisci di contattare il proprio referente commerciale per ampliare l'assortimento

# Formato risposta
- Italiano, tono cordiale, frasi brevi
- **Grassetto** per nomi prodotti
- Gestisci ogni intent in modo chiaro, senza mescolare
- Non aggiungere frasi inutili dopo aver confermato un'aggiunta (es. "Altro che posso fare?" è ok; "confermo l'ordine precedente" NON va mai scritto)
- Il campo `message` deve contenere SOLO il testo da mostrare al cliente. NON iniziare con frasi generiche tipo "Per il prodotto richiesto, ecco i dettagli..." — vai diretto alla risposta.

# Contratto output — CRITICO
**Modalità PROPOSTA**: order_confirmed=False, product_items=[]
**Modalità AGGIUNTA**: order_confirmed=True, product_items=[{cod_art, quantity, confidence}]
**Modalità EDIT**: cart_edits=[{cart_item_id, action, new_quantity}], edit_confirmed=True/False

REGOLA ASSOLUTA: se nel campo `message` scrivi "Ho aggiunto X" o qualsiasi frase che indica un'aggiunta al carrello, DEVI obbligatoriamente:
1. Impostare order_confirmed=True
2. Inserire il cod_art di X in product_items

Se non sei sicuro del prodotto, NON scrivere "Ho aggiunto" — proponi e chiedi conferma."""


