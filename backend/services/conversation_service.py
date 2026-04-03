import re
import json
import logging
from typing import IO, Optional, List, Tuple

from openai import OpenAI
from pydantic import BaseModel, Field

from config import get_settings
from ports.i_ai_client import IAIClient
from ports.i_session_manager import ISessionManager
from services.sse_broadcaster import OPERATOR_CHANNEL
from adapters.postgres_adapter import PostgresAdapter

logger = logging.getLogger(__name__)

class ProductSearchParams(BaseModel):
    intent: str = "SPECIFIC"
    keywords: list[str] = Field(default_factory=list)
    expanded_categories: list[str] = Field(default_factory=list)
    limit: int = 10

class ProductItem(BaseModel):
    cod_art: str
    quantity: float = 1
    confidence: float = 0.9

class CartEdit(BaseModel):
    cart_item_id: int
    action: str
    new_quantity: Optional[float] = None

class BusinessDecisionResponse(BaseModel):
    message: str = ""
    product_codes: list[str] = Field(default_factory=list)
    product_items: list[ProductItem] = Field(default_factory=list)
    order_confirmed: bool = False
    cart_edits: list[CartEdit] = Field(default_factory=list)
    edit_confirmed: bool = False

class ConversationService:
    """Servizio applicativo per il flusso conversazionale."""

    def __init__(self, db: PostgresAdapter, ai_client: IAIClient, broadcaster=None):
        self._db = db
        self._ai_client = ai_client
        self._broadcaster = broadcaster
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
        # Serializzazione datetime per JSON
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

    # =======================================================================
    # Chat AI — Orchestrazione principale
    # =======================================================================

    async def handle_message(self, message: str, client_id: int,
                             history: list[dict],
                             session_id: Optional[int] = None,
                             pending_cart_edits: Optional[list] = None) -> dict:
        """Processa un messaggio utente e ritorna la risposta AI + azioni."""
        logger.info(f"Nuova richiesta chat - Cliente: {client_id}, Messaggio: '{message}'")

        message_lower = message.lower().strip()

        # --- Caso speciale: "il solito" ---
        usual_phrases = [
            "il solito", "come sempre", "quello di prima", "lo stesso", "come al solito",
            "come l'altra volta", "l'ultimo", "ultimo ordinato", "l'ultima volta"
        ]
        is_usual = any(phrase in message_lower for phrase in usual_phrases)

        if is_usual:
            return self._handle_usual_request(client_id)

        # --- Estrazione intenti ---
        search_params = self._extract_search_params(message)
        intent = search_params.intent

        # --- Intent EDIT: carrello vuoto => risposta diretta ---
        if intent == "EDIT":
            cart = self._db.get_cart_by_client(client_id, session_id)
            if not cart:
                return {
                    "success": True,
                    "message": "Il carrello è vuoto, non c'è nulla da modificare. Vuoi aggiungere qualcosa?",
                    "cart_edits": None,
                    "edit_confirmed": False,
                }

        # --- Ricerca prodotti ---
        products = self._search_products_for_chat(client_id, search_params)

        # --- Conferma: arricchisci con prodotti da messaggi precedenti ---
        if search_params.intent == "CONFIRMATION" and history:
            products = self._enrich_confirmation_products(
                client_id, products, history
            )

        # --- Storico ordini ---
        order_history = self._db.get_last_orders(client_id, limit=10)

        # --- Carrello per contesto EDIT ---
        cart_for_context = (
            self._db.get_cart_by_client(client_id, session_id)
            if intent == "EDIT" else None
        )

        # --- Decisione business AI ---
        decision = self._make_business_decision(
            user_message=message,
            products=products,
            order_history=order_history,
            search_params=search_params,
            history=history,
            cart=cart_for_context,
            pending_cart_edits=pending_cart_edits,
        )

        # --- Override intent (solo CONFIRMATION può aggiungere) ---
        if intent == "ADVICE":
            if decision.product_items or decision.order_confirmed:
                logger.info("Intent ADVICE: forzati order_confirmed=False e product_items=[]")
            raw_items = []
            order_confirmed = False
        elif intent == "SPECIFIC":
            if decision.product_items or decision.order_confirmed:
                logger.info("Intent SPECIFIC: forzati order_confirmed=False e product_items=[]")
            raw_items = []
            order_confirmed = False
        elif intent == "EDIT":
            raw_items = []
            order_confirmed = False
        else:
            raw_items = list(decision.product_items or [])
            order_confirmed = decision.order_confirmed

        # --- Coerenza messaggio ↔ output ---
        raw_items, order_confirmed = self._ensure_message_output_coherence(
            decision.message or "",
            products,
            raw_items,
            order_confirmed,
            user_intent_confirmation=(search_params.intent == "CONFIRMATION"),
        )

        # --- Filtra solo prodotti disponibili ---
        allowed_cod_art = {p["cod_art"] for p in products}
        filtered_items = [it for it in raw_items if it.cod_art in allowed_cod_art]
        dropped = [it.cod_art for it in raw_items if it.cod_art not in allowed_cod_art]
        if dropped:
            logger.warning(f"Prodotti rimossi (non in lista): {dropped}")
        if raw_items and not filtered_items:
            logger.warning("IA ha restituito cod_art non in lista disponibili, filtrati a []")
        order_confirmed = order_confirmed and len(filtered_items) > 0

        # --- Serializza cart_edits ---
        cart_edits_out = None
        if decision.cart_edits:
            cart_edits_out = [e.model_dump() for e in decision.cart_edits]
        edit_confirmed_out = decision.edit_confirmed

        # --- Salva messaggi nel DB (se session_id presente) ---
        user_message_id = None
        ai_message_id = None
        if session_id:
            user_message_id = self._db.save_message(session_id, "user", message)
            ai_metadata = None
            if filtered_items:
                ai_metadata = json.dumps({
                    "suggested_products": [
                        {"cod_art": it.cod_art, "quantity": it.quantity, "confidence": it.confidence}
                        for it in filtered_items
                    ]
                })
            ai_message_id = self._db.save_message(
                session_id, "ai", decision.message or "", ai_metadata
            )

            # --- Emit SSE events ---
            if self._broadcaster:
                await self._broadcaster.emit(session_id, "message", {
                    "id": user_message_id,
                    "sender": "user",
                    "content": message,
                })
                # Also notify operator dashboard in real-time
                await self._broadcaster.emit(OPERATOR_CHANNEL, "message", {
                    "id": user_message_id,
                    "sender": "user",
                    "content": message,
                    "session_id": session_id,
                })
                if ai_message_id:
                    await self._broadcaster.emit(session_id, "message", {
                        "id": ai_message_id,
                        "sender": "ai",
                        "content": decision.message or "",
                    })
                # Emit cart update if AI added/edited items
                if filtered_items or decision.cart_edits:
                    await self._broadcaster.emit(session_id, "cart_update", {})

        # --- Build response ---
        product_items_out = [
            {"cod_art": it.cod_art, "quantity": it.quantity}
            for it in filtered_items
        ]
        product_codes_out = [it.cod_art for it in filtered_items]
        product_confidences_out = {
            it.cod_art: it.confidence for it in filtered_items
        } if filtered_items else None

        logger.info(
            f"Risposta: message='{decision.message}', "
            f"product_items={[(it.cod_art, it.quantity) for it in filtered_items]}, "
            f"order_confirmed={order_confirmed}"
        )

        return {
            "success": True,
            "response": decision.message,
            "message": decision.message,
            "user_message_id": user_message_id,
            "ai_message_id": ai_message_id,
            "product_items": product_items_out if product_items_out else None,
            "product_codes": product_codes_out if product_codes_out else None,
            "product_confidences": product_confidences_out,
            "order_confirmed": order_confirmed,
            "cart_edits": cart_edits_out,
            "edit_confirmed": edit_confirmed_out,
        }

    # =======================================================================
    # Private — "il solito"
    # =======================================================================

    def _handle_usual_request(self, client_id: int) -> dict:
        order_history = self._db.get_order_history_flat(client_id, limit=10)
        available = set(self._db.get_available_cod_art(client_id))

        for item in order_history:
            if item["cod_art"] in available:
                logger.info(f"'il solito' - uso: {item['cod_art']}")
                return {
                    "success": True,
                    "message": f"Come sempre, ho aggiunto {item.get('des_art') or item['cod_art']} al tuo ordine.",
                    "product_items": [{"cod_art": item["cod_art"], "quantity": 1}],
                    "product_codes": [item["cod_art"]],
                    "product_confidences": {item["cod_art"]: 0.95},
                    "order_confirmed": True,
                }

        if order_history:
            return {
                "success": True,
                "message": "Al momento non ho disponibile il prodotto che ordini di solito. Vuoi che ti proponga altre opzioni?",
                "order_confirmed": False,
            }
        return {
            "success": True,
            "message": "Non ho trovato ordini precedenti. Puoi specificare quale prodotto vuoi?",
            "order_confirmed": False,
        }

    # =======================================================================
    # Private — Estrazione parametri di ricerca
    # =======================================================================

    def _extract_search_params(self, user_message: str) -> ProductSearchParams:
        try:
            logger.info(f"Analisi semantica: '{user_message}'")

            # Filtro conferme hardcoded
            conferme = [
                "si", "sì", "ok", "va bene", "confermo", "aggiungi", "procedi", "corretto",
                "sì aggiungila", "si aggiungila", "aggiungila", "aggiungila pure",
                "va bene quella", "quella va bene", "sì quella", "si quella",
                "entrambe", "entrambi", "sì entrambe",
            ]
            msg_clean = user_message.lower().strip().replace("!", "").replace(".", "").replace("?", "")

            if (msg_clean in conferme
                or (msg_clean.startswith("sì ") and "aggiung" in msg_clean)
                or (msg_clean.startswith("si ") and "aggiung" in msg_clean)):
                logger.info("Rilevata conferma verbale: salto estrazione keyword.")
                return ProductSearchParams(intent="CONFIRMATION", keywords=[], limit=10)

            response = self._openai.beta.chat.completions.parse(
                model=self._model_fast,
                messages=[
                    {
                        "role": "system",
                        "content": """Sei un assistente per ordini B2B in un bar/ristoro. Analizza il **significato** della richiesta (non limitarti a parole chiave: considera sinonimi e formulazioni diverse) e restituisci:

                        - intent (criterio semantico):
                          * SPECIFIC: l'utente vuole AGGIUNGERE qualcosa al proprio ordine (nuovo prodotto, non ancora in carrello). Qualsiasi formulazione con questo significato: aggiungere, ordinare, ricevere, avere, portami, inserisci, includi, metti nel carrello, voglio X, mi serve X, dammi X, prendo X, due coca per favore, ecc. Se l'intenzione è "voglio che questo prodotto entri nel mio ordine" → SPECIFIC.
                          * ADVICE: l'utente chiede un consiglio o una categoria (es. aperitivo, qualcosa per la colazione, cosa mi consigli).
                          * REORDER: riordino / rifare un ordine precedente.
                          * CONFIRMATION: l'utente conferma una proposta dell'assistente (sì, ok, va bene, quella, la prima, aggiungila).
                          * EDIT: SOLO quando l'utente si riferisce chiaramente a qualcosa CHE È GIÀ NEL CARRELLO e vuole MODIFICARLO o RIMUOVERLO. Esempi: togliere/rimuovere/eliminare/cancellare un articolo già ordinato; cambiare la quantità di qualcosa già presente (es. "da 2 a 1", "riduci", "invece di 2 metti 1"). Se l'utente vuole "avere" o "ordinare" qualcosa di nuovo → SPECIFIC, non EDIT. In caso di dubbio tra aggiungere qualcosa di nuovo (SPECIFIC) e modificare il carrello (EDIT) → scegli SPECIFIC.

                        - keywords: termini principali estratti dalla richiesta. Se intent=ADVICE includi la categoria.
                        - expanded_categories: SOLO se intent=ADVICE, elenca 4-5 tipi di prodotti concreti. Se intent=SPECIFIC lascia expanded_categories vuota.
                        - Non estrarre verbi, articoli o espressioni di cortesia nelle keywords.""",
                    },
                    {"role": "user", "content": user_message},
                ],
                response_format=ProductSearchParams,
            )

            params = response.choices[0].message.parsed
            if not params.keywords and len(user_message.split()) < 5 and msg_clean not in conferme:
                params.keywords = [user_message.strip()]
                if params.intent == "ADVICE" and not params.expanded_categories:
                    params.expanded_categories = [user_message.strip()]
            return params

        except Exception as e:
            logger.error(f"Errore estrazione parametri: {e}")
            return ProductSearchParams(intent="SPECIFIC", keywords=[], limit=10)

    # =======================================================================
    # Private — Ricerca prodotti per la chat
    # =======================================================================

    def _search_products_for_chat(self, client_id: int,
                                  params: ProductSearchParams) -> list[dict]:
        """Cerca prodotti rilevanti per il contesto della chat."""
        all_products = []
        seen = set()

        for kw in (params.keywords or []):
            results = self._db.search_products_for_ai(kw, client_id, limit=params.limit)
            for p in results:
                if p["cod_art"] not in seen:
                    seen.add(p["cod_art"])
                    all_products.append(p)

        for cat in (params.expanded_categories or []):
            results = self._db.search_products_for_ai(cat, client_id, limit=5)
            for p in results:
                if p["cod_art"] not in seen:
                    seen.add(p["cod_art"])
                    all_products.append(p)

        return all_products

    def _enrich_confirmation_products(self, client_id: int,
                                      products: list[dict],
                                      history: list[dict]) -> list[dict]:
        """Arricchisce la lista prodotti con quelli menzionati in messaggi precedenti."""
        seen = {p["cod_art"] for p in products}

        for role_val in ["user", "assistant"]:
            for m in reversed(history):
                r = (m.get("role") or "").lower()
                if r == role_val:
                    content = (m.get("content") or "").strip()
                    if content:
                        prev_params = self._extract_search_params(content)
                        prev_products = self._search_products_for_chat(client_id, prev_params)
                        for p in prev_products:
                            if p["cod_art"] not in seen:
                                seen.add(p["cod_art"])
                                products.append(p)
                    break

        return products

    # =======================================================================
    # Private — Decisione business AI (il prompt gigante)
    # =======================================================================

    def _make_business_decision(
        self,
        user_message: str,
        products: list[dict],
        order_history: list[dict],
        search_params: ProductSearchParams,
        history: Optional[list[dict]] = None,
        cart: Optional[list[dict]] = None,
        pending_cart_edits: Optional[list] = None,
    ) -> BusinessDecisionResponse:
        try:
            logger.info("IA sta prendendo decisione commerciale...")

            max_show = 50 if len(products) > 20 else 15
            products_text = "\n".join([
                f"- COD: {p['cod_art']} | {p.get('des_art', '')} | UM: {p.get('des_um', '')}"
                for p in products[:max_show]
            ]) if products else "Nessun prodotto trovato in catalogo."

            history_text = ""
            if order_history:
                lines = []
                for h in order_history[:10]:
                    items = h.get("items") or []
                    if isinstance(items, str):
                        try:
                            items = json.loads(items)
                        except Exception:
                            items = []
                    for it in (items if isinstance(items, list) else []):
                        lines.append(
                            f"- {it.get('des_art', '')} (Cod: {it.get('cod_art', '')}) "
                            f"qta: {it.get('qta', '')}. Data: {h.get('data_ord', '')}"
                        )
                history_text = "\n".join(lines[:10]) if lines else "Il cliente non ha ordini precedenti."
            else:
                history_text = "Il cliente non ha ordini precedenti."

            # Cart context (per intent EDIT)
            is_edit = search_params.intent == "EDIT"
            edit_instructions = ""
            if is_edit and cart:
                cart_text = "\n".join([
                    f"- ID: {c['id']} | COD: {c['cod_art']} | {c.get('des_art', c['cod_art'])} | qta: {c['qta']}"
                    for c in cart
                ])
                edit_instructions = f"""
--- CARRELLO ATTUALE (usa gli ID per cart_edits) ---
{cart_text}

L'utente chiede di MODIFICARE il carrello. Devi restituire:
- **cart_edits**: lista di modifiche. Ogni elemento ha: cart_item_id (id dalla tabella sopra), action ("remove" per togliere, "set_quantity" per cambiare quantità), new_quantity (obbligatorio solo se action=set_quantity).
- **edit_confirmed**: True se le modifiche sono **solo** set_quantity → applica subito. False se c'è almeno una rimozione → chiedi conferma.
"""

            pending_edits_block = ""
            if pending_cart_edits:
                pending_repr = "\n".join([f"- {e}" for e in pending_cart_edits])
                pending_edits_block = f"""
--- MODIFICHE CARRELLO IN SOSPESO ---
{pending_repr}

**Regola:** Se l'utente conferma queste modifiche, restituisci esattamente queste in cart_edits e edit_confirmed=True.
"""

            # Il system prompt grande (identico al PoC)
            system_prompt = self._get_system_prompt()

            # Conversation context
            conversation_block = ""
            if history:
                lines = []
                for m in history[:10]:
                    label = "Utente" if (m.get("role") or "").lower() == "user" else "Assistente"
                    lines.append(f"{label}: {m.get('content', '').strip()}")
                conversation_block = "--- CONVERSAZIONE PRECEDENTE ---\n" + "\n".join(lines) + "\n--- FINE CONVERSAZIONE ---\n\n"

            # Intent hint
            intent_hint = ""
            current_intent = search_params.intent or "SPECIFIC"
            if search_params.intent == "ADVICE" and (search_params.keywords or search_params.expanded_categories):
                k = search_params.keywords[:3]
                e = search_params.expanded_categories[:5]
                intent_hint = f"\n(Intento: consiglio/categoria - cerca: {', '.join(k or e)}.)\n\n"

            confirmation_only_hint = ""
            if current_intent != "CONFIRMATION":
                confirmation_only_hint = f"""
**REGOLA OBBLIGATORIA (intent={current_intent}):** NON restituire order_confirmed=True né product_items. Proponi opzioni o chiedi conferma.
"""

            user_prompt = f"""{conversation_block}Messaggio Utente: "{user_message}"
            {intent_hint}{confirmation_only_hint}DATI DI CONTESTO:
            --- STORICO ORDINI ---
            {history_text}

            --- PRODOTTI DISPONIBILI ORA ---
            {products_text}
            {edit_instructions}
            {pending_edits_block}

            Prendi una decisione."""

            response = self._openai.beta.chat.completions.parse(
                model=self._model_smart,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=BusinessDecisionResponse,
                temperature=0.1,
            )

            return response.choices[0].message.parsed

        except Exception as e:
            logger.error(f"Errore decisione IA: {e}", exc_info=True)
            return BusinessDecisionResponse(
                message="Scusa, ho un piccolo problema tecnico. Puoi ripetermi cosa ti serve?",
                product_codes=[],
                product_items=[],
                order_confirmed=False,
            )

    # =======================================================================
    # Private — Coerenza output
    # =======================================================================

    def _ensure_message_output_coherence(
        self,
        assistant_message: str,
        products: list[dict],
        current_items: list[ProductItem],
        current_order_confirmed: bool,
        user_intent_confirmation: bool,
    ) -> Tuple[list[ProductItem], bool]:
        """Se l'output è incoerente (conferma ma product_items vuoto), inferisci dal testo."""
        if not assistant_message or not products:
            return current_items, current_order_confirmed

        msg_clean = re.sub(r"\*\*", "", assistant_message)
        msg_upper = msg_clean.upper()
        extracted_with_pos = []
        seen_cod = set()

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
                if len(words) >= 4:
                    stems.append(" ".join(words[:4]))
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

        use_extracted = len(current_items) == 0 and user_intent_confirmation
        if use_extracted:
            if not current_order_confirmed:
                return current_items, current_order_confirmed
            items = [ProductItem(cod_art=c, quantity=q, confidence=0.7) for c, q in extracted]
            logger.info(f"Coerenza: inferiti product_items={[(it.cod_art, it.quantity) for it in items]}")
            return items, True

        return current_items, current_order_confirmed

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
            m = re.search(r"(\d+)\s*(?:bottiglie?|unità|pezzi|fusti|lattine?|×|x)?\s*$",
                          segment, re.IGNORECASE)
            if m:
                return max(0.001, float(int(m.group(1))))
        return 1.0

    # =======================================================================
    # Private — System prompt (identico al PoC, estratto per leggibilità)
    # =======================================================================

    def _get_system_prompt(self) -> str:
        return """# Ruolo
Assistente ordini B2B (bar/ristoro). Assisti il cliente nel suo interesse: aiutalo a ordinare ciò che vuole. Aggiungi al carrello **solo quando hai la certezza** del prodotto da aggiungere; altrimenti proponi opzioni o chiedi conferma.

# Regola di decisione (priorità massima)
Aggiungi al carrello (order_confirmed=True, product_items compilati) **solo quando hai la certezza** del prodotto (o dei prodotti) da aggiungere.

- **Certezza per confermare**: l'ordine si conferma (order_confirmed=True) solo quando hai la certezza del prodotto da aggiungere. L'utente deve aver detto in modo **esplicito** che conferma quanto gli hai proposto.
- Se l'utente cambia preferenza o indica un'altra categoria: **non dare per scontato** che abbia già scelto un articolo.
- **Meglio chiedere una volta in più che una in meno**: in dubbio, chiedi conferma.

# Vincoli di dominio
- **Catalogo**: ogni cod_art in product_items deve essere presente in PRODOTTI DISPONIBILI ORA.
- **Quantità**: usa il numero indicato dall'utente; se non specificato, default 1.
- **Prodotto non in catalogo**: proponi **solo** alternative da PRODOTTI DISPONIBILI ORA.

# Contratto di output
**Modalità A — PROPOSTA**: order_confirmed=False, product_items=[]
**Modalità B — AGGIUNTA**: order_confirmed=True, product_items con cod_art e quantity.

**Struttura di product_items:**
- Un solo prodotto: [{\"cod_art\": \"<codice>\", \"quantity\": N, \"confidence\": 0.95}]
- Più prodotti: un elemento per ogni articolo.
- **confidence** (0.0-1.0): sicurezza della proposta.

# Formato
Messaggio: markdown essenziale, **grassetto** per nomi prodotti. Frasi brevi, tono cordiale, italiano."""
