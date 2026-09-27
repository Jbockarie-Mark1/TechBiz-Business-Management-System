# TechBiz Business Management System — Local MVP v2

A working business-management web app built first for printing and desktop publishing, but designed so the same codebase can be customized for other businesses.

## Main features
- Secure session login and password change
- Dashboard KPIs and low-stock alerts
- Customer directory, profile, sales/payment/job history and outstanding balances
- Sales with multiple line items, invoices/receipts and follow-up payments
- Stock-aware sales validation and automatic stock deduction
- Products, raw materials, services and stock movement history
- Supplier directory and purchases that automatically increase stock
- Printing/desktop publishing production jobs and workflow status
- Expenses and derived cashbook
- Financial reports, receivables, gross-profit estimate and CSV sales export
- Users, roles and audit activity
- Business branding, currency, business type and module toggles
- `business_id` / tenant separation on operational data for future multi-business hosting
- SQLite locally, PostgreSQL-ready for hosting
- Docker and Docker Compose support

## Run locally with Python

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open: http://127.0.0.1:8000

Initial local login:
- Username: `admin`
- Password: `ChangeMe123!`

Change the password immediately in Business Settings.

## Run with Docker

```bash
docker compose up --build
```

Open: http://localhost:8000

## Hosting later
For production, set a strong `SESSION_SECRET`, change the owner password, and set `DATABASE_URL` to a PostgreSQL database. The app is already structured so the SQLite database can be replaced without rewriting the application.
