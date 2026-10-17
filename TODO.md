# To-do List

## Completed

- [x] Set up a Flask application with separate customer, staff, admin, and authentication page groups.
- [x] Connect the application to MySQL through PyMySQL and environment-based settings.
- [x] Create customer registration and login pages
- [x] Add a unique username field to customer registration
- [x] Hash passwords before saving them to the database
- [x] Add logout and basic role checks for customer, staff, and admin routes.
- [x] Build the initial login and registration page styling.
- [x] Choose a light color palette: navy, print blue, coral, white, and soft gray
- [x] Create a palette/design preview page at `/design-preview`.
- [x] Add starter page and route scaffolding for customer, staff, and admin sections
- [x] Write beginner-focused setup instructions in `README.md`

## Make customer orders work

- [x] Add a database table for printshops and sample listings
- [x] Show active printshops from MySQL on the customer printshop page
- [ ] Add database tables for print services and orders
- [ ] Show each printshop's available services from MySQL
- [ ] Let a customer select a printshop and service, enter job details, and submit an order request
- [ ] Save order requests and show their status on the customer dashboard and order history
- [ ] Let staff view incoming orders and update their status

## Account and role management

- [ ] Add a safe admin-only way to create staff and admin accounts.
- [ ] Add account profile and password-change pages.
- [ ] Add password reset and email verification.
- [ ] Improve form validation and add CSRF protection.
- [ ] Make the login and registration flow report database errors clearly without exposing sensitive details.

## Printshop management

- [ ] Let staff manage their printshop profile and services.
- [ ] Add upload validation, file size limits, and safe storage for customer print files.
- [ ] Show uploaded files and order details to the right customer and printshop staff only.

## Visuals

- [ ] Add a dark mode later, as planned
- [ ] Add the logo
