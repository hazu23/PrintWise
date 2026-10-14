"""Small helpers shared by several pages."""
from datetime import date, datetime

from flask import request


class Pagination:
    """Works out which slice of a long list to show and which page links to draw."""

    def __init__(self, total: int, per_page: int, page: int = 1):
        self.total, self.per_page = total, per_page
        self.pages = max(1, -(-total // per_page))
        self.page = min(max(1, page), self.pages)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def first_item(self) -> int:
        return self.offset + 1 if self.total else 0

    @property
    def last_item(self) -> int:
        return min(self.offset + self.per_page, self.total)


def current_page() -> int:
    try:
        return int(request.args.get("page", "1"))
    except ValueError:
        return 1


def parse_date(text: str):
    """Turn "2026-10-13" into a date, or None when it is empty or wrong."""
    try:
        return datetime.strptime((text or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def today_local() -> date:
    from app.db import now
    return now().date()
