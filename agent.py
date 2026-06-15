"""
agent.py

The SecondLook planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card, compare_price


# ── query parsing ─────────────────────────────────────────────────────────────

_SIZE_RE = re.compile(
    r"\bsize\s+([a-z0-9./]+)|\b(xxs|xs|s|m|l|xl|xxl)\b|\b(us\s?\d+(?:\.\d)?)\b",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"(?:under|below|less than|max|<)\s*\$?\s*(\d+(?:\.\d+)?)",
                       re.IGNORECASE)


def _parse_query(query: str) -> dict:
    """
    Extract description / size / max_price from a natural-language query using
    regex. Size and price phrases are stripped out so they don't pollute the
    description keywords.
    """
    size = None
    max_price = None

    price_match = _PRICE_RE.search(query)
    if price_match:
        max_price = float(price_match.group(1))

    size_match = _SIZE_RE.search(query)
    if size_match:
        size = next(g for g in size_match.groups() if g).strip().upper()

    # Build the description from what's left after removing size/price phrases.
    description = _PRICE_RE.sub("", query)
    description = re.sub(r"\bsize\s+[a-z0-9./]+", "", description, flags=re.IGNORECASE)
    description = re.sub(r"[\$]", "", description).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "result_index": 0,           # which result is currently selected
        "selected_item": None,       # current item, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "price_check": None,         # string returned by compare_price (stretch)
        "retry_note": None,          # set if search was retried with looser filters
        "trace": [],                 # human-readable log of each agent decision
        "turn": "search",            # search | next | cheaper | restyle
        "error": None,               # set if the interaction ended early
    }


def _log(session: dict, msg: str) -> None:
    """Append a reasoning line to the session trace (shown in the UI)."""
    session["trace"].append(msg)


# ── follow-up detection (conversation memory) ──────────────────────────────────

_NEXT_WORDS = ("another", "other one", "next", "something else", "show me more",
               "different one", "other option", "more options")
_CHEAPER_WORDS = ("cheaper", "less expensive", "lower price", "more affordable")
_RESTYLE_WORDS = ("restyle", "style it", "different outfit", "another outfit",
                  "other way", "new outfit", "style again", "different look")


def _detect_followup(query: str, prev: dict | None) -> str | None:
    """
    Decide whether this query is a follow-up that should reuse the previous
    session's results instead of running a brand-new search.

    Returns "next" | "cheaper" | "restyle", or None for a fresh search.
    Only fires when there is a previous session with usable search results.
    """
    if not prev or not prev.get("search_results") or prev.get("selected_item") is None:
        return None
    q = query.lower().strip()
    if any(w in q for w in _RESTYLE_WORDS):
        return "restyle"
    if any(w in q for w in _CHEAPER_WORDS):
        return "cheaper"
    if any(w in q for w in _NEXT_WORDS):
        return "next"
    return None


# ── shared styling step ─────────────────────────────────────────────────────────

def _style_and_card(session: dict) -> dict:
    """
    Steps 5–7, shared by fresh searches and follow-ups: style the selected item,
    write the fit card, and run the price check. State flows item → outfit → card.
    """
    item = session["selected_item"]
    n_wardrobe = len(session["wardrobe"].get("items", []))
    mode = "general advice (empty wardrobe)" if n_wardrobe == 0 \
        else f"{n_wardrobe} wardrobe items"
    _log(session, f"👗 suggest_outfit('{item['title']}', {mode})")
    session["outfit_suggestion"] = suggest_outfit(item, session["wardrobe"])

    _log(session, "✨ create_fit_card(outfit, item) — caption at temp=1.0")
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], item)

    _log(session, f"💰 compare_price('{item['title']}') vs {item['category']} median")
    session["price_check"] = compare_price(item)
    return session


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict, prev_session: dict | None = None) -> dict:
    """
    Main agent entry point. Runs the SecondLook planning loop for one turn and
    returns the completed session dict.

    Args:
        query:        Natural language user request.
        wardrobe:     User's wardrobe dict.
        prev_session: The session dict from the previous turn, or None. When
                      provided, the agent can treat short queries like "show me
                      another", "anything cheaper?", or "style it differently"
                      as follow-ups that reuse the previous search results
                      instead of running a brand-new search (conversation
                      memory). Defaults to None → behaves exactly like a fresh,
                      single-turn run.

    Returns:
        The session dict after the turn. Check session["error"] first — if not
        None, the turn ended early and outfit_suggestion / fit_card are None.
        session["trace"] holds a human-readable log of every decision made.
    """
    intent = _detect_followup(query, prev_session)
    if intent:
        return _run_followup(intent, query, wardrobe, prev_session)

    # ── fresh search ──────────────────────────────────────────────────────────
    session = _new_session(query, wardrobe)
    session["turn"] = "search"

    # Step 2: parse the query into search parameters.
    session["parsed"] = _parse_query(query)
    p = session["parsed"]
    _log(session, f"🔎 New search — parsed: desc='{p['description']}', "
                  f"size={p['size']}, max_price={p['max_price']}")

    # Step 3: search. Branch on the result.
    session["search_results"] = search_listings(
        p["description"], p["size"], p["max_price"]
    )
    _log(session, f"→ search_listings returned {len(session['search_results'])} match(es)")

    # Fallback (stretch): if empty AND a size was set, retry without the size.
    if not session["search_results"] and p["size"]:
        _log(session, f"↻ Empty in size {p['size']} — retrying without the size filter")
        retried = search_listings(p["description"], None, p["max_price"])
        if retried:
            session["search_results"] = retried
            session["retry_note"] = (
                f"No exact match in size {p['size']}, so I dropped the size "
                "filter and searched everything in your budget."
            )
            _log(session, f"→ retry returned {len(retried)} match(es)")

    # Still empty -> set error and return early. Do NOT call the other tools.
    if not session["search_results"]:
        bits = [f"'{p['description']}'"]
        if p["size"]:
            bits.append(f"size {p['size']}")
        if p["max_price"] is not None:
            bits.append(f"under ${p['max_price']:g}")
        session["error"] = (
            f"No listings matched {', '.join(bits)}. Try removing the size "
            "filter, raising your budget, or describing the item differently."
        )
        _log(session, "⚠️ No matches → set error, STOPPED before suggest_outfit")
        return session

    # Step 4: select the top (most relevant) result.
    session["result_index"] = 0
    session["selected_item"] = session["search_results"][0]
    item = session["selected_item"]
    _log(session, f"✓ Selected top match: '{item['title']}' "
                  f"(${item['price']:g}, {item['platform']})")

    # Steps 5–7: style, caption, price-check.
    return _style_and_card(session)


# ── follow-up turns (reuse previous results, no new search) ─────────────────────

def _carry_forward(query: str, wardrobe: dict, prev: dict, turn: str) -> dict:
    """Build a fresh session that inherits the previous turn's search results."""
    session = _new_session(query, wardrobe)
    session["turn"] = turn
    session["parsed"] = prev.get("parsed", {})
    session["search_results"] = prev["search_results"]
    session["result_index"] = prev.get("result_index", 0)
    session["selected_item"] = prev.get("selected_item")
    return session


