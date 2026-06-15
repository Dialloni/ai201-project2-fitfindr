"""
Tests for the SecondLook tools and planning loop.

Run from the project root with:
    pytest tests/

The search/filter tests are offline. The two LLM-dependent tests are skipped
automatically when GROQ_API_KEY is not set, so the suite still passes in CI.
"""

import os

import pytest

from tools import search_listings, suggest_outfit, create_fit_card, compare_price
from agent import run_agent, _parse_query, _detect_followup
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

_HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))
_needs_llm = pytest.mark.skipif(not _HAS_KEY, reason="GROQ_API_KEY not set")


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Impossible combination -> empty list, no exception.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=40)
    assert all(item["price"] <= 40 for item in results)


def test_search_size_filter_token_match():
    # "M" should match listings sized "M", "S/M", "M/L" — never one without M.
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_sorted_by_relevance():
    results = search_listings("vintage denim jacket", size=None, max_price=None)
    # Best match first: top result should mention at least one query keyword.
    assert results
    top = (results[0]["title"] + " " + " ".join(results[0]["style_tags"])).lower()
    assert any(w in top for w in ("vintage", "denim", "jacket"))


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_bad_item():
    # No LLM call needed — guard returns a string.
    assert isinstance(suggest_outfit({}, get_example_wardrobe()), str)


@_needs_llm
def test_suggest_outfit_with_wardrobe():
    item = search_listings("vintage graphic tee", None, 50)[0]
    out = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(out, str) and len(out) > 0


@_needs_llm
def test_suggest_outfit_empty_wardrobe():
    item = search_listings("vintage graphic tee", None, 50)[0]
    out = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(out, str) and len(out) > 0


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_fit_card_empty_outfit():
    # Empty outfit -> descriptive error string, never an exception.
    item = search_listings("vintage graphic tee", None, 50)[0]
    card = create_fit_card("", item)
    assert isinstance(card, str)
    assert "fit card" in card.lower()


@_needs_llm
def test_fit_card_varies():
    item = search_listings("vintage graphic tee", None, 50)[0]
    a = create_fit_card("pair with baggy jeans and chunky sneakers", item)
    b = create_fit_card("layer under a denim jacket with combat boots", item)
    assert a != b


# ── compare_price (stretch) ───────────────────────────────────────────────────

def test_compare_price_returns_string():
    item = search_listings("jacket", None, None)[0]
    assert isinstance(compare_price(item), str)


def test_compare_price_bad_input():
    assert isinstance(compare_price({}), str)


# ── planning loop ─────────────────────────────────────────────────────────────

def test_parse_query():
    p = _parse_query("vintage graphic tee under $30, size M")
    assert p["max_price"] == 30.0
    assert p["size"] == "M"
    assert "vintage" in p["description"].lower()


def test_run_agent_no_results_sets_error():
    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    assert session["error"] is not None
    assert session["fit_card"] is None
    assert session["outfit_suggestion"] is None


@_needs_llm
def test_run_agent_happy_path():
    session = run_agent("vintage graphic tee under $30", get_example_wardrobe())
    assert session["error"] is None
    assert session["selected_item"] is not None
    assert isinstance(session["fit_card"], str) and len(session["fit_card"]) > 0
    assert len(session["trace"]) > 0   # reasoning trace populated


# ── conversation memory / follow-ups (offline) ────────────────────────────────

def test_detect_followup_needs_prior_results():
    # No previous session -> always a fresh search.
    assert _detect_followup("show me another", None) is None
    fake_prev = {"search_results": [{"x": 1}], "selected_item": {"x": 1}}
    assert _detect_followup("show me another one", fake_prev) == "next"
    assert _detect_followup("anything cheaper?", fake_prev) == "cheaper"
    assert _detect_followup("style it differently", fake_prev) == "restyle"
    assert _detect_followup("vintage denim jacket", fake_prev) is None


def test_followup_next_beyond_end_sets_note():
    # Build a prev session whose selected item is the LAST result, then ask for
    # another — should stop with a message and not crash (no LLM call on this path).
    prev = {
        "search_results": [{"title": "A", "price": 10, "category": "tops",
                            "platform": "depop"}],
        "result_index": 0,
        "selected_item": {"title": "A", "price": 10, "category": "tops",
                          "platform": "depop"},
        "parsed": {},
    }
    session = run_agent("show me another", get_example_wardrobe(), prev_session=prev)
    assert session["error"] is not None
    assert session["fit_card"] is None
