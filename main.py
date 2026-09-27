import csv
import hashlib
import io
import json
import os
import secrets
from datetime import date, datetime
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'techbiz.db')}")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Business(Base):
    __tablename__ = "businesses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="TechBiz")
    business_type: Mapped[str] = mapped_column(String(120), default="Printing & Desktop Publishing")
    currency: Mapped[str] = mapped_column(String(12), default="SLE")
    phone: Mapped[str] = mapped_column(String(60), default="")
    email: Mapped[str] = mapped_column(String(140), default="")
    address: Mapped[str] = mapped_column(String(255), default="Freetown, Sierra Leone")
    receipt_footer: Mapped[str] = mapped_column(String(255), default="Thank you for your business.")
    theme_primary: Mapped[str] = mapped_column(String(20), default="#c8102e")
    modules_json: Mapped[str] = mapped_column(Text, default='["sales","customers","jobs","inventory","suppliers","expenses","reports"]')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Administrator")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="Owner")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    phone: Mapped[str] = mapped_column(String(60), default="")
    email: Mapped[str] = mapped_column(String(140), default="")
    company: Mapped[str] = mapped_column(String(160), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    phone: Mapped[str] = mapped_column(String(60), default="")
    email: Mapped[str] = mapped_column(String(140), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    sku: Mapped[str] = mapped_column(String(80), default="")
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(100), default="General")
    item_type: Mapped[str] = mapped_column(String(20), default="product")
    unit: Mapped[str] = mapped_column(String(30), default="unit")
    cost_price: Mapped[float] = mapped_column(Float, default=0)
    sale_price: Mapped[float] = mapped_column(Float, default=0)
    stock_qty: Mapped[float] = mapped_column(Float, default=0)
    min_stock: Mapped[float] = mapped_column(Float, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(30))
    qty: Mapped[float] = mapped_column(Float)
    reference: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    product = relationship("Product")


class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    invoice_no: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    total: Mapped[float] = mapped_column(Float, default=0)
    amount_paid: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[str] = mapped_column(String(50), default="Cash")
    status: Mapped[str] = mapped_column(String(30), default="Unpaid")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer = relationship("Customer")
    items = relationship("SaleItem", cascade="all, delete-orphan", back_populates="sale")
    payments = relationship("Payment", cascade="all, delete-orphan", back_populates="sale")


class SaleItem(Base):
    __tablename__ = "sale_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    cost_price: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(50), default="Cash")
    reference: Mapped[str] = mapped_column(String(100), default="")
    payment_date: Mapped[str] = mapped_column(String(20), default=lambda: date.today().isoformat())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sale = relationship("Sale", back_populates="payments")


class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    purchase_no: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    supplier_invoice: Mapped[str] = mapped_column(String(100), default="")
    total: Mapped[float] = mapped_column(Float, default=0)
    amount_paid: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[str] = mapped_column(String(50), default="Cash")
    purchase_date: Mapped[str] = mapped_column(String(20), default=lambda: date.today().isoformat())
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    supplier = relationship("Supplier")
    items = relationship("PurchaseItem", cascade="all, delete-orphan", back_populates="purchase")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    purchase = relationship("Purchase", back_populates="items")
    product = relationship("Product")


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    category: Mapped[str] = mapped_column(String(100), default="General")
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[str] = mapped_column(String(50), default="Cash")
    expense_date: Mapped[str] = mapped_column(String(20), default=lambda: date.today().isoformat())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrintJob(Base):
    __tablename__ = "print_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    job_no: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    job_type: Mapped[str] = mapped_column(String(100), default="Printing")
    quantity: Mapped[float] = mapped_column(Float, default=1)
    size: Mapped[str] = mapped_column(String(80), default="")
    material: Mapped[str] = mapped_column(String(120), default="")
    colour: Mapped[str] = mapped_column(String(50), default="Full Colour")
    sides: Mapped[str] = mapped_column(String(50), default="Single-sided")
    finishing: Mapped[str] = mapped_column(String(180), default="")
    design_required: Mapped[bool] = mapped_column(Boolean, default=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    deposit: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(60), default="New")
    due_date: Mapped[str] = mapped_column(String(20), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer = relationship("Customer")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, value = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000)
        return secrets.compare_digest(dk.hex(), value)
    except Exception:
        return False


def make_ref(prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]}"


