"""Static game content: personas, dialogue, events, upgrades, staff, names."""

PERSONAS = {
    # knowledge: how closely they know the true value; greed: opening ask multiplier
    # reserve: walk-away floor as a fraction of what they believe it's worth
    "desperate": dict(label="Desperate Seller", vibe="Anxious", knowledge=0.6, greed=1.08, reserve=0.52,
                      patience=55, mood=75, concession=0.55, callback=0.45, weight=15),
    "shark": dict(label="Experienced Negotiator", vibe="Confident", knowledge=0.95, greed=1.35, reserve=0.86,
                  patience=70, mood=60, concession=0.22, callback=0.12, weight=13),
    "collector": dict(label="Collector", vibe="Particular", knowledge=0.9, greed=1.4, reserve=0.9,
                      patience=80, mood=65, concession=0.18, callback=0.15, weight=9),
    "clueless": dict(label="Uninformed Seller", vibe="Casual", knowledge=0.2, greed=1.25, reserve=0.68,
                     patience=60, mood=80, concession=0.45, callback=0.3, weight=13),
    "crook": dict(label="Dishonest Seller", vibe="Smooth-talking", knowledge=0.8, greed=1.3, reserve=0.5,
                  patience=48, mood=70, concession=0.38, callback=0.35, weight=9),
    "impatient": dict(label="Impatient Seller", vibe="In a hurry", knowledge=0.7, greed=1.2, reserve=0.72,
                      patience=30, mood=55, concession=0.5, callback=0.25, weight=13),
    "wealthy": dict(label="Wealthy Owner", vibe="Well-dressed", knowledge=0.7, greed=1.45, reserve=0.8,
                    patience=65, mood=70, concession=0.3, callback=0.1, weight=8),
    "regular": dict(label="Regular Seller", vibe="Friendly", knowledge=0.75, greed=1.25, reserve=0.75,
                    patience=55, mood=70, concession=0.35, callback=0.25, weight=14),
}

LINES = {
    "greet": {
        "desperate": ["Please, I really need some cash today. What'll you give me for this {item}?",
                      "Rent's due tomorrow... I've got this {item}. I was hoping for ${ask}.",
                      "I hate to part with it, but I need money fast. ${ask} for the {item}?"],
        "shark": ["I know exactly what this {item} is worth. ${ask}, and that's generous.",
                  "Let's not waste each other's time. {item}, ${ask}.",
                  "I've checked the market. ${ask} for this {item}. Fair and square."],
        "collector": ["This {item} is the pride of my collection. I won't let it go below ${ask}.",
                      "A true connoisseur would appreciate this {item}. ${ask}.",
                      "I'm downsizing my collection. This {item} — ${ask}, non-negotiable... mostly."],
        "clueless": ["Found this {item} in my grandma's attic. Is ${ask} alright?",
                     "No idea what this {item} is really worth. Maybe ${ask}?",
                     "My roommate said this {item} might be worth something. ${ask}?"],
        "crook": ["Genuine {item}, flawless condition. ${ask}, today only, friend.",
                  "You won't find a better {item} in the city. ${ask}, no questions needed.",
                  "Fell off a... I mean, came from a private collection. {item}, ${ask}."],
        "impatient": ["Quick, I've got a bus to catch. {item}, ${ask}. Yes or no?",
                      "I don't have all day. ${ask} for the {item}.",
                      "Let's make this fast. {item}. ${ask}."],
        "wealthy": ["I'm redecorating; this {item} no longer fits. ${ask} seems appropriate.",
                    "My assistant usually handles this. The {item} — ${ask}.",
                    "This {item} was a gift. I'd accept ${ask}."],
        "regular": ["Hi! I'd like to sell this {item}. I was thinking ${ask}?",
                    "Clearing out some stuff. How about ${ask} for the {item}?",
                    "Got this {item} I don't use anymore. ${ask} sound fair?"],
    },
    "counter": {
        "desperate": ["I... I can't go that low. ${ask}?", "Please, at least ${ask}.", "Could you do ${ask}? I need it."],
        "shark": ["Cute. ${ask}.", "You'll have to do better. ${ask}.", "I'll come down to ${ask}. Don't push it."],
        "collector": ["That's an insult to the piece. ${ask}.", "I could perhaps accept ${ask}.", "${ask}. It's worth every cent."],
        "clueless": ["Hmm, how about ${ask} instead?", "Meet me at ${ask}?", "Could we say ${ask}?"],
        "crook": ["Come on, ${ask}, it's a steal.", "For you? ${ask}.", "${ask} and we never met."],
        "impatient": ["Ugh. ${ask}. Final-ish.", "${ask}, come on, hurry.", "Fine, ${ask}."],
        "wealthy": ["I'd consider ${ask}.", "${ask}, darling.", "Let's say ${ask}."],
        "regular": ["How about ${ask}?", "Could you do ${ask}?", "I'd take ${ask}."],
    },
    "final": ["${ask} is my absolute lowest.", "That's it — ${ask}, final offer.", "I can't go below ${ask}."],
    "accept": {
        "desperate": ["Oh thank you, thank you!", "Deal. That really helps me out."],
        "shark": ["Fine. Pleasure doing business.", "Deal. You drive a hard bargain."],
        "collector": ["Take good care of it.", "Very well. It's yours."],
        "clueless": ["Sweet, deal!", "Awesome, thanks!"],
        "crook": ["Great doing business. Bye!", "Deal! ...I'll be going now."],
        "impatient": ["Done. Bye.", "Deal. Gotta run!"],
        "wealthy": ["Splendid.", "Very well, that will do."],
        "regular": ["Deal! Thanks.", "Sounds good to me."],
    },
    "insulted": ["Are you joking?", "That's insulting.", "Seriously? No way.", "You're wasting my time."],
    "backwards": ["You're going backwards now?", "That's lower than before!"],
    "storm": ["Forget it, I'm going somewhere else!", "I'm done here.", "Unbelievable. Goodbye."],
    "timeout": ["I've waited long enough. Bye.", "I don't have time for this.", "Never mind, I'll try another shop."],
    "callback": ["Wait! Wait... fine. ${ask} and it's yours.", "Hold on! ${ask}? Please?", "Okay okay — ${ask}, last chance."],
}

