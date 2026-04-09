import pytest
from unittest.mock import Mock
from services.confidence_scorer import ConfidenceScorer, ConfidenceContext


class TestConfidenceScorer:
    """Unit test per ConfidenceScorer (calcolo fiducia risultati AI)"""

    @pytest.fixture
    def scorer(self):
        """Istanza di ConfidenceScorer"""
        return ConfidenceScorer()

    # ========== Test Initialize Scorer ==========

    def test_scorer_initializes_with_settings(self, scorer):
        """Test: ConfidenceScorer inizializza con pesi da Settings"""
        # Verify
        assert scorer.low_confidence_threshold is not None
        assert scorer._weights is not None
        assert isinstance(scorer._weights, dict)

    # ========== Test Signal History ==========

    def test_signal_history_ordered_before(self, scorer):
        """Test: _signal_history ritorna 1.0 se cliente ha già ordinato"""
        # Setup
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001", "des_art": "Pasta"}],
            order_history=[
                {
                    "id": 1,
                    "items": [{"cod_art": "ART001", "qta": 5}]
                }
            ],
            intent="ORDER",
            user_message="voglio ART001",
            search_params_keywords=["art001"],
        )
        
        # Execute
        result = scorer._signal_history(context, "ART001")
        
        # Verify
        assert result == 1.0

    def test_signal_history_not_ordered_before(self, scorer):
        """Test: _signal_history ritorna 0.5 se cliente non ha mai ordinato"""
        # Setup
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001", "des_art": "Pasta Nuova"}],
            order_history=[],  # Vuoto
            intent="ORDER",
            user_message="voglio pasta nuova",
            search_params_keywords=["pasta", "nuova"],
        )
        
        # Execute
        result = scorer._signal_history(context, "ART001")
        
        # Verify
        assert result == 0.5

    # ========== Test Signal Similarity ==========

    def test_signal_similarity_with_cosine_distance(self, scorer):
        """Test: _signal_similarity calcola 1-distance da similarity_map"""
        # Setup
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001", "des_art": "Pasta"}],
            order_history=[],
            intent="ORDER",
            user_message="pasta integrale",
            search_params_keywords=["pasta"],
            similarity_map={"ART001": 0.15},  # cosine distance 0.15
        )
        
        # Execute
        result = scorer._signal_similarity(context, "ART001")
        
        # Verify - dovrebbe essere 1.0 - 0.15 = 0.85
        assert 0.84 < result < 0.86

    def test_signal_similarity_no_embeddings_order_intent(self, scorer):
        """Test: _signal_similarity fallback per CONFIRMATION intent"""
        # Setup
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001"}],
            order_history=[],
            intent="CONFIRMATION",
            user_message="perfetto",
            search_params_keywords=[],
            similarity_map={},  # Vuota
        )
        
        # Execute
        result = scorer._signal_similarity(context, "ART001")
        
        # Verify - dovrebbe usare fallback 0.55 per CONFIRMATION
        assert result == 0.55

    def test_signal_similarity_no_embeddings_other_intent(self, scorer):
        """Test: _signal_similarity fallback 0.3 per intent non specifici"""
        # Setup
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001"}],
            order_history=[],
            intent="ORDER",
            user_message="pasta",
            search_params_keywords=["pasta"],
            similarity_map={},  # Vuota
        )
        
        # Execute
        result = scorer._signal_similarity(context, "ART001")
        
        # Verify - dovrebbe usare fallback 0.3 per ORDER
        assert result == 0.3

    # ========== Test Signal Intent Type ==========

    def test_signal_intent_type_confirmation(self, scorer):
        """Test: _signal_intent_type per CONFIRMATION intent (high tier)"""
        # Setup
        intent = "CONFIRMATION"
        
        # Execute
        result = scorer._signal_intent_type(intent)
        
        # Verify - CONFIRMATION è high tier = 1.0
        assert result == 1.0

    def test_signal_intent_type_reorder(self, scorer):
        """Test: _signal_intent_type per REORDER intent (high tier)"""
        # Setup
        intent = "REORDER"
        
        # Execute
        result = scorer._signal_intent_type(intent)
        
        # Verify - REORDER è high tier = 1.0
        assert result == 1.0

    def test_signal_intent_type_specific(self, scorer):
        """Test: _signal_intent_type per SPECIFIC intent (medium tier)"""
        # Setup
        intent = "SPECIFIC"
        
        # Execute
        result = scorer._signal_intent_type(intent)
        
        # Verify - SPECIFIC è medium tier = 0.7
        assert result == 0.7

    def test_signal_intent_type_default(self, scorer):
        """Test: _signal_intent_type per intent sconosciuto (default)"""
        # Setup
        intent = "UNKNOWN_INTENT"
        
        # Execute
        result = scorer._signal_intent_type(intent)
        
        # Verify - intent sconosciuto ritorna default = 0.5
        assert result == 0.5

    # ========== Test Signal Quantity ==========

    def test_signal_quantity_explicit(self, scorer):
        """Test: _signal_quantity per quantità esplicita nel messaggio"""
        # Setup - messaggio con numero esplicito
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001"}],
            order_history=[],
            intent="ORDER",
            user_message="voglio 5 pasta",  # "5" è numero esplicito
            search_params_keywords=["pasta"],
        )
        
        # Execute
        result = scorer._signal_quantity(context)
        
        # Verify - deve riconoscere quantità esplicita
        assert result > 0.5

    def test_signal_quantity_implicit(self, scorer):
        """Test: _signal_quantity per quantità implicita"""
        # Setup - messaggio senza numero
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001"}],
            order_history=[],
            intent="ORDER",
            user_message="voglio pasta",  # Nessun numero
            search_params_keywords=["pasta"],
        )
        
        # Execute
        result = scorer._signal_quantity(context)
        
        # Verify - deve avere score più basso per quantità implicita
        assert 0.0 <= result <= 0.7

    # ========== Test Score Computation ==========

    def test_score_computes_confidence_for_products(self, scorer):
        """Test: score() ritorna dict con confidence per ogni prodotto"""
        # Setup
        context = ConfidenceContext(
            client_id=100,
            products=[
                {"cod_art": "ART001", "des_art": "Pasta A", "match_source": "keyword"},
                {"cod_art": "ART002", "des_art": "Pasta B", "match_source": "vector"},
            ],
            order_history=[
                {"id": 1, "items": [{"cod_art": "ART001", "qta": 5}]}
            ],
            intent="ORDER",
            user_message="voglio 5 pasta",
            search_params_keywords=["pasta"],
            similarity_map={"ART001": 0.1, "ART002": 0.2},
        )
        
        # Execute
        result = scorer.score(context)
        
        # Verify
        assert isinstance(result, dict)
        assert "ART001" in result
        assert "ART002" in result
        # Confidence deve essere tra 0 e 1
        assert 0.0 <= result["ART001"] <= 1.0
        assert 0.0 <= result["ART002"] <= 1.0

    def test_score_empty_products(self, scorer):
        """Test: score() ritorna dict vuoto se non ci sono prodotti"""
        # Setup
        context = ConfidenceContext(
            client_id=100,
            products=[],  # Nessun prodotto
            order_history=[],
            intent="ORDER",
            user_message="pasta",
            search_params_keywords=["pasta"],
        )
        
        # Execute
        result = scorer.score(context)
        
        # Verify
        assert result == {}

    def test_score_clamps_to_01_range(self, scorer):
        """Test: score() clamma confidence tra 0 e 1"""
        # Setup con pesi che potrebbero superare 1.0
        context = ConfidenceContext(
            client_id=100,
            products=[{"cod_art": "ART001", "des_art": "Test"}],
            order_history=[{"id": 1, "items": [{"cod_art": "ART001"}]}],
            intent="ORDER",
            user_message="voglio 5 art001",
            search_params_keywords=["art001"],
            similarity_map={"ART001": 0.0},  # Score massimo
        )
        
        # Execute
        result = scorer.score(context)
        
        # Verify
        confidence = result.get("ART001", 0)
        assert 0.0 <= confidence <= 1.0

    # ========== Test Low Confidence Threshold ==========

    def test_low_confidence_threshold_property(self, scorer):
        """Test: low_confidence_threshold property ritorna valore da Settings"""
        # Execute
        threshold = scorer.low_confidence_threshold
        
        # Verify
        assert isinstance(threshold, (float, int))
        assert 0.0 <= threshold <= 1.0