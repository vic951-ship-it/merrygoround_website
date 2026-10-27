# Merry-Go-Round Range Selector (starter)

## Run in Termux
```sh
pkg update
pkg install python
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000` in your phone browser.

## What this starter does
- SQLite database persists registrations in `merrygoround.db`.
- Shows five ranges at a time and lets the user page forward indefinitely.
- Shows ranges with registered members in the previously-selected list.
- Enforces a maximum of ten members per range.
- Validates a selected contribution against the range.
- Calculates maintenance as KSh 8 × range number.
- Calculates one-time circle entry fee as the highest amount × 10.
- Stores registrations and round records in SQLite.

## Important limitations before real use
This is a starter, not a production payment or savings platform. It does **not** initiate or confirm M-PESA payments, and it does not yet run a complete round or distribute payouts. Payment status must only be updated by a verified Safaricom Daraja callback after checking the callback result and transaction details. Do not add a public endpoint that lets users mark their own payments as paid.

Before handling real money, add authentication and admin access, HTTPS, CSRF protection, database backups, proper M-PESA STK Push/callback verification, duplicate callback protection, audit logs, and a tested beneficiary-rotation rule. On Render, use a persistent disk and set `DATABASE_PATH` to a file on that disk; otherwise a local SQLite database may be lost on redeploy/restart.