PERSUADE = {
    "flaws": {"name": "Point out flaws", "desc": "Use what you've found. Bluffing is risky."},
    "cash": {"name": "Cash right now", "desc": "Works on people who need money fast."},
    "reputation": {"name": "Vouch for your shop", "desc": "Stronger with high reputation."},
    "market": {"name": "\"The market is soft\"", "desc": "Only convincing when demand really is down."},
}

TOOLS = {
    "inspect": {"name": "Condition Inspection", "cost": 150, "time": 3, "desc": "Reveals true condition."},
    "scan": {"name": "Authenticity Scan", "cost": 450, "time": 5, "desc": "Detects counterfeits. Lab L2 also spots modifications."},
    "expert": {"name": "Lab Certification", "cost": 1100, "time": 8, "desc": "Lab tests reveal everything, including rare editions. Never wrong."},
}

UPGRADES = {
    "showroom": {"name": "Showroom Expansion", "costs": [6000, 13000, 24000], "values": [4, 6, 8, 10],
                 "desc": "More display slots for items on sale (+1 staff slot per level)."},
    "storage": {"name": "Back Room Storage", "costs": [4000, 9000, 18000], "values": [8, 12, 18, 26],
                "desc": "Hold more items in total."},
    "lab": {"name": "Appraisal Lab", "costs": [7000, 16000], "values": [0, 1, 2],
            "desc": "Tools 30% / 55% cheaper and faster. Level 2 detects modifications."},
    "cases": {"name": "Premium Display Cases", "costs": [5000, 11000, 20000], "values": [0, 1, 2, 3],
              "desc": "+8% buyer appeal per level."},
    "ads": {"name": "Advertising", "costs": [4500, 10000, 19000], "values": [0, 1, 2, 3],
            "desc": "More sellers walk through your door."},
    "service": {"name": "Customer Lounge", "costs": [4000, 9500], "values": [0, 1, 2],
                "desc": "Sellers wait and negotiate 20% longer per level."},
    "security": {"name": "Security System", "costs": [5000, 12000], "values": [0, 1, 2],
                 "desc": "Deters theft and softens fake-sale complaints."},
    "specialty": {"name": "Specialty Corner", "costs": [9000], "values": [0, 1],
                  "desc": "Pick a category: buyers looking for it favour your shop (+15% appeal)."},
}

