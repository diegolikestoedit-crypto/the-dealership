"""Item catalog, item instances and valuation rules for The Dealership."""
import itertools

CATEGORIES = {
    "electronics": {"name": "Electronics", "color": "#4fc3f7"},
    "watches": {"name": "Watches", "color": "#ffd54f"},
    "jewelry": {"name": "Jewelry", "color": "#f48fb1"},
    "antiques": {"name": "Antiques", "color": "#bcaaa4"},
    "collectibles": {"name": "Collectibles", "color": "#aed581"},
    "art": {"name": "Artwork", "color": "#ce93d8"},
    "instruments": {"name": "Instruments", "color": "#ffab91"},
    "furniture": {"name": "Furniture", "color": "#a1887f"},
    "historical": {"name": "Historical", "color": "#90a4ae"},
    "luxury": {"name": "Luxury Goods", "color": "#ffcc80"},
    "cars": {"name": "Vehicles", "color": "#ef5350"},
    "space": {"name": "Space Memorabilia", "color": "#80deea"},  # unlockable expansion
}
BASE_CATEGORIES = [c for c in CATEGORIES if c != "space"]

CONDITIONS = [
    # (key, label, multiplier)
    ("new", "Brand New", 1.25),
    ("excellent", "Excellent", 1.0),
    ("good", "Good", 0.8),
    ("used", "Used", 0.6),
    ("damaged", "Damaged", 0.35),
    ("broken", "Broken", 0.15),
]
COND_INDEX = {c[0]: i for i, c in enumerate(CONDITIONS)}
COND_MULT = [c[2] for c in CONDITIONS]
COND_LABEL = [c[1] for c in CONDITIONS]

# Edition tiers: index 0 standard .. 3 legendary
EDITION_MULT = [1.0, 1.7, 3.2, 6.5]
EDITION_NAMES = {
    "electronics": ["Standard", "Limited Edition", "Developer Unit", "Prototype"],
    "watches": ["Standard", "Limited Run", "Anniversary Edition", "Unique Piece"],
    "jewelry": ["Standard", "Designer Piece", "Royal Provenance", "Historic Gem"],
    "antiques": ["Standard", "Workshop Original", "Master Craftsman", "Museum Grade"],
    "collectibles": ["Standard", "First Print", "Error Variant", "One of a Kind"],
    "art": ["Print", "Signed", "Studio Original", "Lost Masterwork"],
    "instruments": ["Standard", "Custom Shop", "Tour Used", "Legend's Own"],
    "furniture": ["Standard", "Designer", "Signed Maker", "Palace Commission"],
    "historical": ["Standard", "Documented", "Expedition Piece", "National Treasure"],
    "luxury": ["Standard", "Limited Edition", "Atelier Exclusive", "Haute Couture"],
    "space": ["Replica-grade", "Ground Crew", "Flown", "Moon Mission"],
    "cars": ["Standard", "Low Mileage", "Matching Numbers", "Celebrity Owned"],
}

