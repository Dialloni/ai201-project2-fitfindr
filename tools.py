"""
tools.py

The SecondLook tools. Each tool is a standalone function that can be called and
tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  -> list[dict]
    suggest_outfit(new_item, wardrobe)             -> str
    create_fit_card(outfit, new_item)              -> str
    compare_price(item)                            -> str   (stretch)
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

_MODEL = "llama-3.3-70b-versatile"

# Short, generic words that should not count toward relevance scoring.
_STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "in", "of", "to", "my",
    "looking", "want", "need", "size", "under", "below", "cheap", "some",
    "im", "i", "is", "are", "that", "this", "it", "good", "nice",
}


# -- Groq client ---------------------------------------------------------------

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _llm(messages: list[dict], temperature: float = 0.7, max_tokens: int = 400) -> str:
    """Single helper around the Groq chat completion call."""
    client = _get_groq_client()
    resp = client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens, stopwords removed."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


# -- Tool 1: search_listings ---------------------------------------------------

def _size_matches(query_size: str, listing_size: str) -> bool:
    """Token-aware, case-insensitive size match. 'M' matches 'S/M', 'M/L'."""
    if not query_size:
        return True
    q = query_size.strip().lower()
    listing = (listing_size or "").lower()
    # Split listing size on non-alphanumeric to get its size tokens.
    tokens = re.split(r"[^a-z0-9]+", listing)
    return q in tokens or q == listing or q in listing.split()


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Returns a list of matching listing dicts sorted by relevance (best first),
    or [] if nothing matches. Never raises.
    """
    try:
        listings = load_listings()
    except Exception:
        # Data file unreadable -> behave like "no matches" rather than crash.
        return []

    query_tokens = _tokenize(description)
    results = []

    for item in listings:
        # 1. Hard filters first.
        if max_price is not None and item.get("price", 0) > max_price:
            continue
        if size and not _size_matches(size, item.get("size", "")):
            continue

        # 2. Score by keyword overlap across the searchable text fields.
        haystack = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
            item.get("brand") or "",
            item.get("category", ""),
        ])
        hay_tokens = set(_tokenize(haystack))

        score = 0
        for qt in query_tokens:
            if qt in hay_tokens:
                # Title / tag hits are worth more than body hits.
                weight = 2 if qt in _tokenize(item.get("title", "")) \
                    or qt in [t.lower() for t in item.get("style_tags", [])] else 1
                score += weight

        # No description given -> filters alone qualify the item.
        if not query_tokens:
            score = 1

        if score > 0:
            results.append((score, item))

    results.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in results]


# -- Tool 2: suggest_outfit ----------------------------------------------------

