# PrintWise

PrintWise is a beginner-friendly Flask project for a printing business. A customer can create an account, log in, and view the customer pages. The project uses Python, Flask, HTML, CSS, and MySQL.

## Run the project

You need Python 3.10 or newer.

1. Open a terminal in the folder that contains `app.py`.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install the packages:

   ```powershell
   pip install -r requirements.txt
   ```

4. Start your MySQL server (for example, from the XAMPP Control Panel).
5. In MySQL Workbench, create the `printwise` database if it does not exist, then run `schema.sql` to create the app's MySQL account and permissions.
6. Copy `.env.example` to `.env` and set its database username and password to match the MySQL account you are using.
7. Start the website:

   ```powershell
   python run.py
   ```

8. Open <http://127.0.0.1:5000> and choose **Create account**.

The app checks for the `users` table when it starts and creates it if needed. If the table is from an older version, the app adds a username column and gives existing accounts a temporary username such as `user12`. This update needs `ALTER` and `UPDATE` permission, which `schema.sql` grants to the app account. Run the updated `schema.sql` again if you already created that account before adding usernames. MySQL stores account data in the `printwise` database, which you can view in Workbench.

## Beginner project map

```text
app.py                 Creates the Flask app and registers the pages
config.py              Loads settings, including the session secret
run.py                 Starts the local development server
users/
  __init__.py          Creates the page groups called Blueprints
  auth.py              Registration, login, logout, and role checks
  db.py                Connects to MySQL and creates the users table
  admin/admin.py       Admin page routes
  staff/staff.py       Staff page routes
  user/user.py         Customer page routes
templates/
  base.html             Shared page layout and navigation
  auth/                 Login and registration forms
  admin/, staff/, user/ Role-specific HTML pages
static/
  css/                  Shared styling and the palette preview
```

## What account registration does

- New registrations receive the `customer` role. People cannot choose admin or staff access from the public form.
- Each account has a unique username, but people still log in with their email address.
- Passwords are saved as password hashes, not as readable text.
- Login details are kept in Flask's session cookie.
- Customer, staff, and admin page routes check the role before showing a page.
- Admin and staff account creation is not built yet. Those roles will need a controlled setup step in a later feature.

The database connection uses PyMySQL. The `.env` file holds local connection settings and is ignored by Git. Do not commit your real database password or secret key.

## Main URLs

- `/` — home page
- `/register` — create a customer account
- `/login` — log in
- `/user/dashboard` — customer dashboard (login required)
- `/staff/dashboard` — staff dashboard (staff role required)
- `/admin/dashboard` — admin dashboard (admin role required)
- `/design-preview` — the sample color palette dashboard

This is a learning project. Before using it for real customers, add stronger form protection, password reset, account verification, and a controlled way to create staff and admin accounts. Turn off Flask debug mode before deployment.
