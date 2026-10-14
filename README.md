# PrintWise

A centralized platform for print shops. Customers send print jobs (file, paper size, paper type, color, copies) to a partner shop and follow the status until pickup. Shops run their order queue, record payments at the counter, and manage services and inventory. An administrator registers the shop clients.

Final project for IPT, OOP and Web Systems and Technologies, Laguna University, College of Computing Studies, 1st semester AY 2026-2027.

**Stack:** Flask (Python), MySQL, HTML5, CSS3, Bootstrap 5, JavaScript.

---

## 1. Set up and run (Windows with XAMPP)

You need Python 3.11 or newer and XAMPP (for MySQL). Commands below are for Command Prompt or PowerShell. On macOS or Linux use `python3` and `source venv/bin/activate`.

1. **Start MySQL.** Open the XAMPP Control Panel and click *Start* next to MySQL.
2. **Open a terminal in the project folder** (the folder that contains `run.py`).
3. **Create a virtual environment and install the packages:**
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Create your settings file.** Copy `.env.example` to a new file named `.env`. Set `SECRET_KEY` to a long random text. You can make one with:
   ```
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   XAMPP's MySQL uses user `root` with an empty password, which is already the default in the file. If you set a MySQL password, put it in `DB_PASSWORD`.
5. **Create the database and tables:**
   ```
   flask --app run init-db
   ```
   (If `flask` is not found, use `python -m flask --app run init-db`.)
6. **Create the administrator account:**
   ```
   flask --app run create-admin
   ```
   or add fictional demo data (an admin, 4 demo shops, 2 customers, sample orders and payments):
   ```
   flask --app run seed-demo
   ```
7. **Run the site:**
   ```
   python run.py
   ```
   Open http://127.0.0.1:5000

**Prefer phpMyAdmin?** Create a database named `printwise`, open it, choose *Import*, and select `database/schema.sql`. Then continue from step 6.

**Start over:** `flask --app run init-db --reset` deletes all tables and data after asking you to confirm.

### Demo accounts (only after `seed-demo`)

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `Admin@1234` |
| Shop owner (4 shops) | `inkwell`, `bubukal`, `campus`, `quickpage` | `Shop@1234` |
| Customer | `juan`, `maria` | `Customer@1234` |

These shops are fictional. **Delete them before using real clients** (log in as admin, open *Print shops*, and delete each demo shop). Change the admin password from *Profile*.

### Real emails (SMTP)

By default no email account is set, so emails are **printed in the terminal** where `python run.py` is running (open the link from there). To send real emails, edit `.env`. For Gmail: turn on 2-Step Verification, create an *App password* at myaccount.google.com/apppasswords, then set `MAIL_USERNAME` to your Gmail address and `MAIL_PASSWORD` to the app password. Restart the server.

### Run the automated tests

```
python -m unittest discover -s tests -v
```

The tests use a temporary SQLite database, so they never touch your MySQL data. (SQLite is used only for tests. The real app runs on MySQL.)

### Internet needed in the browser

Bootstrap, Bootstrap Icons and the two Google Fonts load from a CDN, so the browser needs internet. For a defense without Wi-Fi, download those files into `app/static/vendor/` and point the `<link>` and `<script>` tags in `app/templates/base.html` to them.

---

## 2. How the system works

**Three kinds of account**

| Role | Created by | Can do |
|---|---|---|
| Customer | Registers on the site | Choose a shop and service, upload a file, set size/paper/color/sides/copies, track the status, edit or cancel while the shop has not accepted it, delete cancelled or declined orders |
| Shop owner | Administrator | Work the order queue, accept/print/ready/decline, record the payment at the counter, manage services, track inventory by hand, see sales and download a CSV |
| Administrator | `create-admin` command | Add shop clients and their owner accounts, hide or delete shops, manage and reset accounts, see all orders |

**Order flow:** Submitted, Accepted, Printing, Ready for pickup, Completed (or Declined / Cancelled). **Prices are not shown online.** The shop tells the customer the price at the counter and records the payment, which completes the order and creates a receipt number. This matches what the partner shops asked for.

**Shop accounts:** the administrator creates the shop and its owner with a temporary password (shown once). At first login the owner is forced to choose their own username and password.

**Inventory** is updated by hand (add or remove stock with a reason), with a log and a low-stock warning. It is not deducted automatically, because busy shops cannot count every sheet.

---

## 3. Where each required feature lives

| # | Required feature | Where to look |
|---|---|---|
| 1 | Own logo and branding | `app/static/img/logo-mark.svg`, `favicon.svg`, `app/static/css/app.css` (CMYK ink palette, press-run tracker), used in every layout in `app/templates/layouts/` |
| 2 | Index / home page | `app/templates/public/index.html`, route in `app/blueprints/public.py` |
| 3 | Registration | `app/blueprints/auth.py` (`register`), `app/templates/auth/register.html` |
| 4 | Login | `auth.py` (`login`): generic error message, lockout after 5 wrong attempts |
| 5 | Web security | Password hashing `app/models/user.py`; CSRF, headers, open-redirect guard `app/security.py`; parameterized SQL only `app/db.py` and `app/models/base.py`; Jinja auto-escaping for XSS; safe uploads `app/uploads.py` |
| 6 | Session management | `app/security.py` (`login_user`, `load_current_user`, `login_required`, `roles_required`); 2-hour session, HttpOnly + SameSite cookie, new session on login, POST-only logout |
| 7 | SMTP email | `app/mailer.py`, wording in `app/notifications.py`: account confirmation, password reset, new-order alert to shop, status updates to customer, shop account created |
| 8 | Dashboard | One per role: `templates/customer/dashboard.html`, `shop/dashboard.html`, `admin/dashboard.html` |
| 9 | Profile management | `app/blueprints/account.py`: details, email re-confirmation, password change, photo upload |
| 10 | CRUD | Orders (`customer.py`), services and inventory (`shop.py`), shops and accounts (`admin.py`) |
| 11 | Responsive UI | Bootstrap grid, collapsing sidebar (offcanvas on phones), responsive tables |
| 12 | Validation and error handling | Server: `app/validators.py`. Client: HTML5 attributes plus `app/static/js/app.js`. Friendly 400/403/404/413/500 pages in `app/__init__.py` |
| 13 | OOP | See below |

### OOP in this project (for your defense)

- **Inheritance.** `Model` (`app/models/base.py`) is the parent of every table class. It holds the shared create, read, update, delete code once. `Customer`, `ShopOwner` and `Admin` inherit from `User` (`app/models/user.py`).
- **Encapsulation.** Passwords are only handled through `User.set_password()` and `User.check_password()`. Nothing else touches `password_hash`, and `to_dict()` hides it. Business rules live inside the classes: `Order.change_status()` refuses illegal jumps, `Order.complete_with_payment()` records the payment and closes the order in one transaction, `InventoryItem.adjust()` refuses to go below zero.
- **Polymorphism.** Loading a row through `User.get()` returns the right subclass. Every account answers `home_endpoint()` differently, so the login code just redirects to `user.home_endpoint()`.
- **Other classes.** `Database` (`app/db.py`), `FormValidator` (`app/validators.py`), `FileStore` (`app/uploads.py`), `SalesReport` (`app/models/order.py`), `Pagination` (`app/utils.py`).

### Request flow (useful to explain)

Browser request, then `before_request` checks the CSRF token and loads the logged-in user, then the route function in a blueprint validates input with `FormValidator`, works through model objects, and renders a Jinja template. Errors raise friendly pages.

---

## 4. Project structure

```
printwise/
  run.py                 start the server
  config.py              settings (read from .env)
  requirements.txt
  .env.example
  database/schema.sql    MySQL tables
  app/
    __init__.py          create_app(), error pages, template filters
    db.py                Database class (parameterized SQL)
    security.py          CSRF, sessions, access control, tokens, headers
    validators.py        server-side form validation
    mailer.py            email sending (SMTP / console)
    notifications.py     wording of emails and in-app notifications
    uploads.py           safe file uploads
    catalog.py           paper sizes, types, payment methods, ...
    cli.py, seed.py      init-db, create-admin, seed-demo
    models/              User/Customer/ShopOwner/Admin, PrintShop, Service,
                         Order, Transaction, InventoryItem, Notification
    blueprints/          public, auth, account, customer, shop, admin
    templates/           Jinja pages (layouts, per-role folders, emails)
    static/              css, js, images
  tests/test_app.py      73 automated tests
  docs/                  client interview notes and sign-off form (templates)
```

---

## 5. Client engagement documents

Required by the project guidelines. Fill them in for each partner shop and include them in your submission:

- `docs/client-interview-notes.md` (already contains what the shops told you)
- `docs/client-signoff.md` (short acknowledgment the owner signs after trying the system)

---

## 6. Limitations

- Payments are **recorded**, not processed. There is no online payment.
- Pickup only. There is no delivery.
- Uploaded files are stored on the server's disk in `instance/uploads/`, not scanned for viruses.
- Set `SESSION_COOKIE_SECURE=true` and serve over HTTPS before putting this on the internet, and do not use `debug=True` (in `run.py`) in production.
