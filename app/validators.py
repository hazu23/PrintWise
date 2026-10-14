"""Server-side form validation.

The browser also checks forms (HTML5 attributes and static/js/app.js), but that
can be bypassed, so every value is checked here again before it is used.
`FormValidator` collects one friendly message per field; the template shows it
next to the field and keeps what the user typed.
"""
import re
from decimal import Decimal, InvalidOperation

USERNAME_RE = re.compile(r"^[a-z0-9._]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^[0-9+ \-]{7,20}$")


def password_problem(password: str):
    """Return a message when the password is too weak, otherwise None."""
    if len(password) < 8:
        return "Use at least 8 characters."
    if len(password) > 128:
        return "Use 128 characters or fewer."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Include at least one letter and one number."
    return None


class FormValidator:
    def __init__(self, data):
        self.data = data
        self.errors: dict = {}
        self.values: dict = {}

    # ----- plumbing --------------------------------------------------------
    def _raw(self, name: str) -> str:
        return (self.data.get(name) or "").strip()

    def fail(self, name: str, message: str):
        self.errors.setdefault(name, message)
        return None

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def _store(self, name, value):
        self.values[name] = value
        return value

    # ----- field types -----------------------------------------------------
    def text(self, name, label, required=True, min_length=0, max_length=255,
             choices=None, lower=False, pattern=None, pattern_message=None):
        value = self._raw(name)
        if lower:
            value = value.lower()
        if not value:
            if required:
                return self.fail(name, f"{label} is required.")
            return self._store(name, "")
        if len(value) < min_length:
            return self.fail(name, f"{label} must be at least {min_length} characters.")
        if len(value) > max_length:
            return self.fail(name, f"{label} must be {max_length} characters or fewer.")
        if choices is not None and value not in choices:
            return self.fail(name, f"Choose a valid option for {label.lower()}.")
        if pattern and not pattern.match(value):
            return self.fail(name, pattern_message or f"{label} is not valid.")
        return self._store(name, value)

    def email(self, name, label="Email address", required=True):
        value = self.text(name, label, required=required, max_length=120, lower=True,
                          pattern=EMAIL_RE, pattern_message="Enter a valid email address, like name@example.com.")
        return value

    def username(self, name, label="Username"):
        return self.text(name, label, lower=True, pattern=USERNAME_RE,
                         pattern_message="Use 3 to 30 letters, numbers, dots or underscores.")

    def phone(self, name, label="Phone number", required=False):
        return self.text(name, label, required=required, max_length=20, pattern=PHONE_RE,
                         pattern_message="Enter a valid phone number, like 0917 123 4567.")

    def integer(self, name, label, minimum=None, maximum=None, required=True):
        raw = self._raw(name)
        if not raw:
            if required:
                return self.fail(name, f"{label} is required.")
            return self._store(name, None)
        if not re.fullmatch(r"-?\d{1,9}", raw):
            return self.fail(name, f"{label} must be a whole number.")
        value = int(raw)
        if minimum is not None and value < minimum:
            return self.fail(name, f"{label} must be {minimum} or more.")
        if maximum is not None and value > maximum:
            return self.fail(name, f"{label} must be {maximum} or less.")
        return self._store(name, value)

    def amount(self, name, label, minimum=Decimal("0"), maximum=Decimal("1000000")):
        raw = self._raw(name).replace(",", "")
        if not raw:
            return self.fail(name, f"{label} is required.")
        try:
            value = Decimal(raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return self.fail(name, f"{label} must be an amount, like 150.00.")
        if value < minimum:
            return self.fail(name, f"{label} cannot be less than {minimum}.")
        if value > maximum:
            return self.fail(name, f"{label} is too large.")
        return self._store(name, value)

    def password(self, name, label="Password"):
        value = self.data.get(name) or ""  # never strip passwords
        if not value:
            return self.fail(name, f"{label} is required.")
        problem = password_problem(value)
        if problem:
            return self.fail(name, problem)
        return self._store(name, value)

    def same(self, name, other, message="The two entries do not match."):
        if (self.data.get(name) or "") != (self.data.get(other) or ""):
            self.fail(name, message)

    def checkbox(self, name) -> bool:
        return self._store(name, 1 if self.data.get(name) in ("1", "on", "true", "yes") else 0)