# key, name, category, art kind, base value, rarity (1-5), fakeable
CATALOG_RAW = [
    # Electronics
    ("ph_retro", "Retro Flip Phone", "electronics", "phone", 60, 1, False),
    ("ph_smart", "Smartphone X12", "electronics", "phone", 420, 2, True),
    ("lap_pro", "Pro Laptop 16\"", "electronics", "laptop", 900, 2, False),
    ("lap_vintage", "Beige Home Computer", "electronics", "laptop", 350, 3, False),
    ("cam_film", "Rangefinder Film Camera", "electronics", "camera", 520, 3, True),
    ("cam_dslr", "Mirrorless Camera Body", "electronics", "camera", 780, 2, False),
    ("con_retro", "8-bit Game Console", "electronics", "console", 180, 2, False),
    ("con_hand", "Handheld Console", "electronics", "console", 150, 1, False),
    ("hp_studio", "Studio Headphones", "electronics", "headphones", 240, 1, True),
    ("rad_tube", "Valve Tube Radio", "electronics", "radio", 210, 3, False),
    ("tv_crt", "Wooden CRT Television", "electronics", "tv", 140, 2, False),
    ("drone", "Camera Drone", "electronics", "drone", 650, 2, False),
    # Watches
    ("w_diver", "Ocean Diver Watch", "watches", "watch", 2400, 3, True),
    ("w_dress", "Gold Dress Watch", "watches", "watch", 1600, 3, True),
    ("w_chrono", "Racing Chronograph", "watches", "watch", 3800, 4, True),
    ("w_quartz", "Quartz Field Watch", "watches", "watch", 180, 1, False),
    ("w_pocket", "Silver Pocket Watch", "watches", "pocketwatch", 650, 3, True),
    ("w_digital", "Calculator Watch", "watches", "watch", 70, 1, False),
    ("w_tourb", "Skeleton Tourbillon", "watches", "watch", 7200, 5, True),
    # Jewelry
    ("j_ring_dia", "Diamond Solitaire Ring", "jewelry", "ring", 1900, 3, True),
    ("j_ring_sig", "Signet Ring", "jewelry", "ring", 320, 2, False),
    ("j_necklace", "Pearl Necklace", "jewelry", "necklace", 900, 2, True),
    ("j_emerald", "Emerald Pendant", "jewelry", "necklace", 2600, 4, True),
    ("j_earrings", "Sapphire Earrings", "jewelry", "earrings", 1100, 3, True),
    ("j_brooch", "Art Nouveau Brooch", "jewelry", "brooch", 750, 3, True),
    ("j_tiara", "Crystal Tiara", "jewelry", "crown", 3400, 5, True),
    # Antiques
    ("a_vase", "Porcelain Vase", "antiques", "vase", 800, 3, True),
    ("a_clock", "Mantel Clock", "antiques", "clock", 620, 2, False),
    ("a_lamp", "Stained Glass Lamp", "antiques", "lamp", 1300, 3, True),
    ("a_teapot", "Silver Teapot", "antiques", "teapot", 540, 2, True),
    ("a_globe", "Antique Globe", "antiques", "globe", 980, 3, False),
    ("a_gramo", "Horn Gramophone", "antiques", "gramophone", 760, 3, False),
    ("a_music", "Music Box", "antiques", "musicbox", 280, 2, False),
    # Collectibles
    ("c_card", "Holo Trading Card", "collectibles", "card", 300, 3, True),
    ("c_comic", "Golden-Age Comic", "collectibles", "comic", 650, 3, True),
    ("c_coin", "Gold Coin", "collectibles", "coin", 820, 3, True),
    ("c_robot", "Tin Toy Robot", "collectibles", "robot", 260, 2, True),
    ("c_vinyl", "Rare Vinyl Record", "collectibles", "vinyl", 140, 2, True),
    ("c_figure", "Action Figure (Boxed)", "collectibles", "figure", 120, 1, True),
    ("c_stamp", "Stamp Album", "collectibles", "book", 220, 2, False),
    ("c_jersey", "Signed Jersey", "collectibles", "jersey", 480, 3, True),
    # Art
    ("art_land", "Landscape Oil Painting", "art", "painting", 1500, 3, True),
    ("art_port", "Portrait in Gilt Frame", "art", "painting", 2200, 4, True),
    ("art_abs", "Abstract Canvas", "art", "abstract", 900, 3, True),
    ("art_sketch", "Charcoal Sketch", "art", "sketch", 300, 2, True),
    ("art_bust", "Marble Bust", "art", "bust", 1800, 4, True),
    ("art_bronze", "Bronze Statuette", "art", "statue", 1200, 3, True),
    # Instruments
    ("i_guitar", "Electric Guitar", "instruments", "guitar", 1100, 3, True),
    ("i_acoustic", "Acoustic Guitar", "instruments", "acoustic", 380, 2, False),
    ("i_violin", "Old Violin", "instruments", "violin", 1600, 4, True),
    ("i_trumpet", "Brass Trumpet", "instruments", "trumpet", 420, 2, False),
    ("i_synth", "Analog Synthesizer", "instruments", "synth", 1300, 3, False),
    ("i_sax", "Tenor Saxophone", "instruments", "sax", 950, 3, False),
    # Furniture
    ("f_chair", "Mid-century Lounge Chair", "furniture", "chair", 1400, 3, True),
    ("f_cabinet", "Oak Curio Cabinet", "furniture", "cabinet", 700, 2, False),
    ("f_rug", "Hand-knotted Rug", "furniture", "rug", 1100, 3, True),
    ("f_stool", "Industrial Stool", "furniture", "stool", 90, 1, False),
    ("f_mirror", "Gilded Mirror", "furniture", "mirror", 640, 2, False),
    # Historical
    ("h_sword", "Cavalry Sabre", "historical", "sword", 1200, 3, True),
    ("h_helmet", "Knight's Helm", "historical", "helmet", 2100, 4, True),
    ("h_map", "Hand-drawn Sea Chart", "historical", "map", 900, 3, True),
    ("h_book", "Leather-bound Atlas", "historical", "book", 560, 2, False),
    ("h_medal", "Campaign Medal", "historical", "medal", 300, 2, True),
    ("h_compass", "Brass Ship Compass", "historical", "compass", 420, 2, True),
    # Luxury
    ("l_bag", "Designer Handbag", "luxury", "handbag", 1800, 3, True),
    ("l_shades", "Designer Sunglasses", "luxury", "sunglasses", 260, 1, True),
    ("l_pen", "Gold Fountain Pen", "luxury", "pen", 520, 2, True),
    ("l_perfume", "Vintage Perfume", "luxury", "perfume", 340, 2, True),
    ("l_lighter", "Lacquer Lighter", "luxury", "lighter", 280, 2, True),
    ("l_scarf", "Silk Scarf", "luxury", "scarf", 380, 2, True),
    ("art_sea", "Watercolor Seascape", "art", "painting", 700, 2, True),
    ("art_pop", "Pop Art Print", "art", "abstract", 450, 2, True),
    ("art_mini", "Miniature Portrait", "art", "painting", 950, 3, True),
    ("art_garden", "Impressionist Garden", "art", "painting", 3200, 5, True),
    ("art_vase", "Studio Glass Sculpture", "art", "vase", 600, 2, False),
    ("e_arcade", "Arcade Cabinet", "electronics", "arcade", 1800, 3, False),
    ("e_mixer", "Studio Mixing Desk", "electronics", "synth", 2600, 4, False),
    ("e_watch", "Smartwatch Prototype", "electronics", "watch", 1200, 4, True),
    ("c_rookie", "Signed Rookie Card", "collectibles", "card", 1800, 4, True),
    ("c_issue1", "Issue #1 Comic", "collectibles", "comic", 4200, 5, True),
    ("c_doll", "Antique Porcelain Doll", "collectibles", "figure", 900, 3, True),
    ("i_drum", "Vintage Drum Kit", "instruments", "drum", 1400, 3, False),
    ("i_piano", "Upright Piano", "instruments", "piano", 2400, 3, False),
    # Relics (historical / antiques)
    ("h_amphora", "Ancient Amphora", "historical", "amphora", 1500, 4, True),
    ("h_idol", "Bronze Idol", "historical", "statue", 2400, 4, True),
    ("h_fossil", "Ammonite Fossil", "historical", "fossil", 380, 2, True),
    ("h_scroll", "Illuminated Scroll", "historical", "scroll", 1700, 4, True),
    ("h_rcoin", "Roman Denarius", "historical", "coin", 260, 2, True),
    ("a_chest", "Iron-bound Sea Chest", "antiques", "chest", 680, 2, False),
    # Vehicles
    ("v_hatch", "Rusty Hatchback", "cars", "hatchback", 650, 1, False),
    ("v_scooter", "Vintage Scooter", "cars", "scooter", 750, 2, False),
    ("v_sedan", "Family Sedan", "cars", "sedan", 1400, 1, False),
    ("v_moto", "Cafe Racer Motorcycle", "cars", "motorcycle", 1700, 2, True),
    ("v_pickup", "Pickup Truck", "cars", "pickup", 1900, 2, False),
    ("v_jeep", "Off-road 4x4", "cars", "jeep", 2500, 2, False),
    ("v_van", "Camper Van", "cars", "van", 2800, 3, False),
    ("v_muscle", "Classic Muscle Car", "cars", "muscle", 5200, 4, True),
    ("v_roadster", "Vintage Roadster", "cars", "roadster", 6800, 4, True),
    ("v_super", "Italian Supercar", "cars", "supercar", 12000, 5, True),
    # Space (expansion)
    ("s_meteor", "Iron Meteorite", "space", "meteor", 1400, 4, True),
    ("s_patch", "Mission Patch", "space", "patch", 260, 2, True),
    ("s_helmet", "Astronaut Visor", "space", "visor", 3000, 5, True),
    ("s_model", "Rocket Model", "space", "rocket", 480, 2, False),
]