def _format_wardrobe(wardrobe: dict) -> str:
    lines = []
    for it in wardrobe.get("items", []):
        tags = ", ".join(it.get("style_tags", []))
        note = f" ({it['notes']})" if it.get("notes") else ""
        lines.append(f"- {it['name']} [{it.get('category', '')}; {tags}]{note}")
    return "\n".join(lines)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1-2 complete outfits.
    Empty wardrobe -> general styling advice. Never raises.
    """
    if not isinstance(new_item, dict) or not new_item.get("title"):
        return "Can't suggest an outfit — no valid item was provided."

    item_desc = (
        f"{new_item.get('title')} "
        f"({new_item.get('category', 'item')}; "
        f"{', '.join(new_item.get('style_tags', []))}; "
        f"colors: {', '.join(new_item.get('colors', []))})"
    )
    items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []

    try:
        if not items:
            # Empty-wardrobe path: general styling advice.
            messages = [
                {"role": "system", "content":
                    "You are a thrift-savvy stylist. Be concrete and concise."},
                {"role": "user", "content":
                    f"A shopper is considering this secondhand piece:\n{item_desc}\n\n"
                    "They have no wardrobe entered yet. Suggest one or two complete "
                    "outfit directions: what kinds of pieces to pair it with, what "
                    "vibe it suits, and one specific styling tip. 4-6 sentences."},
            ]
        else:
            # Wardrobe path: pair with named owned pieces.
            messages = [
                {"role": "system", "content":
                    "You are a thrift-savvy stylist. Use ONLY the pieces listed. "
                    "Name specific pieces. Be concrete and concise."},
                {"role": "user", "content":
                    f"New secondhand piece:\n{item_desc}\n\n"
                    f"The shopper's current wardrobe:\n{_format_wardrobe(wardrobe)}\n\n"
                    "Suggest one or two complete outfits using this new piece plus "
                    "named pieces from their wardrobe. Add a specific styling tip "
                    "(tuck, roll, layer). 4-6 sentences."},
            ]
        return _llm(messages, temperature=0.7)
    except Exception:
        return (
            "Couldn't generate a custom outfit right now, but this piece pairs "
            "well with neutral basics — think straight-leg denim and clean "
            "sneakers for an easy everyday look."
        )


# -- Tool 3: create_fit_card ---------------------------------------------------

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable OOTD-style caption. Empty outfit -> error string.
    Never raises.
    """
    if not outfit or not outfit.strip():
        return ("Can't create a fit card — no outfit was provided. Run "
                "suggest_outfit first so there's a look to caption.")
    if not isinstance(new_item, dict) or not new_item.get("title"):
        return "Can't create a fit card — the item details are missing."

    title = new_item.get("title", "this piece")
    price = new_item.get("price")
    platform = new_item.get("platform", "")
    price_str = f"${price:g}" if isinstance(price, (int, float)) else "a steal"

    try:
        messages = [
            {"role": "system", "content":
                "You write short, casual OOTD captions for thrift finds. "
                "Sound like a real person, not a product listing. No hashtag spam."},
            {"role": "user", "content":
                f"Item: {title}\nPrice: {price_str}\nPlatform: {platform}\n"
                f"Outfit: {outfit}\n\n"
                "Write a 2-4 sentence caption for an Instagram/TikTok OOTD post. "
                "Mention the item, price, and platform once each, naturally. "
                "Capture the outfit's vibe in specific terms. Casual voice, "
                "1-2 emojis max."},
        ]
        # High temperature -> output varies across runs / inputs.
        return _llm(messages, temperature=1.0, max_tokens=200)
    except Exception:
        # Templated fallback so the agent still returns something usable.
        plat = f" off {platform}" if platform else ""
        return (f"thrifted this {title.lower()} for {price_str}{plat} and it's "
                f"already my favorite. full look coming to stories ✨")


# -- Tool 4: compare_price (stretch) -------------------------------------------

def compare_price(item: dict) -> str:
    """
    Estimate whether an item's price is fair vs. the median for its category.
    Never raises.
    """
    if not isinstance(item, dict) or item.get("price") is None:
        return "Not enough info to judge the price."
    try:
        listings = load_listings()
    except Exception:
        return "Couldn't load comparable listings to judge the price."

    category = item.get("category")
    price = item["price"]
    prices = sorted(
        l["price"] for l in listings
        if l.get("category") == category and l.get("id") != item.get("id")
        and isinstance(l.get("price"), (int, float))
    )
    if not prices:
        return "Not enough comparable listings to judge whether the price is fair."

    mid = len(prices) // 2
    median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2

    cat = category or "this category"
    if price <= median * 0.85:
        verdict = "a good deal — below"
    elif price <= median * 1.15:
        verdict = "about fair — right around"
    else:
        verdict = "on the pricey side — above"
    return f"${price:g} is {verdict} the ${median:g} median for {cat}."


# -- Manual smoke test ---------------------------------------------------------

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    res = search_listings("vintage graphic tee", size=None, max_price=50)
    print(f"search -> {len(res)} results; top: {res[0]['title'] if res else 'none'}")
    if res:
        print("\noutfit ->", suggest_outfit(res[0], get_example_wardrobe())[:200])
        print("\nfit card ->", create_fit_card("pair with baggy jeans", res[0])[:200])
        print("\nprice ->", compare_price(res[0]))
