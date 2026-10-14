# Client requirements interview notes

**Project:** PrintWise, a centralized platform for printing businesses
**Prepared by:** ______________________ (student name)

## Client details

| | |
|---|---|
| Shop / business name | |
| Owner or contact person | |
| Address | |
| Contact number or email | |
| Date of interview | |
| How it was held (in person, call, chat) | |

> Repeat this page for each of the 3 to 5 partner shops.

## Questions and answers

**1. What services and paper sizes do you offer, and how do you handle prices?**
The shop does not want the price shown to the customer right after they upload a file. Instead, the system shows the printing status. The shop states the price when the customer is physically at the shop.
*Reflected in PrintWise:* customers never see a price online. The shop records the amount received at the counter, which completes the order and creates a receipt number.

**2. How do you take orders now?**
Orders should come through the system we are building. Customers upload their files and choose specifications such as size, quantity and color.
*Reflected in PrintWise:* the order form (service, paper size, paper type, color, sides, copies, pages, notes, file upload) and the shop's order queue.

**3. What are your biggest problems today?**
Transaction tracking, inventory management, handling customer orders, and unorganized operations.
*Reflected in PrintWise:*
- Transaction tracking: payments recorded per order, receipt numbers, daily and monthly sales, CSV download.
- Inventory management: paper and ink stock with a history of changes and a low-stock warning. Quantities are updated by hand, because the shop is too busy to count every sheet.
- Customer orders and unorganized operations: one order queue with statuses, filters and search; customers get email updates, so they do not need to ask.

**4. Would you try the system and give a short sign-off at the end?**
Yes.

## Decisions agreed with the client

- Inventory is updated manually (no automatic deduction).
- The administrator creates the shop account first. The owner then changes their own username and password at first login.
- Payment is made at the shop. Pickup only.

## Other notes from the discussion

(Write anything else the client mentioned: special services, busy hours, concerns.)

&nbsp;

&nbsp;
