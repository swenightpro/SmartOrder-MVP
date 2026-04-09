import pytest
from unittest.mock import Mock, patch, AsyncMock
from pydantic import BaseModel
import json
from services.conversation_service import ConversationService, MultiIntentClassification, IntentItem, BusinessDecisionResponse, ProductItem, ProductSearchParams
from ports.i_ai_client import IAIClient
from adapters.postgres_adapter import PostgresAdapter

@pytest.fixture
def mock_db():
    db = Mock()
    db.get_messages.return_value = []
    db.get_cart_by_client.return_value = []
    db.get_last_orders.return_value = []
    db.get_order_history_flat.return_value = []
    db.get_available_cod_art.return_value = []
    db.search_products_keyword.return_value = []
    db.search_products_keyword_no_asscli.return_value = []
    db.search_products.return_value = []
    db.search_products_vector.return_value = []
    db.save_message.return_value = 1
    db.is_product_in_assortment.return_value = True
    return db

@pytest.fixture
def mock_ai_client():
    ai = Mock()
    ai.generate_json = AsyncMock()
    ai.generate_embedding = AsyncMock(return_value=[0.1])
    return ai

@pytest.fixture
def mock_broadcaster():
    mock = Mock()
    mock.emit = AsyncMock()
    return mock

@pytest.fixture
def mock_openai_client():
    with patch("services.conversation_service.OpenAI") as mock_openai:
        instance = json.loads
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.parsed = MultiIntentClassification(
            intents=[IntentItem(intent="ORDER", keywords=["pane"])]
        )
        # For parse:
        mock_client = Mock()
        mock_client.beta.chat.completions.parse.return_value = mock_response
        mock_openai.return_value = mock_client
        yield mock_client

@pytest.fixture
def cs(mock_db, mock_ai_client, mock_broadcaster, mock_openai_client):
    return ConversationService(mock_db, mock_ai_client, mock_broadcaster)


def test_classify_intents(cs, mock_openai_client):
    # test_classify_intents is sync
    res = cs._classify_intents("ciao", [], [])
    assert res.intents[0].intent == "ORDER"

def test_make_business_decision(cs, mock_openai_client):
    # make_business_decision is sync
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.parsed = BusinessDecisionResponse(
        message="ok",
        product_items=[ProductItem(cod_art="PANE", quantity=1)],
        order_confirmed=True
    )
    cs._openai.beta.chat.completions.parse.return_value = mock_response

    res = cs._make_business_decision("ciao", [], [], [], [], [])
    assert res.message == "ok"

def test_is_greeting(cs):
    assert cs._is_greeting_message("ciao") == True
    assert cs._is_greeting_message("voglio del pane") == False

def test_is_quantity_only(cs):
    assert cs._is_quantity_only_reply("2") == True
    assert cs._is_quantity_only_reply("voglio 2 di pane") == False

def test_coerce_positive_quantity(cs):
    assert cs._coerce_positive_quantity(5) == 5
    assert cs._coerce_positive_quantity(-2) == 1
    assert cs._coerce_positive_quantity(0) == 1
    assert cs._coerce_positive_quantity("due") == 1

def test_split_questions_text(cs):
    text = "Come stai? Quanto costa il pane?"
    parts = cs._split_questions_text(text)
    assert len(parts) == 2
    assert "Come stai" in parts[0]

def test_extract_meaningful_tokens(cs):
    text = "Un pezzo di test"
    tokens = cs._extract_meaningful_tokens(text)
    assert "pezzo" in tokens or "test" in tokens

def test_is_confirmation(cs):
    assert cs._is_confirmation_like_reply("sì") == True
    assert cs._is_confirmation_like_reply("no") == False

def test_handle_usual_request(cs, mock_db):
    mock_db.get_order_history_flat.return_value = [{"cod_art": "PANE", "des_art": "Pane", "qta": 2}]
    res = cs._handle_usual_request(100)
    assert res is not None

@pytest.mark.asyncio
async def test_handle_message_greeting(cs, mock_db):
    res = await cs.handle_message("ciao", 100, 1)
    assert res is not None
    assert "message" in res

@pytest.mark.asyncio
async def test_handle_message_usual(cs, mock_db):
    mock_db.get_order_history_flat.return_value = [{"cod_art": "P1", "des_art": "P", "qta": 1}]
    # Handle "il solito" bypasses AI
    res = await cs.handle_message("il solito", 100, 1)
    assert res is not None

@pytest.mark.asyncio
async def test_handle_message_full_flow(cs, mock_db, mock_openai_client):
    
    # Mock internal methods
    cs._classify_intents = Mock(return_value=MultiIntentClassification(
        intents=[IntentItem(intent="ORDER", keywords=["pane"])]
    ))
    cs._make_business_decision = Mock(return_value=BusinessDecisionResponse(
        message="Aggiunto pane",
        product_items=[ProductItem(cod_art="PANE", quantity=1)],
        order_confirmed=True
    ))
    cs._search_products_for_chat = Mock(return_value=[{"cod_art": "PANE", "des_art": "Pane", "quantity": 1}])
    cs._recover_from_hallucinations = Mock(
        return_value=([ProductItem(cod_art="PANE", quantity=1)], [{"cod_art": "PANE"}], cs._make_business_decision.return_value)
    )

    res = await cs.handle_message("voglio del pane", 100, 1)
    assert res is not None