# Specialists you can hire. Stars 1-3; wages are paid weekly (first week prorated).
WAGES = {1: 2000, 2: 10000, 3: 50000}
MAX_EMPLOYEES = 4
EMPLOYEES = {
    "mechanic": {"name": "Mechanic", "icon": "🔧",
                 "desc": "Repairs any item in your stock for a fee. Takes days, depending on the item and how broken it is.",
                 "stars": ["Repairs up to Good · 1 job at a time", "Repairs up to Excellent · 2 jobs · faster & cheaper",
                           "Restores to Brand New · 3 jobs · fastest & cheapest"]},
    "mentalist": {"name": "Mentalist", "icon": "🔮",
                  "desc": "Reads sellers' minds: much better persuasion, and a sense of how low they'll really go.",
                  "stars": ["+15% persuasion · reveals personality & exact mood", "+30% persuasion · senses their lowest price (±15%)",
                            "+45% persuasion · knows their lowest price (±6%)"]},
    "lucky": {"name": "Lucky Kid", "icon": "🍀",
              "desc": "Things just go your way: offers land more often, buyers tip, thieves trip over themselves.",
              "stars": ["Small luck boost", "Good luck: deals land more, buyers tip more", "Unreal luck"]},
    "expert": {"name": "Appraisal Expert", "icon": "🎓",
               "desc": "Instantly tells you an item's real value for free — but can get very rare pieces wrong.",
               "stars": ["4 opinions/day · often fooled by rare items", "8 opinions/day · sometimes fooled by rare items",
                         "Unlimited · rarely wrong"]},
    "negotiator": {"name": "Negotiator", "icon": "💬", "desc": "Haggles for you: sellers accept lower prices.",
                   "stars": ["Sellers' floor −4%", "Sellers' floor −8%", "Sellers' floor −12%"]},
    "sales": {"name": "Salesperson", "icon": "🤝", "desc": "Draws buyers to your shop and closes sales slightly above their budget.",
              "stars": ["+5% appeal · closes +4%", "+10% appeal · closes +8%", "+15% appeal · closes +12%"]},
    "security": {"name": "Security Guard", "icon": "🛡️", "desc": "Stops shoplifters and spots dishonest sellers.",
                 "stars": ["Stops 30% of thefts · flags crooks", "Stops 60% · also spots lies about condition",
                           "Stops 90% · flags everything shady"]},
    "analyst": {"name": "Market Analyst", "icon": "📊", "desc": "Forecasts tomorrow's market every morning.",
                "stars": ["Rough forecast", "Exact forecast", "Exact forecast + names tomorrow's event"]},
    "scout": {"name": "Auction Scout", "icon": "🔭", "desc": "Inspects auction lots before bidding opens — only you see the report.",
              "stars": ["Reveals lot condition", "+ authenticity", "+ rare editions"]},
    "marketer": {"name": "Marketer", "icon": "📣", "desc": "Advertising and word of mouth: more sellers and more buyers.",
                 "stars": ["+15% sellers · +10% buyers", "+30% sellers · +20% buyers", "+45% sellers · +30% buyers"]},
}
AI_HIRES = {"cautious": ["security", "expert"], "roller": ["sales", "marketer"], "collector": ["expert", "scout"],
            "flipper": ["marketer", "negotiator"], "bargain": ["negotiator", "lucky"], "antique": ["mechanic", "expert"],
            "tech": ["mechanic", "analyst"], "balanced": ["sales", "negotiator"]}

FIRST = ["Alex", "Sam", "Jordan", "Riley", "Morgan", "Casey", "Taylor", "Jamie", "Avery", "Quinn", "Rowan",
         "Drew", "Elliot", "Harper", "Kai", "Logan", "Marley", "Nico", "Parker", "Reese", "Skyler", "Toni",
         "Val", "Wren", "Zion", "Bea", "Cyril", "Dina", "Emil", "Farah", "Gus", "Hana", "Ivo", "Juno",
         "Kofi", "Lena", "Milo", "Nadia", "Omar", "Pia", "Rafa", "Sela", "Tobi", "Uma", "Vik", "Yara"]
