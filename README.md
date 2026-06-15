# SecondLook 🛍️

*Give secondhand a second look.*

A multi-tool AI agent that helps you find secondhand pieces and figure out how
to wear them. Describe what you want in plain language — SecondLook searches mock
listings, styles the find against your wardrobe, and writes a shareable fit card,
recovering gracefully when a tool returns nothing.

## 🎬 Demo Video

[Watch the demo on Loom](https://www.loom.com/share/b07d5d9853b748b487aa4f5f7a3144d7) — a full multi-step interaction (all three tools), visible state passing, conversation-memory follow-ups, and a triggered failure with the agent's graceful response.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Add your Groq key to a `.env` file in the repo root (free at
[console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Run

```bash
python app.py          # Gradio UI at http://localhost:7860
python agent.py        # CLI: happy path + no-results path
pytest tests/          # 15 tests (LLM tests auto-skip without a key)
```

---

## Tool Inventory

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `search_listings` | `description (str)`, `size (str \| None)`, `max_price (float \| None)` | `list[dict]` of listing dicts sorted by relevance, or `[]` | Find listings matching keywords, filtered by size/price |
| `suggest_outfit` | `new_item (dict)`, `wardrobe (dict)` | `str` outfit suggestion | Style the item against owned pieces (or general advice if wardrobe empty) |
| `create_fit_card` | `outfit (str)`, `new_item (dict)` | `str` caption | Write a casual, shareable OOTD caption |
| `compare_price` *(stretch)* | `item (dict)` | `str` verdict | Judge if the price is fair vs. the category median |

Each listing dict contains: `id, title, description, category, style_tags,
size, condition, price, colors, brand, platform`. These signatures match the
functions in [tools.py](tools.py) exactly.

### search_listings
Hard-filters by `max_price` and `size` (token-aware: `"M"` matches `"S/M"`,
`"M/L"`), then scores remaining listings by keyword overlap with `description`
across title, description, style_tags, colors, brand, and category — title/tag
hits weighted double. Drops zero-score items; sorts highest-score first.

### suggest_outfit
Two prompt paths. With a wardrobe, the LLM is constrained to pair the new item
with the user's *named* pieces plus a styling tip. With an empty wardrobe, it
returns general styling directions instead.

### create_fit_card
Guards an empty outfit before any LLM call. Runs at temperature `1.0` so the
caption varies across runs and inputs (verified by `test_fit_card_varies`).

---

## How the Planning Loop Works

`run_agent(query, wardrobe, prev_session=None)` in [agent.py](agent.py) runs a
pipeline with **two top-level branches** (fresh search vs. conversational
follow-up) and a **conditional early exit** — it does *not* call all tools
unconditionally.

**Branch 0 — follow-up detection.** `_detect_followup()` checks whether there's a
previous session with results and the query is a follow-up
("another"/"cheaper"/"style it differently"). If so, the agent **reuses the prior
`search_results` and skips `search_listings` entirely** (see Conversation Memory
below). Otherwise it runs a fresh search:

1. **Parse** — `_parse_query()` uses regex to pull `description`, `size`, and
   `max_price` out of the query, stripping the size/price phrases so they don't
   pollute the keywords.
2. **Search** — call `search_listings`. **Branch on the result:**
   - If `[]` **and** a size was parsed → **retry once** with `size=None` and
     record the adjustment in `session["retry_note"]` *(stretch: retry+fallback)*.
   - If still `[]` → set `session["error"]` with what was searched and what to
     try, and **return early**. `suggest_outfit` and `create_fit_card` are never
     called on empty input.
3. **Select** — `session["selected_item"] = search_results[result_index]`.
4. **Suggest** — `suggest_outfit(selected_item, wardrobe)`.
5. **Fit card** — `create_fit_card(outfit_suggestion, selected_item)`.
6. **Price check** *(stretch)* — `compare_price(selected_item)`.

The agent's behavior changes with the input: an impossible query terminates at
step 2 with an error; a follow-up skips search; a fresh valid query flows through
all tools. Every decision is appended to `session["trace"]` (see Reasoning Trace).

### Conversation Memory (multi-turn)

The Gradio UI keeps the previous turn's session in a `gr.State`, passed back as
`prev_session`. Follow-ups reuse it with **no new search**:

| You say | Agent does |
|---------|-----------|
| "show me another one" | advances `result_index` to the next match |
| "anything cheaper?" | picks the next-cheapest match (same category first) |
| "style it differently" | keeps the item, regenerates the outfit + fit card |

End-of-list / nothing-cheaper cases set a friendly note instead of crashing.

### Reasoning Trace (planning loop, visible)

Each turn logs its decisions to `session["trace"]`, rendered in the **"🧠 What the
agent did"** panel — e.g. `→ search_listings returned 12 match(es)`,
`✓ Selected top match`, `🔁 Follow-up 'cheaper' — picked '…' ($15 < $30), no new
search`, `⚠️ No matches → STOPPED before suggest_outfit`. This makes the planning
loop observable rather than a black box.

## State Management

A single `session` dict (created by `_new_session`) is the source of truth for
one interaction. Each step reads earlier fields and writes its own:

- `parsed` ← parse step → read by `search_listings`
- `search_results` / `result_index` ← search → read by the early-exit check, item selection, and follow-ups
- `selected_item` ← chosen result → **flows into** `suggest_outfit`, `create_fit_card`, `compare_price`
- `outfit_suggestion` ← `suggest_outfit` → **flows into** `create_fit_card`
- `fit_card`, `price_check`, `retry_note`, `error` ← set by their steps → read by `app.py`
- `trace` ← appended at every decision → rendered in the reasoning panel

The item found by `search_listings` reaches `suggest_outfit` through
`session["selected_item"]` — the user never re-enters it. `app.py` reads the
final session and maps fields to the four panels. **Across turns**, the whole
session dict is held in a `gr.State` and passed back as `prev_session`, which is
how conversation memory works.

## Error Handling (per tool)

| Tool | Failure mode | What the agent does |
|------|-------------|---------------------|
| `search_listings` | No match | Returns `[]` (never raises). Loop retries once without the size filter; if still empty, sets a specific `error` and stops. |
| `suggest_outfit` | Empty wardrobe | Switches to a general-advice prompt and returns concrete styling directions. LLM exception → neutral-basics fallback string. |
| `create_fit_card` | Empty/whitespace outfit | Returns a descriptive error string with no LLM call. LLM exception → templated caption built from item fields. |
| `compare_price` | No comparable listings | Returns a neutral "not enough comparable listings" message. |

**Concrete example from testing** — running the no-results query:

```
$ python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
[]
```

The full agent on the same query returns:

> ⚠️ No listings matched 'designer ballgown', size XXS, under $5. Try removing
> the size filter, raising your budget, or describing the item differently.

…and `session["fit_card"]` stays `None` — `suggest_outfit` is never reached.

---

## Spec Reflection

- **How the spec helped:** writing the Planning Loop section in `planning.md` as
  explicit branches ("if `[]` and size set → retry; if still `[]` → error and
  return early") meant `run_agent` was a near-direct translation — the early-exit
  logic was decided before any code.
- **Where implementation diverged:** the spec treated size matching as a simple
  case-insensitive compare. The real data has messy sizes (`"S/M"`, `"W30 L30"`,
  `"US 8"`), so I added token-aware matching (`_size_matches`) — otherwise a
  query for size `M` would miss every `S/M` listing. The retry-with-fallback
  stretch was added partly to cover the remaining mismatches.

## AI Usage

1. **`search_listings` implementation** — I gave Claude the Tool 1 block from
   `planning.md` (inputs, return type, failure mode) plus the listings field
   list, and asked it to implement the function using `load_listings()`. Claude's
   first version did a plain `size.lower() == listing_size.lower()` compare; I
   **overrode** it with token-aware matching after seeing it returned zero
   results for size `M` against `S/M` listings, and added the stopword-filtered
   keyword scoring so generic words like "looking"/"for" didn't inflate scores.

2. **Planning loop** — I gave Claude the Architecture diagram + Planning Loop and
   State Management sections and asked for `run_agent`. The generated version
   called `suggest_outfit` even when search returned `[]`; I **revised** it to
   return early on the empty branch and added the size-drop retry (`retry_note`)
   that wasn't in the first draft, then verified with `python agent.py` that the
   no-results path leaves `fit_card = None`.

3. **Conversation memory** — I asked Claude to add multi-turn follow-ups reusing a
   prior session. Its first "cheaper" branch picked the globally cheapest match,
   which jumped from a tee to a beret; I **overrode** it to prefer the same
   category first, and kept `run_agent`'s old two-arg signature working by making
   `prev_session` optional so existing tests/callers were unaffected.

## Stretch Features & Extras

- **Price comparison** — `compare_price` judges a find against the category median.
- **Retry with fallback** — empty search + a size filter → auto-retry without the
  size, with the adjustment surfaced to the user.
- **Conversation memory (multi-turn)** — the agent remembers the last search and
  handles "another", "cheaper", and "style it differently" follow-ups without
  re-searching, via a `gr.State` session passed between turns.
- **Visible reasoning trace** — every planning-loop decision is logged and shown
  in a dedicated UI panel.
- **100-item dataset** across all five categories (clothes, shoes, eyeglasses,
  hats, bags, accessories), generated by [scripts/generate_listings.py](scripts/generate_listings.py).
