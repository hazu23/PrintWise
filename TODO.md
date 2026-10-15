# PrintWise Development To-Do List

This checklist tracks the project from the current beginner-friendly Flask prototype toward a usable print-order website.

## Completed

- [x] Set up a Flask application with separate customer, staff, admin, and authentication page groups.
- [x] Connect the application to MySQL through PyMySQL and environment-based settings.
- [x] Create customer registration and login pages.
- [x] Hash passwords before saving them to the database.
- [x] Add logout and basic role checks for customer, staff, and admin routes.
- [x] Build the initial login and registration page styling.
- [x] Choose a light color palette: navy, print blue, coral, white, and soft gray.
- [x] Create a palette/design preview page at `/design-preview`.
- [x] Add starter page and route scaffolding for customer, staff, and admin sections.
- [x] Write beginner-focused setup instructions in `README.md`.

## Next: Make customer orders work

- [ ] Add database tables for printshops, print services, orders, and quotations.
- [ ] Show printshops and their available services from MySQL instead of placeholder content.
- [ ] Let a customer select a printshop and service, enter job details, and submit an order request.
- [ ] Save order requests and show their status on the customer dashboard and order history.
- [ ] Let staff view incoming orders and update their status.
- [ ] Let staff prepare a quotation with price and turnaround time.
- [ ] Let customers review a quotation and accept or decline it.

## Account and role management

- [ ] Add a safe admin-only way to create or promote staff and admin accounts.
- [ ] Add account profile and password-change pages.
- [ ] Add password reset and email verification.
- [ ] Improve form validation and add CSRF protection.
- [ ] Make the login and registration flow report database errors clearly without exposing sensitive details.

## Printshop management

- [ ] Let staff manage their printshop profile and services.
- [ ] Support user-owned templates or static assets, with each account's files kept separate and access-controlled.
- [ ] Add upload validation, file size limits, and safe storage for customer print files.
- [ ] Show uploaded files and order details to the right customer and printshop staff only.

## Finish and launch

- [ ] Replace placeholder dashboard cards and tables with real database information.
- [ ] Check the layout on mobile and improve accessibility, including labels, keyboard focus, and contrast.
- [ ] Add a dark mode later, as planned.
- [ ] Add automated tests for registration, login, permissions, orders, and quotations.
- [ ] Choose and configure production hosting and a production MySQL database.
- [ ] Set production secrets, disable Flask debug mode, and configure HTTPS and backups.
- [ ] Create a simple deployment guide and verify the app from a clean setup.

## Design follow-up

- [ ] Decide whether to add the PrintWise logo. The supplied logo was reviewed but is not currently in the website.
