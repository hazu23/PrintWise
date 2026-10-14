"""Fictional demo data. Every name here is made up; delete it before using real clients."""
import random
from datetime import timedelta

from app.db import db, now
from app.models import (Admin, Customer, InventoryItem, Order, OrderStatusLog, PrintShop, Service,
                        ShopOwner, Transaction, User)
from app.uploads import FileStore
from flask import current_app
from pathlib import Path

MINIMAL_PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
               b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")

SHOPS = [
    ("Inkwell Print Hub", "inkwell", "Demo address 1, Sta. Cruz, Laguna", "Mon-Sat 8:00 AM - 7:00 PM"),
    ("Bubukal Copy Corner", "bubukal", "Demo address 2, Brgy. Bubukal, Sta. Cruz, Laguna", "Mon-Sat 7:30 AM - 6:30 PM"),
    ("Campus Print & Photo", "campus", "Demo address 3, near the university, Sta. Cruz, Laguna", "Mon-Fri 8:00 AM - 8:00 PM"),
    ("Quickpage Digital Prints", "quickpage", "Demo address 4, Sta. Cruz, Laguna", "Daily 9:00 AM - 6:00 PM"),
]
STOCK = [
    ("Short bond paper", "paper", "reams", 20, 5),
    ("A4 bond paper", "paper", "reams", 12, 4),
    ("Glossy photo paper 4R", "paper", "sheets", 150, 50),
    ("Black ink", "ink", "bottles", 3, 2),
    ("Cyan ink", "ink", "bottles", 1, 2),
]


def seed_demo() -> list:
    lines = []
    if User.count(role="admin") == 0:
        admin = Admin(full_name="PrintWise Admin", username="admin", email="admin@printwise.local", email_verified=1)
        admin.set_password("Admin@1234")
        admin.save()
        lines.append("Admin       username: admin       password: Admin@1234")

    if PrintShop.count() > 0:
        lines.append("Demo shops already exist, so no more were added.")
        return lines

    customers = []
    for name, username in (("Juan Dela Cruz", "juan"), ("Maria Santos", "maria")):
        customer = Customer(full_name=name, username=username, email=f"{username}@example.com", email_verified=1)
        customer.set_password("Customer@1234")
        customer.save()
        customers.append(customer)
    lines.append("Customers   usernames: juan, maria   password: Customer@1234")

    methods = ["cash", "cash", "gcash", "cash", "maya"]
    random.seed(7)
    first_shop_owner = None
    for index, (name, slug, address, hours) in enumerate(SHOPS):
        shop = PrintShop(name=name, address=address, hours=hours, contact_phone="0917 000 0000",
                         description="Demo shop for testing. Replace it with a real client.").save()
        owner = ShopOwner(full_name=f"{name} Owner", username=slug, email=f"{slug}@example.com",
                          shop_id=shop.id, email_verified=1)
        owner.set_password("Shop@1234")
        owner.save()
        Service(shop_id=shop.id, name="Document printing", description="Reports, school papers and forms.",
                paper_sizes="Short (8.5 x 11 in),A4 (8.3 x 11.7 in),Long (8.5 x 13 in)",
                paper_types="Bond paper,Cartolina", color_modes="bw,color").save()
        photo = Service(shop_id=shop.id, name="Photo printing", description="Photos on photo paper.",
                        paper_sizes="Photo 4R (4 x 6 in),Photo 5R (5 x 7 in),Photo 8R (8 x 10 in)",
                        paper_types="Glossy photo paper,Matte photo paper", color_modes="color").save()
        for item_name, category, unit, quantity, low in STOCK:
            item = InventoryItem(shop_id=shop.id, name=item_name, category=category, unit=unit,
                                 quantity=0, low_stock_level=low).save()
            item.adjust(quantity, "Starting stock", owner.id)
        if index == 0:
            first_shop_owner = owner
            _seed_orders(shop, owner, customers, Service.find_by(shop_id=shop.id, name="Document printing"), photo, methods)
    lines.append("Shop owners usernames: " + ", ".join(s[1] for s in SHOPS) + "   password: Shop@1234")
    return lines


def _seed_orders(shop, owner, customers, document_service, photo_service, methods):
    """A spread of orders in every status, plus two weeks of payments for the sales page."""
    folder = Path(current_app.config["UPLOAD_DIR"])
    folder.mkdir(parents=True, exist_ok=True)
    plan = (["completed"] * 14) + ["ready", "ready", "printing", "accepted", "pending", "pending", "rejected"]
    for number, status in enumerate(plan):
        customer = customers[number % 2]
        service = document_service if number % 4 else photo_service
        when = now() - timedelta(days=(number * 14) // len(plan), hours=number % 5)
        stored = f"demo-{number}.pdf"
        (folder / stored).write_bytes(MINIMAL_PDF)
        is_photo = service.id == photo_service.id
        order = Order(
            customer_id=customer.id, shop_id=shop.id, service_id=service.id, service_name=service.name,
            paper_size="Photo 4R (4 x 6 in)" if is_photo else "Short (8.5 x 11 in)",
            paper_type="Glossy photo paper" if is_photo else "Bond paper",
            color_mode="color" if is_photo else ("bw" if number % 3 else "color"),
            sides="single" if is_photo else "double", copies=1 + number % 4, pages=None if is_photo else 5 + number,
            file_name=f"{'photos' if is_photo else 'report'}-{number + 1}.pdf", file_stored=stored,
            file_size=len(MINIMAL_PDF), status=status, created_at=when,
            status_note="Demo: file was unreadable" if status == "rejected" else None,
            completed_at=when + timedelta(hours=3) if status == "completed" else None).save()
        order.order_no = f"PW-{when:%y%m}-{order.id:05d}"
        order.save()
        OrderStatusLog(order_id=order.id, status="pending", note="Order submitted", changed_by=customer.id,
                       created_at=when).save()
        if status != "pending":
            OrderStatusLog(order_id=order.id, status=status, changed_by=owner.id,
                           created_at=when + timedelta(hours=1)).save()
        if status == "completed":
            payment = Transaction(order_id=order.id, shop_id=shop.id, amount=round(25 + number * 11.5, 2),
                                  method=methods[number % len(methods)], received_by=owner.id,
                                  created_at=when + timedelta(hours=3)).save()
            payment.receipt_no = f"OR-{payment.id:06d}"
            payment.save()
