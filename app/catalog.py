"""Fixed lists of choices shared by forms, models and templates."""

CUSTOM_SIZE = "Custom size"
OTHER_TYPE = "Other (specify)"

PAPER_SIZES = [
    "Short (8.5 x 11 in)",
    "A4 (8.3 x 11.7 in)",
    "Long (8.5 x 13 in)",
    "A3 (11.7 x 16.5 in)",
    "A5 (5.8 x 8.3 in)",
    "Photo 4R (4 x 6 in)",
    "Photo 5R (5 x 7 in)",
    "Photo 8R (8 x 10 in)",
    "Large format (tarpaulin)",
    CUSTOM_SIZE,
]

PAPER_TYPES = [
    "Bond paper",
    "Glossy photo paper",
    "Matte photo paper",
    "Sticker paper",
    "Card stock",
    "Cartolina",
    "Tarpaulin",
    OTHER_TYPE,
]

COLOR_MODES = {"bw": "Black and white", "color": "Full color"}
SIDES = {"single": "Single-sided", "double": "Double-sided"}

PAYMENT_METHODS = {
    "cash": "Cash",
    "gcash": "GCash",
    "maya": "Maya",
    "bank": "Bank transfer",
    "other": "Other",
}

INVENTORY_CATEGORIES = {
    "paper": "Paper",
    "ink": "Ink",
    "toner": "Toner",
    "supplies": "Supplies",
    "other": "Other",
}

INVENTORY_UNITS = ["sheets", "reams", "pcs", "bottles", "rolls", "boxes", "meters"]