def seed() -> None:
    db = SessionLocal()
    try:
        business = db.scalar(select(Business).limit(1))
        if not business:
            business = Business()
            db.add(business)
            db.commit()
            db.refresh(business)
        if not db.scalar(select(User).where(User.username == "admin")):
            db.add(User(
                business_id=business.id,
                username="admin",
                display_name="Business Owner",
                password_hash=hash_password(os.getenv("ADMIN_PASSWORD", "ChangeMe123!")),
                role="Owner",
            ))
        count = db.scalar(select(func.count()).select_from(Product).where(Product.business_id == business.id)) or 0
        if count == 0:
            db.add_all([
                Product(business_id=business.id, sku="SRV-001", name="Graphic Design", category="Design", item_type="service", unit="job", sale_price=150),
                Product(business_id=business.id, sku="SRV-002", name="A4 Colour Printing", category="Printing", item_type="service", unit="page", sale_price=10),
                Product(business_id=business.id, sku="SRV-003", name="Black & White Printing", category="Printing", item_type="service", unit="page", sale_price=2),
                Product(business_id=business.id, sku="MAT-001", name="A4 80gsm Paper", category="Paper", item_type="product", unit="ream", cost_price=110, sale_price=140, stock_qty=10, min_stock=3),
                Product(business_id=business.id, sku="MAT-002", name="A3 80gsm Paper", category="Paper", item_type="product", unit="ream", cost_price=180, sale_price=220, stock_qty=5, min_stock=2),
                Product(business_id=business.id, sku="MAT-003", name="Laminating Pouch A4", category="Finishing", item_type="product", unit="pack", cost_price=200, sale_price=260, stock_qty=4, min_stock=2),
            ])
        db.commit()
    finally:
        db.close()


seed()

app = FastAPI(title="TechBiz Business Management System", version="2.0")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "local-dev-secret-change-before-hosting"), same_site="lax")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def money(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


templates.env.filters["money"] = money


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, db: Session) -> Optional[User]:
    uid = request.session.get("user_id")
    return db.get(User, uid) if uid else None


def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if not user or not user.active:
        raise HTTPException(status_code=401)
    return user


def business_modules(business: Business) -> list[str]:
    try:
        return json.loads(business.modules_json or "[]")
    except Exception:
        return ["sales", "customers", "jobs", "inventory", "suppliers", "expenses", "reports"]


def ctx(request: Request, db: Session, **extra):
    user = current_user(request, db)
    business = db.get(Business, user.business_id) if user else None
    return {
        "request": request,
        "user": user,
        "business": business,
        "modules": business_modules(business) if business else [],
        "today": date.today().isoformat(),
        **extra,
    }


def log_action(db: Session, user: User, action: str, details: str = "") -> None:
    db.add(AuditLog(business_id=user.business_id, user_id=user.id, action=action, details=details[:255]))


def sale_status(total: float, paid: float) -> str:
    if paid <= 0:
        return "Unpaid"
    if paid + 0.0001 >= total:
        return "Paid"
    return "Part Paid"


@app.exception_handler(401)
async def unauthorized(request: Request, exc):
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username, User.active == True))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid username or password."})
    request.session["user_id"] = user.id
    log_action(db, user, "login", "Signed in")
    db.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    bid = user.business_id
    today_start = datetime.combine(date.today(), datetime.min.time())
    sales_today = float(db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.business_id == bid, Sale.created_at >= today_start)) or 0)
    payments_today = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.business_id == bid, Payment.created_at >= today_start)) or 0)
    expenses_today = float(db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.business_id == bid, Expense.expense_date == date.today().isoformat())) or 0)
    total_sales = float(db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.business_id == bid)) or 0)
    total_paid = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.business_id == bid)) or 0)
    receivables = max(0, total_sales - total_paid)
    open_jobs = db.scalar(select(func.count()).select_from(PrintJob).where(PrintJob.business_id == bid, PrintJob.status.notin_(["Delivered", "Cancelled"]))) or 0
    customer_count = db.scalar(select(func.count()).select_from(Customer).where(Customer.business_id == bid)) or 0
    low_stock = db.scalars(select(Product).where(Product.business_id == bid, Product.item_type == "product", Product.stock_qty <= Product.min_stock).order_by(Product.stock_qty)).all()
    recent_sales = db.scalars(select(Sale).where(Sale.business_id == bid).order_by(Sale.created_at.desc()).limit(7)).all()
    recent_jobs = db.scalars(select(PrintJob).where(PrintJob.business_id == bid).order_by(PrintJob.created_at.desc()).limit(7)).all()
    return templates.TemplateResponse(request, "dashboard.html", ctx(request, db, sales_today=sales_today, payments_today=payments_today, expenses_today=expenses_today, receivables=receivables, open_jobs=open_jobs, customer_count=customer_count, low_stock=low_stock, recent_sales=recent_sales, recent_jobs=recent_jobs))


