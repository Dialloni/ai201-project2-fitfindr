"""
app.py

Gradio interface for SecondLook. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def _format_trace(session: dict) -> str:
    """Turn the agent's decision log into the text for the reasoning panel."""
    header = {
        "search": "🧠 Agent reasoning (new search)",
        "next": "🧠 Agent reasoning (follow-up · reused memory)",
        "cheaper": "🧠 Agent reasoning (follow-up · reused memory)",
        "restyle": "🧠 Agent reasoning (follow-up · reused memory)",
    }.get(session.get("turn", "search"), "🧠 Agent reasoning")
    lines = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(session["trace"]))
    return f"{header}\n\n{lines}"


def handle_query(user_query: str, wardrobe_choice: str, prev_session: dict | None):
    """
    Called by Gradio when the user submits a query.

    Returns five values mapped to: the listing panel, outfit panel, fit-card
    panel, the reasoning panel, and the gr.State that carries this turn's
    session into the next turn (conversation memory).
    """
    # 1. Guard against an empty query — keep prior memory intact.
    if not user_query or not user_query.strip():
        return ("Please type what you're looking for first.", "", "",
                "🧠 Nothing to do — empty query.", prev_session)

    # 2. Select the wardrobe.
    if wardrobe_choice == "Empty wardrobe (new user)":
        wardrobe = get_empty_wardrobe()
    else:
        wardrobe = get_example_wardrobe()

    # 3. Run the agent, passing the previous turn's session for follow-ups.
    session = run_agent(user_query, wardrobe, prev_session=prev_session)
    reasoning = _format_trace(session)

    # 4. Error branch -> message in the first panel, others empty.
    #    Still return the session so follow-up context isn't lost.
    if session["error"]:
        return f"⚠️ {session['error']}", "", "", reasoning, session

    # 5. Map the session to the three panels.
    item = session["selected_item"]
    pos = ""
    if session["search_results"]:
        pos = f"  (match {session['result_index'] + 1} of {len(session['search_results'])})"
    listing_text = (
        f"{item['title']}{pos}\n"
        f"${item['price']:g} · {item.get('platform', '')} · "
        f"{item.get('condition', '')} condition\n"
        f"Size {item.get('size', 'n/a')} · {item.get('category', '')}\n\n"
        f"{item.get('description', '')}"
    )
    if session.get("retry_note"):
        listing_text = f"ℹ️ {session['retry_note']}\n\n" + listing_text
    if session.get("price_check"):
        listing_text += f"\n\n💰 {session['price_check']}"

    return (listing_text, session["outfit_suggestion"], session["fit_card"],
            reasoning, session)


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "denim jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots",
    "gold round eyeglasses",
    "show me another one",                   # follow-up (after a search)
    "anything cheaper?",                     # follow-up (after a search)
    "style it differently",                  # follow-up (after a search)
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="SecondLook") as demo:
        gr.Markdown("""
# SecondLook 🛍️
*Give secondhand a second look.* Find pieces and get outfit ideas based on your wardrobe.

Describe what you're looking for — include size and price to filter. After a result,
you can follow up conversationally: **"show me another"**, **"anything cheaper?"**, or
**"style it differently"** — the agent remembers your last search and reuses it.
        """)

        # Conversation memory: carries the previous turn's session between submits.
        session_state = gr.State(value=None)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        reasoning_output = gr.Textbox(
            label="🧠 What the agent did (planning loop trace)",
            lines=8,
            interactive=False,
        )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these (run a search first, then a follow-up)",
        )

        _outputs = [listing_output, outfit_output, fitcard_output,
                    reasoning_output, session_state]
        _inputs = [query_input, wardrobe_choice, session_state]

        submit_btn.click(fn=handle_query, inputs=_inputs, outputs=_outputs)
        query_input.submit(fn=handle_query, inputs=_inputs, outputs=_outputs)

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