# All money in the game is in "big" dollars: catalogue values above are multiplied once here.
MONEY = 10

CATALOG = {}
for row in CATALOG_RAW:
    key, name, cat, kind, base, rarity, fakeable = row
    base *= MONEY
    CATALOG[key] = {
        "key": key, "name": name, "category": cat, "kind": kind,
        "base": base, "rarity": rarity, "fakeable": fakeable,
    }

# Colour variants keep repeated items from feeling identical.
VARIANTS = ["a", "b", "c", "d"]

TELL_FAKE = [
    "The logo font looks a hair off.",
    "The weight feels slightly light for its size.",
    "The serial engraving is shallow and uneven.",
    "The stitching/finish is a bit too perfect.",
    "Paperwork looks freshly printed.",
]
TELL_RARE = [
    "There's an unusual marking on the underside.",
    "It has a numbered plate you don't recognize.",
    "The finish differs from the usual production model.",
    "A faded certificate is tucked inside.",
]
TELL_MISC = [
    "It's been well looked after, by the look of it.",
    "There's a bit of dust in the crevices.",
    "The seller keeps glancing at it fondly.",
]

_ids = itertools.count(1)


def new_item_id():
    return "it%d" % next(_ids)


def bump_ids(minimum):
    """After loading a save, make sure new ids don't collide."""
    global _ids
    _ids = itertools.count(minimum + 1)