LAST = ["Abara", "Brooks", "Castillo", "Dubois", "Eriksen", "Fontaine", "Grant", "Haddad", "Ito", "Jansen",
        "Kowalski", "Laurent", "Moreau", "Nakamura", "Okafor", "Petrov", "Quist", "Rossi", "Sato", "Torres",
        "Ulrich", "Varga", "Weiss", "Xu", "Yilmaz", "Zamora"]

AI_DEALERS = [
    {"name": "Cautious Carla", "style": "cautious"},
    {"name": "High-Roller Hank", "style": "roller"},
    {"name": "Collector Kim", "style": "collector"},
    {"name": "Flipper Fred", "style": "flipper"},
    {"name": "Bargain Betty", "style": "bargain"},
    {"name": "Antique Ada", "style": "antique"},
    {"name": "Tech Theo", "style": "tech"},
    {"name": "Steady Sol", "style": "balanced"},
]

AI_STYLES = {
    # buy: max price as fraction of own estimate; markup: listing price multiplier
    # risk: auction aggressiveness; noise: appraisal error; scan: scan items above this naive value
    "cautious": dict(buy=0.62, markup=1.18, risk=0.7, noise=0.12, scan=2500, upgrades=["storage", "lab", "security", "showroom"], fav=None),
    "roller": dict(buy=0.73, markup=1.3, risk=1.05, noise=0.2, scan=12000, upgrades=["showroom", "cases", "ads", "storage"], fav="luxury"),
    "collector": dict(buy=0.72, markup=1.35, risk=0.95, noise=0.1, scan=4000, upgrades=["lab", "cases", "showroom", "specialty"], fav="collectibles"),
    "flipper": dict(buy=0.68, markup=1.1, risk=0.8, noise=0.16, scan=6000, upgrades=["ads", "showroom", "storage", "service"], fav=None),
    "bargain": dict(buy=0.6, markup=1.15, risk=0.6, noise=0.14, scan=3000, upgrades=["ads", "storage", "service", "showroom"], fav=None),
    "antique": dict(buy=0.7, markup=1.28, risk=0.9, noise=0.11, scan=3500, upgrades=["specialty", "lab", "cases", "showroom"], fav="antiques"),
    "tech": dict(buy=0.7, markup=1.22, risk=0.85, noise=0.13, scan=5000, upgrades=["specialty", "showroom", "ads", "storage"], fav="electronics"),
    "balanced": dict(buy=0.66, markup=1.2, risk=0.8, noise=0.14, scan=4500, upgrades=["showroom", "storage", "lab", "cases"], fav=None),
}

EVENTS = [
    {"key": "tech_expo", "name": "Tech Expo in Town", "desc": "Electronics demand surges.", "cats": {"electronics": 0.4},
     "rumor": "Gadget bloggers are booking every hotel in the city..."},
    {"key": "watch_slump", "name": "Luxury Watch Slump", "desc": "Watches lose demand after a market scandal.", "cats": {"watches": -0.3},
     "rumor": "Whispers of a watchmaker scandal are spreading..."},
    {"key": "antique_collector", "name": "Famous Collector Buying Antiques", "desc": "Antiques soar; a big spender is shopping.", "cats": {"antiques": 0.45},
     "rumor": "A well-known collector's private jet just landed..."},
    {"key": "vintage_craze", "name": "Collectibles Craze", "desc": "A viral video sparks a collectibles frenzy.", "cats": {"collectibles": 0.35},
     "rumor": "Something nostalgic is trending online..."},
    {"key": "recession", "name": "Economic Downturn", "desc": "All demand falls; sellers are more desperate.", "cats": {"*": -0.15},
     "rumor": "Economists are nervous about tomorrow's figures..."},
    {"key": "luxury_boom", "name": "Luxury Boom", "desc": "Luxury goods and jewelry in vogue.", "cats": {"luxury": 0.3, "jewelry": 0.2},
     "rumor": "Fashion week is just around the corner..."},
    {"key": "shortage", "name": "Supply Shortage", "desc": "A category is scarce: fewer sellers, higher prices.", "cats": {},
     "rumor": "Shipping delays are hitting one sector hard..."},
    {"key": "auction_house", "name": "Major Auction House Opens", "desc": "Extra and rarer lots at today's auction.", "cats": {},
     "rumor": "A prestigious auction house is preparing its grand opening..."},
    {"key": "rush", "name": "Customer Rush", "desc": "Sellers and buyers flood the street.", "cats": {},
     "rumor": "A street festival is planned nearby..."},
    {"key": "estate", "name": "Estate Collection", "desc": "A whole estate goes under the hammer today.", "cats": {},
     "rumor": "A reclusive old collector has passed away..."},
    {"key": "fake_ring", "name": "Counterfeit Ring Active", "desc": "Police warn of a surge in convincing fakes.", "cats": {},
     "rumor": "Police are investigating a forgery workshop..."},
    {"key": "art_fair", "name": "Art Fair Weekend", "desc": "Art and designer furniture in demand.", "cats": {"art": 0.4, "furniture": 0.15},
     "rumor": "Gallery owners are buzzing about something..."},
    {"key": "music_fest", "name": "Music Festival", "desc": "Musicians are hunting for instruments.", "cats": {"instruments": 0.4},
     "rumor": "Stage crews are setting up in the park..."},
    {"key": "museum", "name": "Museum Acquisition Drive", "desc": "Historical objects wanted.", "cats": {"historical": 0.4},
     "rumor": "The city museum got a big donation..."},
]
EVENTS += [
    {"key": "car_show", "name": "Classic Car Show", "desc": "Petrolheads are in town: vehicles in demand.", "cats": {"cars": 0.4},
     "rumor": "Chrome polish is sold out across the city..."},
    {"key": "fuel_spike", "name": "Fuel Price Spike", "desc": "Fuel prices jump; nobody wants a gas guzzler.", "cats": {"cars": -0.25},
     "rumor": "Oil traders are looking very nervous..."},
]
EVENT_BY_KEY = {e["key"]: e for e in EVENTS}

