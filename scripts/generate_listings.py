"""
generate_listings.py

Generates a balanced 100-item mock listings dataset (~20 per category) with
realistic, varied titles, tags, sizes, prices, colors, brands, and platforms.

Deterministic (seeded) so the dataset is reproducible. Guarantees the items the
test suite searches for (vintage graphic tee, denim jacket, jackets under $40,
size-M tops) are present.

Run from the project root:
    python scripts/generate_listings.py
"""

import json
import os
import random

random.seed(7)

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "listings.json")

PLATFORMS = ["depop", "thredUp", "poshmark"]
CONDITIONS = ["excellent", "good", "fair"]
CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "S/M", "M/L", "L/XL", "One Size"]
WAIST_SIZES = ["W27", "W28", "W29", "W30", "W31", "W32", "W34", "S", "M", "L"]
SHOE_SIZES = ["US 6", "US 7", "US 8", "US 8.5", "US 9", "US 10", "US 11"]
ONE_SIZE = ["One Size", "One Size (adjustable)"]

# Each entry: (title, [style_tags], (min_price, max_price), [colors_pool], brand)
# One item is produced per type -> 20 types per category = 20 items each.
TYPES = {
    "tops": [
        ("Vintage Graphic Tee", ["vintage", "graphic", "streetwear", "retro"], (16, 32), ["black", "white", "faded blue"], None),
        ("Band Tee — Tour Bootleg", ["vintage", "graphic", "grunge", "streetwear"], (20, 38), ["black", "charcoal"], None),
        ("Ringer Tee — Striped Trim", ["retro", "y2k", "basics"], (14, 24), ["white", "red", "navy"], None),
        ("Cropped Baby Tee", ["y2k", "fitted", "cropped"], (12, 22), ["pink", "white", "baby blue"], None),
        ("Oversized Crewneck Sweatshirt", ["oversized", "basics", "cozy", "streetwear"], (18, 36), ["grey", "cream", "black"], None),
        ("Zip-Up Hoodie — Faded", ["streetwear", "athletic", "cozy"], (22, 42), ["black", "olive", "grey"], None),
        ("Chunky Knit Sweater", ["cozy", "cottagecore", "earth tones"], (24, 46), ["cream", "brown", "sage"], None),
        ("Ribbed Tank Top", ["basics", "minimal", "fitted"], (8, 18), ["white", "black", "grey"], None),
        ("Flannel Button-Up", ["grunge", "classic", "cozy"], (18, 34), ["red", "green", "blue"], None),
        ("Oxford Shirt — Crisp Cotton", ["preppy", "minimal", "classic"], (16, 30), ["white", "light blue"], None),
        ("Turtleneck — Fine Knit", ["minimal", "classic", "basics"], (16, 28), ["black", "cream", "rust"], None),
        ("Polo Shirt — Pique", ["preppy", "retro", "classic"], (14, 26), ["navy", "green", "white"], None),
        ("Henley Long Sleeve", ["basics", "minimal", "earth tones"], (14, 26), ["oatmeal", "charcoal"], None),
        ("Mock Neck Top", ["minimal", "y2k", "fitted"], (12, 24), ["black", "chocolate"], None),
        ("Cardigan — Button Front", ["cottagecore", "cozy", "vintage"], (22, 40), ["cream", "pink", "sage"], None),
        ("Mesh Long Sleeve", ["y2k", "grunge", "going-out"], (12, 22), ["black", "silver"], None),
        ("Sweater Vest — Argyle", ["preppy", "y2k", "retro"], (16, 30), ["brown", "navy", "cream"], None),
        ("Halter Top — Satin", ["y2k", "glam", "going-out"], (14, 26), ["black", "emerald", "red"], None),
        ("Tie-Dye Long Sleeve", ["tie-dye", "cottagecore", "colorful"], (14, 24), ["pink", "lavender", "mint"], None),
        ("Jersey Tee — Numbered", ["streetwear", "athletic", "y2k"], (16, 30), ["white", "red", "blue"], None),
    ],
    "bottoms": [
        ("Vintage Levi's Straight Jeans", ["vintage", "denim", "classic", "streetwear"], (28, 52), ["blue", "indigo"], "Levi's"),
        ("Baggy Carpenter Jeans", ["baggy", "denim", "streetwear", "y2k"], (26, 46), ["light blue", "washed"], None),
        ("Wide-Leg Trousers", ["minimal", "wide-leg", "earth tones"], (24, 44), ["khaki", "black", "cream"], None),
        ("Cargo Pants — Utility", ["streetwear", "y2k", "utility"], (24, 42), ["olive", "tan", "black"], None),
        ("Pleated Mini Skirt", ["preppy", "y2k", "school"], (16, 30), ["plaid", "black", "navy"], None),
        ("Flowy Midi Skirt", ["cottagecore", "minimal", "flowy"], (18, 38), ["floral", "cream", "sage"], None),
        ("High-Waisted Denim Shorts", ["denim", "vintage", "summer"], (16, 30), ["blue", "white"], None),
        ("Corduroy Pants — Wide Wale", ["retro", "earth tones", "cozy"], (20, 38), ["brown", "rust", "olive"], None),
        ("Pleated Chinos", ["preppy", "minimal", "classic"], (18, 34), ["beige", "navy"], None),
        ("Flare Jeans — High Rise", ["y2k", "denim", "retro"], (24, 44), ["medium blue", "dark wash"], None),
        ("Mom Jeans — Light Wash", ["vintage", "denim", "minimal"], (24, 42), ["light blue"], None),
        ("Sweatpants — Vintage Fleece", ["athletic", "cozy", "streetwear"], (16, 30), ["grey", "navy", "black"], None),
        ("Track Pants — Side Stripe", ["athletic", "y2k", "streetwear"], (18, 34), ["black", "navy"], None),
        ("Linen Trousers", ["minimal", "summer", "earth tones"], (20, 38), ["white", "tan"], None),
        ("Denim Overalls", ["vintage", "denim", "cottagecore"], (28, 50), ["blue", "indigo"], None),
        ("Pleated Maxi Skirt", ["minimal", "flowy", "elegant"], (22, 42), ["black", "charcoal"], None),
        ("Plaid Mini Skirt", ["grunge", "y2k", "school"], (16, 28), ["red plaid", "green plaid"], None),
        ("Culottes — Cropped Wide", ["minimal", "earth tones", "wide-leg"], (18, 32), ["olive", "cream"], None),
        ("Leather Mini Skirt", ["grunge", "glam", "going-out"], (22, 40), ["black"], None),
        ("Capri Pants", ["y2k", "retro", "minimal"], (14, 26), ["khaki", "white"], None),
    ],
    "outerwear": [
        ("Vintage Denim Jacket", ["vintage", "denim", "classic", "streetwear"], (24, 38), ["blue", "black"], None),
        ("Leather Moto Jacket", ["grunge", "classic", "edgy"], (38, 80), ["black", "brown"], None),
        ("Bomber Jacket — Nylon", ["streetwear", "y2k", "athletic"], (24, 40), ["black", "olive", "navy"], None),
        ("Trench Coat — Belted", ["classic", "minimal", "elegant"], (32, 60), ["tan", "khaki", "black"], None),
        ("Puffer Jacket — Cropped", ["streetwear", "cozy", "y2k"], (28, 48), ["black", "silver", "pink"], None),
        ("Windbreaker — Color Block", ["athletic", "retro", "y2k"], (18, 34), ["teal", "purple", "white"], None),
        ("Oversized Blazer", ["minimal", "preppy", "classic"], (22, 38), ["black", "grey", "camel"], None),
        ("Wool Peacoat", ["classic", "minimal", "cozy"], (30, 55), ["navy", "charcoal"], None),
        ("Corduroy Shacket", ["earth tones", "cozy", "retro"], (22, 36), ["brown", "olive"], None),
        ("Varsity Jacket — Wool & Leather", ["retro", "preppy", "vintage"], (30, 58), ["navy", "cream"], None),
        ("Fleece Zip Pullover", ["cozy", "athletic", "streetwear"], (16, 30), ["beige", "grey", "green"], None),
        ("Quilted Liner Jacket", ["minimal", "earth tones", "cozy"], (20, 36), ["olive", "black"], None),
        ("Anorak — Packable", ["athletic", "minimal", "streetwear"], (18, 34), ["yellow", "black"], None),
        ("Faux Shearling Coat", ["cozy", "y2k", "glam"], (28, 50), ["cream", "brown"], None),
        ("Denim Trucker — Sherpa Lined", ["vintage", "denim", "cozy"], (28, 44), ["blue", "black"], None),
        ("Track Jacket — Retro Stripes", ["athletic", "y2k", "streetwear"], (18, 34), ["red", "navy", "white"], None),
        ("Duster Coat — Longline", ["minimal", "elegant", "earth tones"], (26, 46), ["camel", "grey"], None),
        ("Cropped Denim Jacket", ["vintage", "denim", "y2k"], (22, 36), ["light blue", "white"], None),
        ("Raincoat — Glossy", ["minimal", "retro", "utility"], (20, 36), ["yellow", "black", "red"], None),
        ("Cardigan Coat — Chunky Knit", ["cozy", "cottagecore", "earth tones"], (24, 40), ["oatmeal", "brown"], None),
    ],
    "shoes": [
        ("Low-Top Canvas Sneakers", ["classic", "streetwear", "basics"], (20, 38), ["white", "black", "red"], None),
        ("High-Top Canvas Sneakers", ["classic", "streetwear", "retro"], (24, 42), ["red", "black", "white"], None),
        ("Platform Sneakers — Chunky Sole", ["y2k", "streetwear", "chunky"], (28, 50), ["white", "black"], None),
        ("Suede Chelsea Boots", ["minimal", "classic", "earth tones"], (30, 60), ["tan", "brown", "black"], None),
        ("Combat Boots — Lace Up", ["grunge", "classic", "edgy"], (32, 62), ["black"], None),
        ("Platform Mary Janes", ["y2k", "grunge", "school"], (26, 48), ["black", "burgundy"], None),
        ("Penny Loafers — Leather", ["preppy", "classic", "minimal"], (24, 46), ["brown", "black"], None),
        ("Ballet Flats — Pointed", ["minimal", "elegant", "y2k"], (16, 34), ["black", "nude", "red"], None),
        ("Shearling Slippers", ["cozy", "minimal", "everyday"], (16, 30), ["tan", "grey"], None),
        ("Strappy Sandals — Flat", ["minimal", "summer", "everyday"], (14, 30), ["tan", "black"], None),
        ("Derby Shoes — Brogue", ["preppy", "classic", "vintage"], (26, 50), ["brown", "oxblood"], None),
        ("Running Sneakers — Retro", ["athletic", "y2k", "streetwear"], (26, 48), ["grey", "silver", "blue"], None),
        ("Ankle Boots — Heeled", ["minimal", "classic", "going-out"], (28, 54), ["black", "brown"], None),
        ("Clogs — Suede", ["retro", "earth tones", "cozy"], (22, 42), ["tan", "brown"], None),
        ("Espadrilles — Woven", ["summer", "minimal", "earth tones"], (16, 32), ["natural", "navy"], None),
        ("Knee-High Boots — Leather", ["y2k", "glam", "going-out"], (34, 66), ["black", "brown"], None),
        ("Skate Shoes — Suede", ["streetwear", "y2k", "athletic"], (24, 44), ["black", "grey"], None),
        ("Slip-On Sneakers", ["minimal", "basics", "everyday"], (18, 34), ["white", "black", "checkered"], None),
        ("Wedge Sandals", ["summer", "retro", "going-out"], (20, 40), ["tan", "black"], None),
        ("Knit House Slippers", ["cozy", "basics", "minimal"], (10, 22), ["grey", "cream"], None),
    ],
    "accessories": [
        ("Round Wire Eyeglasses", ["vintage", "minimal", "retro"], (16, 30), ["gold", "silver"], None),
        ("Tortoiseshell Square Glasses", ["y2k", "retro", "academic"], (16, 28), ["brown", "amber"], None),
        ("Oversized Sunglasses", ["y2k", "glam", "retro"], (12, 26), ["black", "tortoise"], None),
        ("Baseball Cap — Washed Cotton", ["streetwear", "minimal", "everyday"], (8, 18), ["black", "navy", "beige"], None),
        ("Bucket Hat — Reversible", ["y2k", "streetwear", "colorful"], (12, 24), ["plaid", "khaki", "black"], None),
        ("Corduroy Dad Cap", ["earth tones", "cozy", "retro"], (10, 20), ["green", "brown", "rust"], None),
        ("Ribbed Beanie", ["cozy", "basics", "streetwear"], (8, 16), ["cream", "black", "grey"], None),
        ("Wool Beret", ["vintage", "elegant", "cottagecore"], (10, 20), ["black", "red", "camel"], None),
        ("Silk Scarf — Floral", ["vintage", "cottagecore", "colorful"], (10, 22), ["rust", "cream", "green"], None),
        ("Braided Leather Belt", ["classic", "earth tones", "minimal"], (12, 26), ["brown", "tan"], None),
        ("Studded Belt", ["grunge", "y2k", "edgy"], (12, 24), ["black"], None),
        ("Mini Shoulder Bag — Leather", ["minimal", "y2k", "everyday"], (22, 44), ["tan", "black", "brown"], None),
        ("Canvas Tote Bag", ["minimal", "basics", "everyday"], (8, 18), ["natural", "black"], None),
        ("Mini Backpack", ["y2k", "streetwear", "everyday"], (18, 36), ["black", "pink"], None),
        ("Crossbody Wallet — Chain", ["minimal", "everyday", "classic"], (18, 34), ["black", "brown"], None),
        ("Fingerless Gloves — Knit", ["grunge", "streetwear", "cozy"], (8, 16), ["black", "grey"], None),
        ("Layered Necklace Set", ["minimal", "y2k", "glam"], (10, 24), ["gold", "silver"], None),
        ("Hair Clips Set — Claw", ["y2k", "colorful", "everyday"], (6, 14), ["tortoise", "pearl", "neon"], None),
        ("Vintage Wristwatch", ["vintage", "classic", "minimal"], (24, 60), ["gold", "silver"], None),
        ("Fanny Pack — Nylon", ["streetwear", "y2k", "utility"], (12, 26), ["black", "olive"], None),
    ],
}


