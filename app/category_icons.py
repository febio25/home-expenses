"""Icons of the categories (0.15.0).

The entry forms show the categories as icons, four to a row. Expense
categories are rows of the database, so each one stores the name of its
icon (``categories.icon``), chosen in Impostazioni → Categorie from the list
below. Income categories are a fixed list in the code, and so are their
icons (``INCOME_CATEGORY_ICONS``).

Only names travel through the API: the drawings are Tabler Icons copied
into ``app/static/js/category-icons.js`` (a test checks that every name here
has its drawing there). A future native app would map the same names to its
own images.
"""

from __future__ import annotations

# The icons a person can choose for an expense category, in the order the
# picker shows them (grouped by subject: home, food, health and clothes,
# transport, free time, family, money, generic).
CHOOSABLE_ICONS: tuple[str, ...] = (
    "shopping-cart", "basket", "home", "home-bolt", "bolt", "droplet", "flame", "wifi",
    "armchair", "tool",
    "tools-kitchen-2", "coffee", "pizza", "beer", "cake",
    "first-aid-kit", "pill", "dental", "barbell", "scissors", "shirt", "shoe", "hanger",
    "car", "gas-station", "bus", "train", "bike", "plane",
    "ticket", "movie", "music", "device-gamepad-2", "ball-football", "beach", "book",
    "device-tv",
    "gift", "heart", "paw", "baby-carriage", "school", "plant",
    "repeat", "device-mobile", "receipt", "receipt-tax", "building-bank", "credit-card",
    "cash", "wallet", "briefcase", "shield-check",
    "dots", "tag", "star", "category",
)

# A category with no icon chosen (one created before 0.15.0 with a name of
# its own, or a new one saved without picking) shows this one.
DEFAULT_ICON = "category"

# Icons of the fixed income categories (codes of INCOME_CATEGORIES).
INCOME_CATEGORY_ICONS: dict[str, str] = {
    "salary": "briefcase",
    "meal_voucher": "tools-kitchen-2",
    # 0.16.0: the price tag of the Vinted tab in the bottom bar; «Vendite»
    # takes a banknote with a coin (Tabler has no hand holding a coin).
    "vinted": "tag",
    "refund": "receipt-refund",
    "gift": "gift",
    "sale": "cash-coin",
    "other": "dots",
}

# Every name the interface must be able to draw.
ALL_ICONS: frozenset[str] = frozenset(CHOOSABLE_ICONS) | frozenset(INCOME_CATEGORY_ICONS.values())


def income_icon(code: str) -> str:
    return INCOME_CATEGORY_ICONS.get(code, DEFAULT_ICON)
