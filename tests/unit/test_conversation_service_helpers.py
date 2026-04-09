from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import services.conversation_service as conv_mod
from services.conversation_service import (
    BusinessDecisionResponse,
    CartEdit,
    IntentItem,
    MultiIntentClassification,
    ProductItem,
    ProductSearchParams,
    _build_ai_metadata,
)


@pytest.fixture
def service(monkeypatch):
    mock_openai = Mock()
    monkeypatch.setattr(conv_mod, "OpenAI", Mock(return_value=mock_openai))

    db = Mock()
    db.get_messages.return_value = []
    db.get_messages_with_user_feedback.return_value = []
    db.search_products_keyword.return_value = []
    db.search_products_keyword_no_asscli.return_value = []
    db.search_products_for_ai.return_value = []
    db.search_products_vector.return_value = []
    db.has_embeddings.return_value = False
    db.get_order_history_flat.return_value = []
    db.get_available_cod_art.return_value = []

    ai = Mock()
    ai.generate_embedding.return_value = [0.1, 0.2]
    ai.transcribe_audio = AsyncMock(return_value="ok")

    broadcaster = Mock()
    broadcaster.emit = AsyncMock()

    svc = conv_mod.ConversationService(db, ai, broadcaster)
    return svc, db, ai, broadcaster, mock_openai


def test_build_ai_metadata_optional_fields():
    out = _build_ai_metadata(
        intents=["ORDER"],
        action="PROPOSED",
        products_proposed=[{"cod_art": "A"}],
        products_added=[{"cod_art": "B"}],
        question_asked="quale?",
    )
    assert out["intents"] == ["ORDER"]
    assert out["products_proposed"][0]["cod_art"] == "A"
    assert out["question_asked"] == "quale?"


def test_token_and_greeting_helpers(service):
    svc, _, _, _, _ = service

    assert svc._extract_meaningful_tokens("il 12 acqua frizzante 500") == ["acqua", "frizzante", "500"]
    assert svc._is_greeting_message("Ciao") is True
    assert svc._is_greeting_message("ciao buongiorno salve ehi") is False
    assert svc._is_quantity_only_reply("2") is True
    assert svc._is_quantity_only_reply("voglio 2 bottiglie") is True
    assert svc._is_quantity_only_reply("voglio 2 acqua") is False


def test_extract_and_match_helpers(service):
    svc, db, _, _, _ = service

    names = svc._extract_product_like_bold_names("prova **Acqua Frizzante 50cl** e **6 cartoni**")
    assert names == ["Acqua Frizzante 50cl"]

    product = {"cod_art": "A01", "des_art": "Acqua Frizzante"}
    assert svc._keywords_match_product(["A01"], product) is True
    assert svc._keywords_match_product(["acqua", "frizzante"], product) is True
    assert svc._keywords_match_product(["vap"], product) is False

    db.find_product_by_name.return_value = {"cod_art": "B02", "des_art": "Succo Arancia"}
    matched = svc._match_products_from_names(
        ["Acqua Frizzante", "Succo Arancia"],
        [{"cod_art": "A01", "des_art": "Acqua Frizzante"}],
        10,
    )
    assert [m["cod_art"] for m in matched] == ["A01", "B02"]


def test_merge_recent_proposed_products(service):
    svc, db, _, _, _ = service
    db.find_product_by_code.return_value = {"cod_art": "A01", "des_art": "Acqua Frizzante"}

    history = [
        {
            "sender": "ai",
            "metadata": {
                "products_proposed": [{"cod_art": "A01"}],
                "action": "PROPOSED",
            },
        }
    ]

    out = svc._merge_recent_proposed_products(
        products=[{"cod_art": "B01", "des_art": "Birra"}],
        keywords=["acqua", "frizzante"],
        client_id=10,
        full_history=history,
    )
    assert out[0]["cod_art"] == "A01"
    assert out[1]["cod_art"] == "B01"