def make_item(rng, tpl_key, condition=None, authentic=None, edition=None, fake_rate=0.12):
    tpl = CATALOG[tpl_key]
    if condition is None:
        condition = rng.choices(range(6), weights=[6, 22, 30, 24, 12, 6])[0]
    if authentic is None:
        authentic = not (tpl["fakeable"] and rng.random() < fake_rate)
    if edition is None:
        r = rng.random()
        boost = 0.01 * tpl["rarity"]
        if r < 0.012 + boost * 0.4:
            edition = 3
        elif r < 0.05 + boost:
            edition = 2
        elif r < 0.17 + boost * 2:
            edition = 1
        else:
            edition = 0
    if not authentic:
        edition = 0
    modified = authentic and rng.random() < 0.06
    hints = []
    if not authentic and rng.random() < 0.6:
        hints.append(rng.choice(TELL_FAKE))
    if edition > 0 and rng.random() < 0.55:
        hints.append(rng.choice(TELL_RARE))
    if not hints and rng.random() < 0.3:
        hints.append(rng.choice(TELL_MISC))
    return {
        "id": new_item_id(),
        "tpl": tpl_key,
        "cond": condition,
        "authentic": authentic,
        "edition": edition,
        "modified": modified,
        "quirk": round(rng.uniform(0.9, 1.1), 3),
        "variant": rng.choice(VARIANTS),
        "hints": hints,
    }


def true_value(item, mult=1.0):
    tpl = CATALOG[item["tpl"]]
    v = tpl["base"] * COND_MULT[item["cond"]] * EDITION_MULT[item["edition"]] * item["quirk"]
    if not item["authentic"]:
        v *= 0.06
    if item["modified"]:
        v *= 0.7
    return max(50, int(v * mult))


def naive_value(item, claimed_cond, mult=1.0):
    """What an item looks like it's worth if it were genuine, standard, at the claimed condition."""
    tpl = CATALOG[item["tpl"]]
    return max(50, int(tpl["base"] * COND_MULT[claimed_cond] * mult))


def new_knowledge(claimed_cond):
    return {"cond": False, "auth": False, "edition": False, "expert": False, "claimed": claimed_cond}


def estimate(item, know, mult=1.0):
    """Returns (low, likely, high) based only on what the holder knows."""
    tpl = CATALOG[item["tpl"]]
    if know.get("expert"):
        tv = true_value(item, mult)
        return (int(tv * 0.92), tv, int(tv * 1.08))
    if know.get("opinion"):  # your employed expert's read: confident, but possibly wrong
        o = know["opinion"]
        return (int(o * 0.85), int(o), int(o * 1.15))
    if know["cond"]:
        conds = [item["cond"]]
    else:
        c = know["claimed"]
        conds = list(range(c, min(5, c + 2) + 1))
    if know["auth"]:
        auths = [item["authentic"]]
    else:
        auths = [True, False] if tpl["fakeable"] else [True]
    if know["edition"] or (know["auth"] and not item["authentic"]):
        eds = [item["edition"]]
    else:
        eds = [0, 1]
    base = tpl["base"] * mult
    vals = []
    for c in conds:
        for a in auths:
            for e in eds if a else [0]:
                v = base * COND_MULT[c] * EDITION_MULT[e] * (1 if a else 0.06)
                vals.append(v)
    likely_c = item["cond"] if know["cond"] else know["claimed"]
    likely_a = item["authentic"] if know["auth"] else True
    likely_e = item["edition"] if know["edition"] else 0
    likely = base * COND_MULT[likely_c] * EDITION_MULT[likely_e] * (1 if likely_a else 0.06)
    if item["modified"] and know["auth"] and know.get("lab"):
        likely *= 0.7
        vals = [v * 0.7 for v in vals]
    low, high = min(vals) * 0.9, max(vals) * 1.1
    return (int(low), int(likely), int(high))


def nice(v):
    v = max(1, int(round(v)))
    step = (1 if v < 50 else 5 if v < 300 else 10 if v < 1500 else 25 if v < 6000 else 50 if v < 15000
            else 100 if v < 60000 else 250 if v < 150000 else 1000)
    return max(step, int(round(v / step)) * step)
