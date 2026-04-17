from services.chat.events_service import _event_embedding_text, _is_era_creating
from shared.utils.gemini import _normalize_vector


def test_normalize_vector_returns_unit_length() -> None:
    vec = _normalize_vector([3.0, 4.0])
    assert round((vec[0] ** 2 + vec[1] ** 2) ** 0.5, 6) == 1.0


def test_event_embedding_text_includes_tags() -> None:
    text = _event_embedding_text("Launch", "New variant", ["meta", "ctr"])
    assert "Launch" in text
    assert "tags:" in text


def test_is_era_creating_explicit_override() -> None:
    assert _is_era_creating("user_note", True) is True
    assert _is_era_creating("product_launch", False) is False