def test_format_blocks_and_validation(service):
    svc, _, _, _, _ = service

    contexts = [
        {
            "intent": "CLARIFICATION",
            "question_asked": "quale acqua?",
            "products": [{"cod_art": "A", "des_art": "Acqua", "des_um": "bt", "pezzi_conf": 1}],
        },
        {
            "intent": "CONFIRMATION",
            "pending_action": "PROPOSED",
            "products": [{"cod_art": "B", "des_art": "Birra", "des_um": "ct", "pezzi_conf": 2, "des_tipo_um": "pezzi"}],
        },
        {
            "intent": "CART_EDIT",
            "reference": "togli dal carrello",
            "cart": [{"id": 1, "cod_art": "A", "des_art": "Acqua", "qta": 3}],
            "products": [],
        },
        {
            "intent": "ADVICE",
            "keywords": ["vino"],
            "products": [],
        },
    ]
    block = svc._build_intents_block(contexts)
    assert "CLARIFICATION" in block
    assert "CART_EDIT" in block
    assert "ADVICE" in block

    history_text = svc._format_history_for_decision(
        [
            {
                "sender": "ai",
                "content": "test",
                "metadata": {
                    "action": "PROPOSED",
                    "products_proposed": [{"des_art": "Acqua"}],
                    "question_asked": "quale?",
                },
            },
            {"sender": "user", "content": "", "ocr_text": "OCR"},
        ]
    )
    assert "[AI]" in history_text
    assert "OCR" in history_text

    validated, issues = svc._validate_cart_edits(
        [
            CartEdit(cart_item_id=1, action="remove"),
            CartEdit(cart_item_id=2, action="reduce_by", reduce_by=1),
            CartEdit(cart_item_id=3, action="set_quantity", new_quantity=0),
            CartEdit(cart_item_id=4, action="set_quantity", new_quantity=-1),
            CartEdit(cart_item_id=99, action="unknown"),
        ],
        [
            {"id": 1, "cod_art": "A", "des_art": "Acqua", "qta": 3},
            {"id": 2, "cod_art": "B", "des_art": "Birra", "qta": 2},
            {"id": 3, "cod_art": "C", "des_art": "Cola", "qta": 1},
            {"id": 4, "cod_art": "D", "des_art": "Succo", "qta": 2},
        ],
    )
    assert len(validated) == 3
    assert len(issues) == 2


def test_handle_usual_and_assortment_enrich(service):
    svc, db, _, _, _ = service
    db.get_order_history_flat.return_value = [{"cod_art": "A", "des_art": "Acqua"}]
    db.get_available_cod_art.return_value = ["A"]
    out = svc._handle_usual_request(7)
    assert out["order_confirmed"] is True

    db.get_order_history_flat.return_value = [{"cod_art": "A", "des_art": "Acqua"}]
    db.get_available_cod_art.return_value = []
    out2 = svc._handle_usual_request(7)
    assert out2["order_confirmed"] is False

    db.search_products_keyword_no_asscli.return_value = [
        {"cod_art": "A", "des_art": "Acqua"},
        {"cod_art": "B", "des_art": "Birra"},
    ]
    enriched = svc._enrich_with_assortment_check([{"cod_art": "A", "des_art": "Acqua"}], 1, ["acqua"])
    assert len(enriched) == 2
    assert any(p.get("not_in_assortment") for p in enriched)


def test_search_products_for_chat_paths(service):
    svc, db, ai, _, _ = service

    assert svc._search_products_for_chat(1, ProductSearchParams(keywords=[])) == []
    assert svc._search_products_for_chat(1, ProductSearchParams(keywords=["123"])) == []

    db.search_products_keyword.return_value = [{"cod_art": "A", "des_art": "Acqua"}]
    single = svc._search_products_for_chat(1, ProductSearchParams(keywords=["acqua"]))
    assert single == [{"cod_art": "A", "des_art": "Acqua"}]

    db.search_products_keyword.return_value = []
    db.search_products_keyword_no_asscli.return_value = [{"cod_art": "X", "des_art": "Acqua X"}]
    heuristic = svc._search_products_for_chat(1, ProductSearchParams(keywords=["acqua", "frizzante", "0.5"]))
    assert heuristic

    db.search_products_keyword.return_value = [{"cod_art": "A"}, {"cod_art": "B"}]
    db.search_products_keyword_no_asscli.return_value = []
    db.has_embeddings.return_value = True
    db.search_products_vector.return_value = [
        {"cod_art": "A", "similarity": 0.2},
        {"cod_art": "C", "similarity": 0.9},
    ]
    vec = svc._search_products_for_chat(1, ProductSearchParams(keywords=["acqua", "naturale"]))
    assert vec[0]["cod_art"] == "A"

    ai.generate_embedding.side_effect = RuntimeError("embed failed")
    db.search_products_for_ai.return_value = [{"cod_art": "F"}]
    fallback = svc._search_products_for_chat(1, ProductSearchParams(keywords=["succo pompelmo"]))
    assert fallback == [{"cod_art": "F"}]


