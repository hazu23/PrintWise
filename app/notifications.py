"""Messages sent to users: in-app notifications and emails.

Keeping all the wording here means the blueprints stay short and every
message uses the same plain voice.
"""
from flask import current_app, url_for

from app.mailer import send_email
from app.models import Notification
from app.security import make_token

VERIFY_MAX_AGE = 3 * 24 * 3600
RESET_MAX_AGE = 60 * 60


def absolute_url(endpoint: str, **values) -> str:
    return current_app.config["APP_BASE_URL"] + url_for(endpoint, **values)


def notify(user, title: str, message: str, link: str = None) -> None:
    """Add an in-app notification (the bell icon)."""
    Notification(user_id=user.id, title=title[:120], message=message[:255], link=link).save()


# ----- accounts ------------------------------------------------------------
def send_verification_email(user) -> None:
    token = make_token("verify", {"uid": user.id, "email": user.email})
    send_email(
        user.email, "Confirm your PrintWise email", f"Welcome to PrintWise, {user.first_name}",
        ["Confirm your email address so we can send you updates about your print orders.",
         "This link works for 3 days."],
        absolute_url("auth.verify_email", token=token), "Confirm my email",
    )


def send_password_reset_email(user) -> None:
    token = make_token("reset", {"uid": user.id, "ph": (user.password_hash or "")[-12:]})
    send_email(
        user.email, "Reset your PrintWise password", "Reset your password",
        ["We received a request to reset the password for your account.",
         "This link works for 1 hour and can be used once. If you did not ask for it, you can ignore this email."],
        absolute_url("auth.reset_password", token=token), "Choose a new password",
    )


def send_shop_account_email(owner, shop) -> None:
    send_email(
        owner.email, "Your PrintWise shop account is ready", f"{shop.name} is now on PrintWise",
        [f"Your username is: {owner.username}",
         "The administrator will give you a temporary password. You will be asked to choose your own "
         "username and password the first time you log in."],
        absolute_url("auth.login"), "Go to log in",
    )


# ----- orders ----------------------------------------------------------------
def notify_shop_of_new_order(order, shop_owners) -> None:
    link = url_for("shop.order_detail", order_id=order.id)
    for owner in shop_owners:
        notify(owner, "New print order", f"{order.order_no}: {order.service_name} from {order.customer_name}", link)
        send_email(
            owner.email, f"New order {order.order_no}", "You have a new print order",
            [f"{order.customer_name} sent a file for {order.service_name}.", order.spec_summary,
             f"Copies: {order.copies}"],
            absolute_url("shop.order_detail", order_id=order.id), "Open the order",
        )


STATUS_MESSAGES = {
    "accepted": "The shop accepted your order and will start soon.",
    "printing": "Your order is being printed now.",
    "ready": "Your order is ready. Visit the shop to pick it up and pay at the counter.",
    "completed": "Your order is complete. Thank you for using PrintWise.",
    "rejected": "The shop could not take this order.",
}


def notify_customer_of_status(order, customer, shop_name: str) -> None:
    text = STATUS_MESSAGES.get(order.status, f"Status: {order.status_label}.")
    if order.status == "rejected" and order.status_note:
        text += f" Reason: {order.status_note}"
    link = url_for("customer.order_detail", order_id=order.id)
    notify(customer, f"{order.order_no}: {order.status_label}", text, link)
    send_email(
        customer.email, f"Order {order.order_no}: {order.status_label}", f"Your order is {order.status_label.lower()}",
        [text, f"Shop: {shop_name}"],
        absolute_url("customer.order_detail", order_id=order.id), "Track my order",
    )
