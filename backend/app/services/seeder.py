from sqlmodel import Session, select

from app.models.categorize_rule import CategorizeRule
from app.models.product_category import ProductCategory

DEFAULT_CATEGORIES: list[dict] = [
    {"name": "Dairy", "icon": "🥛", "color": "#60a5fa"},
    {"name": "Fresh Meat & Sausage", "icon": "🥩", "color": "#f87171"},
    {"name": "Lunchmeat & Sandwich Toppings", "icon": "🥪", "color": "#fda4af"},
    {"name": "Bakery & Bread", "icon": "🍞", "color": "#fbbf24"},
    {"name": "Non-Alcoholic Beverages", "icon": "🥤", "color": "#34d399"},
    {"name": "Alcoholic Beverages", "icon": "🍷", "color": "#10b981"},
    {"name": "Snacks & Sweets", "icon": "🍬", "color": "#f472b6"},
    {"name": "Pasta & Grains", "icon": "🍝", "color": "#fb923c"},
    {"name": "Frozen & Ready Meals", "icon": "🧊", "color": "#93c5fd"},
    {"name": "Condiments & Spreads", "icon": "🫙", "color": "#a78bfa"},
    {"name": "Produce", "icon": "🥬", "color": "#4ade80"},
    {"name": "Household & Cleaning", "icon": "🧽", "color": "#2dd4bf"},
    {"name": "Deposit", "icon": "♻️", "color": "#9ca3af"},
    {"name": "Uncategorized", "icon": "🏷️", "color": "#6b7280"},
]

DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "Dairy": [
        "MILCH",
        "JOGHURT",
        "SAHNE",
        "BUTTER",
        "QUARK",
        "MOZZARELLA",
        "GOUDA",
        "EMMENTALER",
        "FRISCHMILCH",
        "SCHMAND",
        "ARYAN",
    ],
    "Fresh Meat & Sausage": [
        "FLEISCH",
        "HACKFLEISCH",
        "RINDERHACK",
        "GEFLUEGEL",
        "HUEHNCHEN",
        "SCHWEINEFILET",
        "RINDERSTEAK",
        "BRATWURST",
        "KOTELETT",
        "GULASCH",
    ],
    "Lunchmeat & Sandwich Toppings": [
        "AUFSCHNITT",
        "SCHINKEN",
        "SALAMI",
        "MORTADELLA",
        "PASTETE",
        "LEBERWURST",
        "PUTENBRUST",
        "SANDWICHBELAG",
    ],
    "Bakery & Bread": [
        "BROT",
        "BROETCHEN",
        "SEMMEL",
        "CROISSANT",
        "LAUGEN",
        "BAGUETTE",
        "BREZEL",
        "VOLLKORNBROT",
    ],
    "Non-Alcoholic Beverages": [
        "WASSER",
        "MINERALWASSER",
        "SPRUDEL",
        "STILLWASSER",
        "LIMONADE",
        "SAFT",
        "NEKTAR",
        "SCHORLE",
        "EISTEE",
        "TONIC",
        "COLA",
        "MONSTER",
    ],
    "Alcoholic Beverages": [
        "BIER",
        "PILS",
        "WEIN",
        "ROTWEIN",
        "WEISSWEIN",
        "SEKT",
        "PROSECCO",
        "RUM",
        "WODKA",
        "GIN",
        "APERITIF",
        "HALBTR.",
        "PINOT",
        "RADLER",
        "CIDER",
        "SCHWARZB.",
    ],
    "Snacks & Sweets": [
        "SCHOKOLADE",
        "CHIPS",
        "KEKS",
        "RIEGEL",
        "BONBON",
        "LAKRITZ",
        "NUESSE",
        "GUMMIBAERCHEN",
        "PRINGLES",
        "NIC NAC",
        "HARIBO",
    ],
    "Pasta & Grains": [
        "SPAGHETTI",
        "FUSILLI",
        "PENNE",
        "RIGATONI",
        "NUDEL",
        "REIS",
        "BASMATIREIS",
        "COUSCOUS",
        "BULGUR",
        "QUINOA",
    ],
    "Frozen & Ready Meals": [
        "TIEFKUEHL",
        "TK",
        "PIZZA",
        "FERTIGGERICHT",
        "MIKROWELLENGERICHT",
        "KROKETTEN",
        "POMMES",
        "FISCHSTAEBCHEN",
    ],
    "Condiments & Spreads": [
        "SENF",
        "KETCHUP",
        "MAYONNAISE",
        "DRESSING",
        "ESSIG",
        "OEL",
        "SOJASOSSE",
        "TOMATENMARK",
        "PESTO",
        "AUFSTRICH",
    ],
    "Produce": [
        "APFEL",
        "BANANE",
        "TOMATE",
        "GURKE",
        "SALAT",
        "PAPRIKA",
        "ZWIEBEL",
        "KAROTTE",
        "KARTOFFEL",
        "ZUCCHINI",
        "AVOCADO",
        "BIRNE",
        "TRAUBEN",
        "BEEREN",
        "PILZE",
        "CHAMPIGNON",
        "BROKKOLI",
        "BLUMENKOHL",
    ],
    "Household & Cleaning": [
        "SEIFE",
        "WASCHMITTEL",
        "REINIGER",
        "PUTZMITTEL",
        "SPUELMITTEL",
        "TOILETTENPAPIER",
        "KUECHENROLLE",
        "TASCHENTUCH",
        "MUELLBEUTEL",
        "SCHWAMM",
    ],
    "Deposit": ["PFAND", "LEERGUT"],
}


def _seeded_rule_priority(keyword: str) -> int:
    normalized = keyword.strip().replace(".", "")
    if len(normalized) <= 4:
        return 10
    return 20


def seed_defaults(session: Session) -> None:
    """Seed default product categories and keyword rules on first run."""
    existing = session.exec(select(ProductCategory)).first()
    if existing:
        return  # Already seeded

    category_map: dict[str, int] = {}

    for cat_data in DEFAULT_CATEGORIES:
        category = ProductCategory(**cat_data, is_default=True)
        session.add(category)
        session.flush()
        category_map[category.name] = category.id  # type: ignore[assignment]

    for cat_name, keywords in DEFAULT_KEYWORDS.items():
        cat_id = category_map.get(cat_name)
        if not cat_id:
            continue
        for keyword in keywords:
            rule = CategorizeRule(
                keyword=keyword,
                match_type="contains",
                category_id=cat_id,
                priority=_seeded_rule_priority(keyword),
            )
            session.add(rule)

    session.commit()