def test_recover_hallucinations_and_coherence(service):
    svc, db, _, _, _ = service

    decision = BusinessDecisionResponse(message="ok", order_confirmed=True)
    db.find_product_by_name.return_value = {"cod_art": "A01", "des_art": "Acqua"}
    db.find_products_by_name_fuzzy.return_value = [{"cod_art": "B02", "des_art": "Birra"}]
    db.find_product_by_code.return_value = None

    recovered, products, decision2 = svc._recover_from_hallucinations(
        decision=decision,
        raw_items=[
            ProductItem(cod_art="NOME-PRODOTTO-MOLTO-LUNGO", quantity=1),
            ProductItem(cod_art="ZZZ", quantity=2),
        ],
        all_products=[{"cod_art": "C03", "des_art": "Cola"}],
        client_id=7,
    )
    assert recovered
    assert products
    assert decision2.message

    corrected, keep = svc._ensure_message_output_coherence(
        assistant_message="Ho aggiunto 2 A01 al carrello.",
        products=[{"cod_art": "A01", "des_art": "Acqua"}],
        current_items=[ProductItem(cod_art="A01", quantity=1)],
        current_order_confirmed=True,
        user_intent_confirmation=False,
        client_id=7,
        run_coherence_check=True,
    )
    assert corrected
    assert keep is True

    empty_items, confirmed = svc._ensure_message_output_coherence(
        assistant_message="Confermo: 3 A01",
        products=[{"cod_art": "A01", "des_art": "Acqua"}],
        current_items=[],
        current_order_confirmed=True,
        user_intent_confirmation=True,
        client_id=7,
        run_coherence_check=False,
    )
    assert empty_items
    assert confirmed is True


def test_static_and_question_utilities(service):
    svc, _, _, _, _ = service

    assert svc._parse_quantity_near("3 A01", "A01", "Acqua") == 3.0
    assert svc._parse_quantity_near("ciascuno 2 A01", "A01", "Acqua") == 2.0

    rewritten = svc._rewrite_false_addition_message(
        "Ho aggiunto i prodotti richiesti",
        [{"des_art": "Acqua"}, {"des_art": "Birra"}],
    )
    assert "Per completare l'aggiunta" in rewritten
    assert "Acqua" in rewritten

    assert svc._determine_action("CART_EDIT", False, [], BusinessDecisionResponse(edit_confirmed=True), False) == "EDIT_APPLIED"
    assert svc._determine_action("ADVICE", False, [], BusinessDecisionResponse(message="quale preferisci?"), False) == "ASKED_CLARIFICATION"
    assert svc._determine_action("REORDER", True, [ProductItem(cod_art="A", quantity=1)], BusinessDecisionResponse(), False) == "REORDER_ADDED"
    assert svc._determine_action("ORDER", False, [], BusinessDecisionResponse(), True) == "ASKED_CLARIFICATION"

    msg = "Vuoi acqua? Oppure birra?"
    assert svc._extract_question_from_message(msg) == "Vuoi acqua?\nOppure birra?"
    assert svc._extract_questions_from_message(msg) == ["Vuoi acqua?", "Oppure birra?"]
    assert svc._split_questions_text("Nessuna domanda") == ["Nessuna domanda"]

    assert svc._coerce_positive_quantity("2,5") == 2.5
    assert svc._coerce_positive_quantity("zero") == 1.0

    qty_map = svc._extract_pending_quantities_from_ai_message(
        "aggiungere 3 bottiglie Acqua A01 e Birra B02 x 2",
        [
            {"cod_art": "A01", "des_art": "Acqua"},
            {"cod_art": "B02", "des_art": "Birra"},
        ],
    )
    assert qty_map["A01"] == 3.0
    assert qty_map["B02"] == 3.0

    assert svc._is_confirmation_like_reply("sì ok") is True
    assert svc._is_confirmation_like_reply("no, aspetta") is False


@pytest.mark.asyncio
async def test_emit_and_save_helpers(service):
    svc, db, _, broadcaster, _ = service
    db.save_message.side_effect = [{"id": 10}, {"id": 11}]

    # save_message returns plain ids in production code; this keeps test robust with mock side effects.
    db.save_message.side_effect = [10, 11]

    result = await svc._save_and_return(
        session_id=12,
        user_message="ciao",
        ai_message="ok",
        result={"success": True},
        intents=["ADVICE"],
        action="PROPOSED",
    )
    assert result["user_message_id"] == 10
    assert result["ai_message_id"] == 11
    assert broadcaster.emit.await_count >= 2

    await svc._emit_messages(12, 10, "u", 11, "a", has_cart_changes=True)
    assert broadcaster.emit.await_count >= 5

    svc_no_broadcast = conv_mod.ConversationService(db, Mock(), None)
    await svc_no_broadcast._emit_messages(12, 10, "u", 11, "a", has_cart_changes=True)