@app.get("/customers", response_class=HTMLResponse)
def customers(request: Request, q: str = "", db: Session = Depends(get_db)):
    user = require_user(request, db)
    stmt = select(Customer).where(Customer.business_id == user.business_id)
    if q:
        stmt = stmt.where(Customer.name.ilike(f"%{q}%"))
    rows = db.scalars(stmt.order_by(Customer.name)).all()
    balances = {}
    for c in rows:
        total = float(db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.business_id == user.business_id, Sale.customer_id == c.id)) or 0)
        paid = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.business_id == user.business_id, Payment.customer_id == c.id)) or 0)
        balances[c.id] = total - paid
    return templates.TemplateResponse(request, "customers.html", ctx(request, db, customers=rows, balances=balances, q=q))


@app.post("/customers")
def add_customer(request: Request, name: str = Form(...), phone: str = Form(""), email: str = Form(""), company: str = Form(""), address: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    user = require_user(request, db)
    c = Customer(business_id=user.business_id, name=name.strip(), phone=phone.strip(), email=email.strip(), company=company.strip(), address=address.strip(), notes=notes.strip())
    db.add(c)
    log_action(db, user, "customer.create", name)
    db.commit()
    return RedirectResponse("/customers", status_code=303)


@app.get("/customers/{cid}", response_class=HTMLResponse)
def customer_detail(cid: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    customer = db.get(Customer, cid)
    if not customer or customer.business_id != user.business_id:
        raise HTTPException(404)
    sales = db.scalars(select(Sale).where(Sale.business_id == user.business_id, Sale.customer_id == cid).order_by(Sale.created_at.desc())).all()
    payments = db.scalars(select(Payment).where(Payment.business_id == user.business_id, Payment.customer_id == cid).order_by(Payment.created_at.desc())).all()
    jobs = db.scalars(select(PrintJob).where(PrintJob.business_id == user.business_id, PrintJob.customer_id == cid).order_by(PrintJob.created_at.desc())).all()
    total = sum(s.total for s in sales)
    paid = sum(p.amount for p in payments)
    return templates.TemplateResponse(request, "customer_detail.html", ctx(request, db, customer=customer, sales=sales, payments=payments, jobs=jobs, balance=total-paid))


@app.post("/customers/{cid}/edit")
def edit_customer(cid: int, request: Request, name: str = Form(...), phone: str = Form(""), email: str = Form(""), company: str = Form(""), address: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    user = require_user(request, db)
    c = db.get(Customer, cid)
    if not c or c.business_id != user.business_id:
        raise HTTPException(404)
    c.name, c.phone, c.email, c.company, c.address, c.notes = name.strip(), phone.strip(), email.strip(), company.strip(), address.strip(), notes.strip()
    log_action(db, user, "customer.update", c.name)
    db.commit()
    return RedirectResponse(f"/customers/{cid}", status_code=303)


@app.get("/inventory", response_class=HTMLResponse)
def inventory(request: Request, q: str = "", db: Session = Depends(get_db)):
    user = require_user(request, db)
    stmt = select(Product).where(Product.business_id == user.business_id)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    products = db.scalars(stmt.order_by(Product.name)).all()
    return templates.TemplateResponse(request, "inventory.html", ctx(request, db, products=products, q=q))


@app.post("/inventory")
def add_inventory(request: Request, name: str = Form(...), sku: str = Form(""), category: str = Form("General"), item_type: str = Form("product"), unit: str = Form("unit"), cost_price: float = Form(0), sale_price: float = Form(0), stock_qty: float = Form(0), min_stock: float = Form(0), db: Session = Depends(get_db)):
    user = require_user(request, db)
    if item_type not in {"product", "service"}:
        raise HTTPException(400, "Invalid item type")
    p = Product(business_id=user.business_id, name=name.strip(), sku=sku.strip(), category=category.strip(), item_type=item_type, unit=unit.strip(), cost_price=max(0, cost_price), sale_price=max(0, sale_price), stock_qty=max(0, stock_qty if item_type == "product" else 0), min_stock=max(0, min_stock))
    db.add(p)
    db.flush()
    if p.item_type == "product" and p.stock_qty:
        db.add(StockMovement(business_id=user.business_id, product_id=p.id, movement_type="in", qty=p.stock_qty, reference="Opening stock"))
    log_action(db, user, "inventory.create", p.name)
    db.commit()
    return RedirectResponse("/inventory", status_code=303)


@app.post("/inventory/{pid}/adjust")
def adjust_stock(pid: int, request: Request, qty: float = Form(...), movement_type: str = Form("in"), notes: str = Form(""), db: Session = Depends(get_db)):
    user = require_user(request, db)
    p = db.get(Product, pid)
    if not p or p.business_id != user.business_id or p.item_type != "product":
        raise HTTPException(404)
    qty = abs(qty)
    if movement_type == "out" and qty > p.stock_qty:
        return RedirectResponse("/inventory?error=stock", status_code=303)
    delta = qty if movement_type == "in" else -qty
    p.stock_qty += delta
    db.add(StockMovement(business_id=user.business_id, product_id=p.id, movement_type=movement_type, qty=qty, reference="Manual adjustment", notes=notes))
    log_action(db, user, "inventory.adjust", f"{p.name}: {movement_type} {qty}")
    db.commit()
    return RedirectResponse("/inventory", status_code=303)


@app.get("/inventory/{pid}/movements", response_class=HTMLResponse)
def stock_movements(pid: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    p = db.get(Product, pid)
    if not p or p.business_id != user.business_id:
        raise HTTPException(404)
    rows = db.scalars(select(StockMovement).where(StockMovement.business_id == user.business_id, StockMovement.product_id == pid).order_by(StockMovement.created_at.desc())).all()
    return templates.TemplateResponse(request, "stock_movements.html", ctx(request, db, product=p, movements=rows))


@app.get("/sales", response_class=HTMLResponse)
def sales(request: Request, q: str = "", db: Session = Depends(get_db)):
    user = require_user(request, db)
    stmt = select(Sale).where(Sale.business_id == user.business_id)
    if q:
        stmt = stmt.where(Sale.invoice_no.ilike(f"%{q}%"))
    rows = db.scalars(stmt.order_by(Sale.created_at.desc())).all()
    return templates.TemplateResponse(request, "sales.html", ctx(request, db, sales=rows, q=q))


@app.get("/sales/new", response_class=HTMLResponse)
def new_sale(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    customers = db.scalars(select(Customer).where(Customer.business_id == user.business_id).order_by(Customer.name)).all()
    products = db.scalars(select(Product).where(Product.business_id == user.business_id, Product.active == True).order_by(Product.name)).all()
    return templates.TemplateResponse(request, "new_sale.html", ctx(request, db, customers=customers, products=products))


@app.post("/sales/new")
def create_sale(request: Request, customer_id: str = Form(""), payment_method: str = Form("Cash"), amount_paid: float = Form(0), notes: str = Form(""), items_json: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    try:
        raw_items = json.loads(items_json)
    except Exception:
        raw_items = []
    if not raw_items:
        return RedirectResponse("/sales/new?error=items", status_code=303)
    customer = None
    if customer_id:
        customer = db.get(Customer, int(customer_id))
        if not customer or customer.business_id != user.business_id:
            raise HTTPException(400, "Invalid customer")
    prepared = []
    total = 0.0
    for item in raw_items:
        pid = int(item.get("product_id")) if item.get("product_id") else None
        qty = float(item.get("qty") or 0)
        price = float(item.get("unit_price") or 0)
        desc = str(item.get("description") or "Item").strip()
        if qty <= 0 or price < 0:
            continue
        product = None
        cost = 0.0
        if pid:
            product = db.get(Product, pid)
            if not product or product.business_id != user.business_id:
                raise HTTPException(400, "Invalid product")
            desc = product.name if not desc else desc
            cost = product.cost_price
            if product.item_type == "product" and qty > product.stock_qty:
                return RedirectResponse(f"/sales/new?error=stock&item={product.id}", status_code=303)
        line_total = qty * price
        total += line_total
        prepared.append((product, pid, desc, qty, price, cost, line_total))
    if not prepared:
        return RedirectResponse("/sales/new?error=items", status_code=303)
    amount_paid = max(0, min(float(amount_paid), total))
    sale = Sale(business_id=user.business_id, customer_id=customer.id if customer else None, invoice_no=make_ref("INV"), total=total, amount_paid=amount_paid, payment_method=payment_method, status=sale_status(total, amount_paid), notes=notes.strip())
    db.add(sale)
    db.flush()
    for product, pid, desc, qty, price, cost, line_total in prepared:
        db.add(SaleItem(sale_id=sale.id, product_id=pid, description=desc, qty=qty, unit_price=price, cost_price=cost, line_total=line_total))
        if product and product.item_type == "product":
            product.stock_qty -= qty
            db.add(StockMovement(business_id=user.business_id, product_id=product.id, movement_type="sale", qty=qty, reference=sale.invoice_no))
    if amount_paid > 0:
        db.add(Payment(business_id=user.business_id, sale_id=sale.id, customer_id=customer.id if customer else None, amount=amount_paid, method=payment_method, payment_date=date.today().isoformat()))
    log_action(db, user, "sale.create", sale.invoice_no)
    db.commit()
    return RedirectResponse(f"/sales/{sale.id}", status_code=303)


@app.get("/sales/{sid}", response_class=HTMLResponse)
def sale_detail(sid: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    sale = db.get(Sale, sid)
    if not sale or sale.business_id != user.business_id:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "receipt.html", ctx(request, db, sale=sale, balance=max(0, sale.total-sale.amount_paid)))


@app.post("/sales/{sid}/payment")
def add_sale_payment(sid: int, request: Request, amount: float = Form(...), method: str = Form("Cash"), reference: str = Form(""), payment_date: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    sale = db.get(Sale, sid)
    if not sale or sale.business_id != user.business_id:
        raise HTTPException(404)
    balance = max(0, sale.total - sale.amount_paid)
    amount = max(0, min(amount, balance))
    if amount <= 0:
        return RedirectResponse(f"/sales/{sid}?error=payment", status_code=303)
    db.add(Payment(business_id=user.business_id, sale_id=sale.id, customer_id=sale.customer_id, amount=amount, method=method, reference=reference.strip(), payment_date=payment_date))
    sale.amount_paid += amount
    sale.status = sale_status(sale.total, sale.amount_paid)
    log_action(db, user, "payment.create", f"{sale.invoice_no}: {amount}")
    db.commit()
    return RedirectResponse(f"/sales/{sid}", status_code=303)


@app.get("/jobs", response_class=HTMLResponse)
def jobs(request: Request, status: str = "", db: Session = Depends(get_db)):
    user = require_user(request, db)
    stmt = select(PrintJob).where(PrintJob.business_id == user.business_id)
    if status:
        stmt = stmt.where(PrintJob.status == status)
    rows = db.scalars(stmt.order_by(PrintJob.created_at.desc())).all()
    customers = db.scalars(select(Customer).where(Customer.business_id == user.business_id).order_by(Customer.name)).all()
    statuses = ["New", "Design", "Awaiting Approval", "Approved", "Printing", "Finishing", "Ready", "Delivered", "Cancelled"]
    return templates.TemplateResponse(request, "jobs.html", ctx(request, db, jobs=rows, customers=customers, statuses=statuses, active_status=status))


@app.post("/jobs")
def add_job(request: Request, customer_id: str = Form(""), title: str = Form(...), job_type: str = Form("Printing"), quantity: float = Form(1), size: str = Form(""), material: str = Form(""), colour: str = Form("Full Colour"), sides: str = Form("Single-sided"), finishing: str = Form(""), design_required: Optional[str] = Form(None), total_amount: float = Form(0), deposit: float = Form(0), due_date: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    user = require_user(request, db)
    cid = int(customer_id) if customer_id else None
    if cid:
        c = db.get(Customer, cid)
        if not c or c.business_id != user.business_id:
            raise HTTPException(400)
    j = PrintJob(business_id=user.business_id, customer_id=cid, job_no=make_ref("JOB"), title=title.strip(), job_type=job_type.strip(), quantity=max(1, quantity), size=size.strip(), material=material.strip(), colour=colour, sides=sides, finishing=finishing.strip(), design_required=bool(design_required), total_amount=max(0, total_amount), deposit=max(0, min(deposit, total_amount if total_amount else deposit)), due_date=due_date, notes=notes.strip())
    db.add(j)
    log_action(db, user, "job.create", j.title)
    db.commit()
    return RedirectResponse("/jobs", status_code=303)


@app.post("/jobs/{jid}/status")
def job_status(jid: int, request: Request, status: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    j = db.get(PrintJob, jid)
    allowed = ["New", "Design", "Awaiting Approval", "Approved", "Printing", "Finishing", "Ready", "Delivered", "Cancelled"]
    if not j or j.business_id != user.business_id or status not in allowed:
        raise HTTPException(404)
    j.status = status
    log_action(db, user, "job.status", f"{j.job_no} -> {status}")
    db.commit()
    return RedirectResponse("/jobs", status_code=303)


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    rows = db.scalars(select(Supplier).where(Supplier.business_id == user.business_id).order_by(Supplier.name)).all()
    purchases = db.scalars(select(Purchase).where(Purchase.business_id == user.business_id).order_by(Purchase.created_at.desc()).limit(10)).all()
    return templates.TemplateResponse(request, "suppliers.html", ctx(request, db, suppliers=rows, purchases=purchases))


@app.post("/suppliers")
def add_supplier(request: Request, name: str = Form(...), phone: str = Form(""), email: str = Form(""), address: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    user = require_user(request, db)
    s = Supplier(business_id=user.business_id, name=name.strip(), phone=phone.strip(), email=email.strip(), address=address.strip(), notes=notes.strip())
    db.add(s)
    log_action(db, user, "supplier.create", s.name)
    db.commit()
    return RedirectResponse("/suppliers", status_code=303)


@app.get("/purchases/new", response_class=HTMLResponse)
def new_purchase(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    suppliers = db.scalars(select(Supplier).where(Supplier.business_id == user.business_id).order_by(Supplier.name)).all()
    products = db.scalars(select(Product).where(Product.business_id == user.business_id, Product.item_type == "product", Product.active == True).order_by(Product.name)).all()
    return templates.TemplateResponse(request, "new_purchase.html", ctx(request, db, suppliers=suppliers, products=products))


@app.post("/purchases/new")
def create_purchase(request: Request, supplier_id: str = Form(""), supplier_invoice: str = Form(""), amount_paid: float = Form(0), payment_method: str = Form("Cash"), purchase_date: str = Form(...), notes: str = Form(""), items_json: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    supplier = None
    if supplier_id:
        supplier = db.get(Supplier, int(supplier_id))
        if not supplier or supplier.business_id != user.business_id:
            raise HTTPException(400)
    try:
        raw_items = json.loads(items_json)
    except Exception:
        raw_items = []
    prepared = []
    total = 0.0
    for item in raw_items:
        pid = int(item.get("product_id") or 0)
        qty = float(item.get("qty") or 0)
        cost = float(item.get("unit_cost") or 0)
        product = db.get(Product, pid)
        if not product or product.business_id != user.business_id or product.item_type != "product" or qty <= 0 or cost < 0:
            continue
        line = qty * cost
        total += line
        prepared.append((product, qty, cost, line))
    if not prepared:
        return RedirectResponse("/purchases/new?error=items", status_code=303)
    amount_paid = max(0, min(amount_paid, total))
    p = Purchase(business_id=user.business_id, supplier_id=supplier.id if supplier else None, purchase_no=make_ref("PUR"), supplier_invoice=supplier_invoice.strip(), total=total, amount_paid=amount_paid, payment_method=payment_method, purchase_date=purchase_date, notes=notes.strip())
    db.add(p)
    db.flush()
    for product, qty, cost, line in prepared:
        db.add(PurchaseItem(purchase_id=p.id, product_id=product.id, description=product.name, qty=qty, unit_cost=cost, line_total=line))
        product.stock_qty += qty
        product.cost_price = cost
        db.add(StockMovement(business_id=user.business_id, product_id=product.id, movement_type="purchase", qty=qty, reference=p.purchase_no))
    log_action(db, user, "purchase.create", p.purchase_no)
    db.commit()
    return RedirectResponse("/suppliers", status_code=303)


@app.get("/expenses", response_class=HTMLResponse)
def expenses(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    rows = db.scalars(select(Expense).where(Expense.business_id == user.business_id).order_by(Expense.expense_date.desc(), Expense.id.desc())).all()
    return templates.TemplateResponse(request, "expenses.html", ctx(request, db, expenses=rows))


@app.post("/expenses")
def add_expense(request: Request, category: str = Form(...), description: str = Form(...), amount: float = Form(...), payment_method: str = Form("Cash"), expense_date: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    if amount <= 0:
        return RedirectResponse("/expenses?error=amount", status_code=303)
    e = Expense(business_id=user.business_id, category=category.strip(), description=description.strip(), amount=amount, payment_method=payment_method, expense_date=expense_date)
    db.add(e)
    log_action(db, user, "expense.create", e.description)
    db.commit()
    return RedirectResponse("/expenses", status_code=303)


@app.get("/cashbook", response_class=HTMLResponse)
def cashbook(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    entries = []
    for p in db.scalars(select(Payment).where(Payment.business_id == user.business_id)).all():
        entries.append({"date": p.payment_date, "type": "Customer payment", "reference": p.sale.invoice_no if p.sale else p.reference, "method": p.method, "in": p.amount, "out": 0})
    for p in db.scalars(select(Purchase).where(Purchase.business_id == user.business_id, Purchase.amount_paid > 0)).all():
        entries.append({"date": p.purchase_date, "type": "Supplier purchase", "reference": p.purchase_no, "method": p.payment_method, "in": 0, "out": p.amount_paid})
    for e in db.scalars(select(Expense).where(Expense.business_id == user.business_id)).all():
        entries.append({"date": e.expense_date, "type": "Expense", "reference": e.description, "method": e.payment_method, "in": 0, "out": e.amount})
    entries.sort(key=lambda x: x["date"], reverse=True)
    total_in = sum(x["in"] for x in entries)
    total_out = sum(x["out"] for x in entries)
    return templates.TemplateResponse(request, "cashbook.html", ctx(request, db, entries=entries, total_in=total_in, total_out=total_out, balance=total_in-total_out))


@app.get("/reports", response_class=HTMLResponse)
def reports(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    bid = user.business_id
    sales_total = float(db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.business_id == bid)) or 0)
    paid = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.business_id == bid)) or 0)
    expenses_total = float(db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.business_id == bid)) or 0)
    purchase_paid = float(db.scalar(select(func.coalesce(func.sum(Purchase.amount_paid), 0)).where(Purchase.business_id == bid)) or 0)
    stock_value = float(db.scalar(select(func.coalesce(func.sum(Product.stock_qty * Product.cost_price), 0)).where(Product.business_id == bid, Product.item_type == "product")) or 0)
    cogs = float(db.scalar(select(func.coalesce(func.sum(SaleItem.qty * SaleItem.cost_price), 0)).join(Sale, SaleItem.sale_id == Sale.id).where(Sale.business_id == bid)) or 0)
    gross_profit = sales_total - cogs
    customer_balances = []
    for c in db.scalars(select(Customer).where(Customer.business_id == bid).order_by(Customer.name)).all():
        t = float(db.scalar(select(func.coalesce(func.sum(Sale.total), 0)).where(Sale.business_id == bid, Sale.customer_id == c.id)) or 0)
        p = float(db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.business_id == bid, Payment.customer_id == c.id)) or 0)
        if abs(t-p) > 0.001:
            customer_balances.append((c, t-p))
    return templates.TemplateResponse(request, "reports.html", ctx(request, db, sales_total=sales_total, paid=paid, receivables=sales_total-paid, expenses_total=expenses_total, purchase_paid=purchase_paid, stock_value=stock_value, cogs=cogs, gross_profit=gross_profit, net_cash=paid-expenses_total-purchase_paid, customer_balances=customer_balances))


@app.get("/reports/sales.csv")
def export_sales(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    rows = db.scalars(select(Sale).where(Sale.business_id == user.business_id).order_by(Sale.created_at.desc())).all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Invoice", "Date", "Customer", "Total", "Paid", "Balance", "Status", "Payment Method"])
    for s in rows:
        w.writerow([s.invoice_no, s.created_at.strftime("%Y-%m-%d"), s.customer.name if s.customer else "Walk-in", s.total, s.amount_paid, s.total-s.amount_paid, s.status, s.payment_method])
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sales-report.csv"})


@app.get("/users", response_class=HTMLResponse)
def users(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if user.role not in {"Owner", "Admin"}:
        raise HTTPException(403)
    rows = db.scalars(select(User).where(User.business_id == user.business_id).order_by(User.display_name)).all()
    logs = db.scalars(select(AuditLog).where(AuditLog.business_id == user.business_id).order_by(AuditLog.created_at.desc()).limit(25)).all()
    return templates.TemplateResponse(request, "users.html", ctx(request, db, users=rows, logs=logs, roles=["Owner", "Admin", "Manager", "Cashier", "Sales", "Designer/Production", "Storekeeper", "Accountant"]))


@app.post("/users")
def add_user(request: Request, username: str = Form(...), display_name: str = Form(...), password: str = Form(...), role: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    if user.role not in {"Owner", "Admin"}:
        raise HTTPException(403)
    if db.scalar(select(User).where(User.username == username)):
        return RedirectResponse("/users?error=username", status_code=303)
    db.add(User(business_id=user.business_id, username=username.strip(), display_name=display_name.strip(), password_hash=hash_password(password), role=role))
    log_action(db, user, "user.create", username)
    db.commit()
    return RedirectResponse("/users", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if user.role not in {"Owner", "Admin", "Manager"}:
        raise HTTPException(403)
    return templates.TemplateResponse(request, "settings.html", ctx(request, db))


@app.post("/settings")
def save_settings(request: Request, name: str = Form(...), business_type: str = Form(...), currency: str = Form("SLE"), phone: str = Form(""), email: str = Form(""), address: str = Form(""), receipt_footer: str = Form(""), theme_primary: str = Form("#c8102e"), modules: list[str] = Form([]), db: Session = Depends(get_db)):
    user = require_user(request, db)
    if user.role not in {"Owner", "Admin", "Manager"}:
        raise HTTPException(403)
    b = db.get(Business, user.business_id)
    b.name = name.strip()
    b.business_type = business_type.strip()
    b.currency = currency.strip().upper()[:12] or "SLE"
    b.phone = phone.strip()
    b.email = email.strip()
    b.address = address.strip()
    b.receipt_footer = receipt_footer.strip()
    b.theme_primary = theme_primary.strip() or "#c8102e"
    b.modules_json = json.dumps(modules or ["sales", "customers", "inventory", "reports"])
    log_action(db, user, "settings.update", "Business settings updated")
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)


@app.post("/settings/password")
def change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    if not verify_password(current_password, user.password_hash) or len(new_password) < 8:
        return RedirectResponse("/settings?password_error=1", status_code=303)
    user.password_hash = hash_password(new_password)
    log_action(db, user, "password.change", "Password changed")
    db.commit()
    return RedirectResponse("/settings?password_saved=1", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok", "app": "TechBiz Business Management System", "version": "2.0"}