def _run_followup(intent: str, query: str, wardrobe: dict, prev: dict) -> dict:
    """
    Handle a conversational follow-up using the previous session's results.
    No new search_listings call is made — this is the conversation-memory path.
    """
    session = _carry_forward(query, wardrobe, prev, intent)
    results = session["search_results"]

    if intent == "restyle":
        _log(session, f"🔁 Follow-up 'restyle' — same item, regenerating the outfit "
                      f"(reusing {len(results)} prior results, no new search)")
        return _style_and_card(session)

    if intent == "cheaper":
        cur = prev["selected_item"]
        cur_price = cur["price"]
        # Prefer a cheaper item in the SAME category; fall back to any cheaper.
        same_cat = [it for it in results
                    if it["price"] < cur_price and it["category"] == cur["category"]]
        pool = same_cat or [it for it in results if it["price"] < cur_price]
        cheaper = sorted(pool, key=lambda it: it["price"])
        if not cheaper:
            session["selected_item"] = prev["selected_item"]
            session["error"] = (
                f"That was already the cheapest match at ${cur_price:g}. "
                "Try a fresh search with a lower budget."
            )
            _log(session, "🔁 Follow-up 'cheaper' — nothing below current price → kept item, set note")
            return session
        session["selected_item"] = cheaper[0]
        session["result_index"] = results.index(cheaper[0])
        _log(session, f"🔁 Follow-up 'cheaper' — picked '{cheaper[0]['title']}' "
                      f"(${cheaper[0]['price']:g} < ${cur_price:g}), no new search")
        return _style_and_card(session)

    # intent == "next": advance to the next item in the prior results.
    new_index = prev.get("result_index", 0) + 1
    if new_index >= len(results):
        session["selected_item"] = prev["selected_item"]
        session["error"] = (
            f"That's all {len(results)} matches for this search. "
            "Try describing something new to search again."
        )
        _log(session, "🔁 Follow-up 'next' — no more results → kept last item, set note")
        return session
    session["result_index"] = new_index
    session["selected_item"] = results[new_index]
    item = session["selected_item"]
    _log(session, f"🔁 Follow-up 'next' — showing #{new_index + 1} of {len(results)}: "
                  f"'{item['title']}' (${item['price']:g}), no new search")
    return _style_and_card(session)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    def show(s):
        print("  trace:")
        for line in s["trace"]:
            print(f"    {line}")
        if s["error"]:
            print(f"  error: {s['error']}")
        else:
            print(f"  item:  {s['selected_item']['title']} (${s['selected_item']['price']:g})")
            print(f"  card:  {s['fit_card'][:120]}...")

    print("=== Turn 1: fresh search ===")
    s1 = run_agent("looking for a vintage graphic tee under $30", get_example_wardrobe())
    show(s1)

    print("\n=== Turn 2: follow-up 'show me another' (conversation memory) ===")
    s2 = run_agent("show me another one", get_example_wardrobe(), prev_session=s1)
    show(s2)

    print("\n=== Turn 3: follow-up 'anything cheaper?' ===")
    s3 = run_agent("anything cheaper?", get_example_wardrobe(), prev_session=s2)
    show(s3)

    print("\n=== No-results path ===")
    s4 = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    show(s4)
