from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.categorize_rule import CategorizeRule
from app.models.parser_template import ParserTemplate
from app.models.product_category import ProductCategory

DEFAULT_LOCALE = "de"


@dataclass
class CategoryDef:
    key: str
    names: dict[str, str]
    icon: str
    color: str
    keywords: list[str] = field(default_factory=list)


CATEGORY_DEFS: list[CategoryDef] = [
    CategoryDef(
        key="dairy",
        names={"de": "Milchprodukte", "en": "Dairy"},
        icon="🥛",
        color="#60a5fa",
        keywords=[
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
    ),
    CategoryDef(
        key="fresh_meat",
        names={"de": "Frischfleisch & Wurst", "en": "Fresh Meat & Sausage"},
        icon="🥩",
        color="#f87171",
        keywords=[
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
    ),
    CategoryDef(
        key="lunchmeat",
        names={"de": "Aufschnitt & Belag", "en": "Lunchmeat & Sandwich Toppings"},
        icon="🥪",
        color="#fda4af",
        keywords=[
            "AUFSCHNITT",
            "SCHINKEN",
            "SALAMI",
            "MORTADELLA",
            "PASTETE",
            "LEBERWURST",
            "PUTENBRUST",
            "SANDWICHBELAG",
        ],
    ),
    CategoryDef(
        key="bakery",
        names={"de": "Brot & Backwaren", "en": "Bakery & Bread"},
        icon="🍞",
        color="#fbbf24",
        keywords=[
            "BROT",
            "BROETCHEN",
            "SEMMEL",
            "CROISSANT",
            "LAUGEN",
            "BAGUETTE",
            "BREZEL",
            "VOLLKORNBROT",
        ],
    ),
    CategoryDef(
        key="non_alcoholic",
        names={"de": "Alkoholfreie Getränke", "en": "Non-Alcoholic Beverages"},
        icon="🥤",
        color="#34d399",
        keywords=[
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
    ),
    CategoryDef(
        key="alcoholic",
        names={"de": "Alkoholische Getränke", "en": "Alcoholic Beverages"},
        icon="🍷",
        color="#10b981",
        keywords=[
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
    ),
    CategoryDef(
        key="snacks",
        names={"de": "Snacks & Süßigkeiten", "en": "Snacks & Sweets"},
        icon="🍬",
        color="#f472b6",
        keywords=[
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
    ),
    CategoryDef(
        key="pasta_grains",
        names={"de": "Nudeln & Getreide", "en": "Pasta & Grains"},
        icon="🍝",
        color="#fb923c",
        keywords=[
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
    ),
    CategoryDef(
        key="frozen",
        names={"de": "Tiefkühl & Fertiggerichte", "en": "Frozen & Ready Meals"},
        icon="🧊",
        color="#93c5fd",
        keywords=[
            "TIEFKUEHL",
            "TK",
            "PIZZA",
            "FERTIGGERICHT",
            "MIKROWELLENGERICHT",
            "KROKETTEN",
            "POMMES",
            "FISCHSTAEBCHEN",
        ],
    ),
    CategoryDef(
        key="condiments",
        names={"de": "Gewürze & Aufstriche", "en": "Condiments & Spreads"},
        icon="🫙",
        color="#a78bfa",
        keywords=[
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
    ),
    CategoryDef(
        key="produce",
        names={"de": "Obst & Gemüse", "en": "Produce"},
        icon="🥬",
        color="#4ade80",
        keywords=[
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
    ),
    CategoryDef(
        key="household",
        names={"de": "Haushalt & Reinigung", "en": "Household & Cleaning"},
        icon="🧽",
        color="#2dd4bf",
        keywords=[
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
    ),
    CategoryDef(
        key="deposit",
        names={"de": "Pfand", "en": "Deposit"},
        icon="♻️",
        color="#9ca3af",
        keywords=["PFAND", "LEERGUT"],
    ),
    CategoryDef(
        key="uncategorized",
        names={"de": "Unkategorisiert", "en": "Uncategorized"},
        icon="🏷️",
        color="#6b7280",
        keywords=[],
    ),
]


def _seeded_rule_priority(keyword: str) -> int:
    normalized = keyword.strip().replace(".", "")
    if len(normalized) <= 4:
        return 10
    return 20


def seed_defaults(session: Session, locale: str = DEFAULT_LOCALE) -> None:
    """Seed default product categories, keyword rules, and parser templates."""
    # Seed parser templates (independent of category seeding)
    template_defs = {
        "rewe": {"display_name": "REWE eBon", "icon": "🛒"},
        "lidl": {"display_name": "Lidl Plus", "icon": "🧾"},
        "kaufland": {"display_name": "Kaufland eBon", "icon": "🧺"},
    }
    template_changed = False
    for slug, definition in template_defs.items():
        existing_template = session.exec(
            select(ParserTemplate).where(ParserTemplate.slug == slug)
        ).first()
        if existing_template is None:
            session.add(
                ParserTemplate(
                    slug=slug,
                    display_name=definition["display_name"],
                    icon=definition["icon"],
                    is_active=True,
                )
            )
            template_changed = True
            continue

        if existing_template.display_name != definition["display_name"]:
            existing_template.display_name = definition["display_name"]
            template_changed = True
        if existing_template.icon != definition["icon"]:
            existing_template.icon = definition["icon"]
            template_changed = True
        if not existing_template.is_active:
            existing_template.is_active = True
            template_changed = True

    if template_changed:
        session.commit()

    existing = session.exec(select(ProductCategory)).first()
    if existing:
        return  # Already seeded

    for cat_def in CATEGORY_DEFS:
        name = cat_def.names.get(locale, cat_def.names.get("en", cat_def.key))
        category = ProductCategory(
            name=name, icon=cat_def.icon, color=cat_def.color, is_default=True
        )
        session.add(category)
        session.flush()

        for keyword in cat_def.keywords:
            rule = CategorizeRule(
                keyword=keyword,
                match_type="contains",
                category_id=category.id,  # type: ignore[assignment]
                priority=_seeded_rule_priority(keyword),
            )
            session.add(rule)

    session.commit()