def pick_sizes(category):
    if category == "bottoms":
        return WAIST_SIZES
    if category == "shoes":
        return SHOE_SIZES
    if category == "accessories":
        return ONE_SIZE
    return CLOTHING_SIZES


def make_description(title, tags, colors):
    cond_phrases = {
        "excellent": "Barely worn, no flaws.",
        "good": "Light wear, plenty of life left.",
        "fair": "Visible wear that adds character.",
    }
    vibe = ", ".join(tags[:2])
    color = colors[0]
    return (f"{title} in {color}. {vibe.capitalize()} vibe. "
            "A solid secondhand find for everyday rotation.")


def main():
    listings = []
    n = 1
    for category, types in TYPES.items():
        sizes = pick_sizes(category)
        for title, tags, (lo, hi), colors, brand in types:
            price = round(random.uniform(lo, hi))
            # keep a small share at .50 to look natural
            if random.random() < 0.3:
                price = price - 0.0 + 0.5
            chosen_colors = random.sample(colors, k=min(len(colors), random.choice([1, 2])))
            item = {
                "id": f"lst_{n:03d}",
                "title": title,
                "description": make_description(title, tags, chosen_colors),
                "category": category,
                "style_tags": tags,
                "size": random.choice(sizes),
                "condition": random.choice(CONDITIONS),
                "price": float(price),
                "colors": chosen_colors,
                "brand": brand,
                "platform": random.choice(PLATFORMS),
            }
            listings.append(item)
            n += 1

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2)
    print(f"Wrote {len(listings)} listings to {os.path.normpath(OUT)}")
    # quick category breakdown
    from collections import Counter
    print(dict(Counter(x["category"] for x in listings)))


if __name__ == "__main__":
    main()