# Dealership types. cats=None means "every category in play".
DEALERSHIP_TYPES = {
    "general": {"note": "Balanced", "turnover": 1.0, "name": "General Dealer", "icon": "🏪", "cats": None, "sign": "TRADING POST",
                "desc": "Buy and sell anything that walks through the door."},
    "cars": {"note": "High risk · big tickets", "turnover": 0.85, "name": "Car Dealership", "icon": "🚗", "cats": ["cars"], "sign": "MOTORS",
             "desc": "Beaters, classics and the odd supercar. Big tickets, big swings."},
    "gallery": {"note": "Forgery-heavy", "turnover": 1.0, "name": "Art Gallery", "icon": "🖼️", "cats": ["art", "furniture"], "sign": "GALLERY",
                "desc": "Paintings, sculpture and designer furniture. Forgeries abound."},
    "relics": {"note": "Balanced", "turnover": 1.0, "name": "Relics & Antiquities", "icon": "🏺", "cats": ["historical", "antiques"], "sign": "ANTIQUITIES",
               "desc": "Ancient relics, old maps, swords and heirlooms."},
    "jeweler": {"note": "Fakes everywhere", "turnover": 1.0, "name": "Jeweler", "icon": "💎", "cats": ["jewelry", "watches", "luxury"], "sign": "JEWELERS",
                "desc": "Watches, gems and designer goods. Fakes are everywhere."},
    "tech": {"note": "Volume game · thin margins", "turnover": 2.0, "name": "Tech Shop", "icon": "💻", "cats": ["electronics"], "sign": "TECH",
             "desc": "Gadgets new and retro. Quick turnover, thin margins."},
    "music": {"note": "Steady", "turnover": 1.25, "name": "Music Store", "icon": "🎸", "cats": ["instruments"], "sign": "MUSIC",
              "desc": "Guitars, violins, brass and synths."},
    "collectibles": {"note": "Volume game · rare jackpots", "turnover": 2.0, "name": "Collectibles Shop", "icon": "🃏", "cats": ["collectibles", "space"], "sign": "COLLECTIBLES",
                     "desc": "Cards, comics, coins and toys (plus space memorabilia when unlocked)."},
}
AI_TYPE_PREF = {"tech": "tech", "antique": "relics", "collector": "collectibles", "roller": "jeweler"}

ESTATE_NAMES = ["the late Mr. Hargrove", "Lady Penhallow", "Professor Okonkwo", "the Van Dalen family",
                "Captain Iverson", "a reclusive inventor", "a retired opera star"]
