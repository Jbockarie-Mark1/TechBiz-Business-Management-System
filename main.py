import csv
import hashlib
import io
import json
import os
import re
import secrets
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from datetime import date, datetime
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, inspect, select, text
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
    theme_sidebar: Mapped[str] = mapped_column(String(20), default="#111827")
    theme_background: Mapped[str] = mapped_column(String(20), default="#f5f7fb")
    logo_path: Mapped[str] = mapped_column(String(255), default="")
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


def ensure_business_branding_columns() -> None:
    """Small compatibility migration for databases created by TechBiz v2.1 or earlier."""
    existing = {c["name"] for c in inspect(engine).get_columns("businesses")}
    additions = {
        "theme_sidebar": "VARCHAR(20) DEFAULT '#111827'",
        "theme_background": "VARCHAR(20) DEFAULT '#f5f7fb'",
        "logo_path": "VARCHAR(255) DEFAULT ''",
    }
    with engine.begin() as conn:
        for column, definition in additions.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE businesses ADD COLUMN {column} {definition}"))


ensure_business_branding_columns()


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

app = FastAPI(title="TechBiz Business Management System", version="2.3")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "local-dev-secret-change-before-hosting"), same_site="lax")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def money(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


templates.env.filters["money"] = money


COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ALLOWED_LOGO_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_LOGO_BYTES = 2 * 1024 * 1024
LOGO_MAX_DIMENSION = 512
LOGO_MAX_PIXELS = 24_000_000
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def safe_color(value: str, fallback: str) -> str:
    value = (value or "").strip()
    return value if COLOR_RE.fullmatch(value) else fallback


def normalize_logo(data: bytes, content_type: str) -> bytes:
    """Validate and resize a business logo to a safe, system-friendly PNG.

    The longest side is capped at LOGO_MAX_DIMENSION while preserving the
    original aspect ratio. Transparency is preserved where available.
    """
    if content_type not in ALLOWED_LOGO_TYPES:
        raise ValueError("Unsupported logo type")
    try:
        with Image.open(BytesIO(data)) as probe:
            probe.verify()
        with Image.open(BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            if width < 1 or height < 1 or width * height > LOGO_MAX_PIXELS:
                raise ValueError("Invalid logo dimensions")
            if getattr(image, "is_animated", False):
                image.seek(0)
            image = image.convert("RGBA")
            image.thumbnail((LOGO_MAX_DIMENSION, LOGO_MAX_DIMENSION), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid logo image") from exc


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
    business = db.scalar(select(Business).limit(1))
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None, "business": business, "user": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username, User.active == True))
    if not user or not verify_password(password, user.password_hash):
        business = db.scalar(select(Business).limit(1))
        return templates.TemplateResponse(request, "login.html", {"request": request, "error": "Invalid username or password.", "business": business, "user": None})
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
def save_settings(
    request: Request,
    name: str = Form(...),
    business_type: str = Form(...),
    currency: str = Form("SLE"),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    receipt_footer: str = Form(""),
    theme_primary: str = Form("#c8102e"),
    theme_sidebar: str = Form("#111827"),
    theme_background: str = Form("#f5f7fb"),
    remove_logo: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    modules: list[str] = Form([]),
    db: Session = Depends(get_db),
):
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
    b.theme_primary = safe_color(theme_primary, "#c8102e")
    b.theme_sidebar = safe_color(theme_sidebar, "#111827")
    b.theme_background = safe_color(theme_background, "#f5f7fb")
    b.modules_json = json.dumps(modules or ["sales", "customers", "inventory", "reports"])

    new_logo_data = None
    if logo and logo.filename:
        content_type = (logo.content_type or "").lower()
        raw_logo_data = logo.file.read(MAX_LOGO_BYTES + 1)
        if len(raw_logo_data) > MAX_LOGO_BYTES:
            return RedirectResponse("/settings?logo_error=1", status_code=303)
        try:
            new_logo_data = normalize_logo(raw_logo_data, content_type)
        except ValueError:
            return RedirectResponse("/settings?logo_error=1", status_code=303)

    if (remove_logo or new_logo_data is not None) and b.logo_path:
        old_name = os.path.basename(b.logo_path)
        old_file = os.path.join(UPLOAD_DIR, old_name)
        if os.path.isfile(old_file):
            os.remove(old_file)
        b.logo_path = ""

    if new_logo_data is not None:
        filename = f"business_{b.id}_{secrets.token_hex(6)}.png"
        with open(os.path.join(UPLOAD_DIR, filename), "wb") as output:
            output.write(new_logo_data)
        b.logo_path = f"/static/uploads/{filename}"

    log_action(db, user, "settings.update", "Business profile, logo and theme updated")
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
    return {"status": "ok", "app": "TechBiz Business Management System", "version": "2.3"}

# TEMPORARY DEPLOYMENT E2E SELF-TEST — removed immediately after verification.
def _deployment_e2e_selftest():
    from fastapi.testclient import TestClient
    from sqlalchemy import delete as sa_delete
    import traceback

    marker = f"__E2E_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3)}"
    username = marker.lower()
    password = "E2E-Test-Only-2026!"
    checks = []
    ids = {}

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
        if not ok:
            raise AssertionError(f"{name}: {detail}")

    db = SessionLocal()
    try:
        business = db.scalar(select(Business).limit(1))
        check("business_exists", business is not None)
        test_user = User(
            business_id=business.id,
            username=username,
            display_name="Deployment E2E Test",
            password_hash=hash_password(password),
            role="Owner",
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        ids["user"] = test_user.id
        bid = business.id

        with TestClient(app) as client:
            r = client.get("/login")
            check("login_page", r.status_code == 200, r.status_code)
            r = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
            check("login_auth", r.status_code == 303 and r.headers.get("location") == "/", f"{r.status_code} {r.headers.get('location')}")
            r = client.get("/")
            check("dashboard", r.status_code == 200, r.status_code)

            r = client.post("/customers", data={
                "name": f"{marker} Customer", "phone": "000", "email": "e2e@example.invalid",
                "company": marker, "address": "E2E", "notes": marker
            }, follow_redirects=False)
            check("customer_create_route", r.status_code == 303, r.status_code)
            db.expire_all()
            customer = db.scalar(select(Customer).where(Customer.business_id == bid, Customer.company == marker))
            check("customer_persisted", customer is not None)
            ids["customer"] = customer.id

            r = client.post("/inventory", data={
                "name": f"{marker} Product", "sku": marker[-18:], "category": "E2E", "item_type": "product",
                "unit": "unit", "cost_price": "5", "sale_price": "10", "stock_qty": "10", "min_stock": "2"
            }, follow_redirects=False)
            check("product_create_route", r.status_code == 303, r.status_code)
            db.expire_all()
            product = db.scalar(select(Product).where(Product.business_id == bid, Product.name == f"{marker} Product"))
            check("product_opening_stock", product is not None and abs(product.stock_qty - 10) < 0.001, getattr(product, "stock_qty", None))
            ids["product"] = product.id

            items = json.dumps([{"product_id": product.id, "description": product.name, "qty": 2, "unit_price": 10}])
            r = client.post("/sales/new", data={
                "customer_id": str(customer.id), "payment_method": "Cash", "amount_paid": "8",
                "notes": marker, "items_json": items
            }, follow_redirects=False)
            check("sale_create_route", r.status_code == 303 and str(r.headers.get("location", "")).startswith("/sales/"), f"{r.status_code} {r.headers.get('location')}")
            sale_id = int(r.headers["location"].rsplit("/", 1)[1])
            ids["sale"] = sale_id
            db.expire_all()
            sale = db.get(Sale, sale_id)
            product = db.get(Product, product.id)
            check("sale_part_paid", sale is not None and sale.status == "Part Paid" and abs(sale.amount_paid - 8) < 0.001, f"{getattr(sale,'status',None)} {getattr(sale,'amount_paid',None)}")
            check("sale_stock_deducted", abs(product.stock_qty - 8) < 0.001, product.stock_qty)
            r = client.get(f"/sales/{sale_id}")
            check("receipt_page", r.status_code == 200, r.status_code)

            r = client.post(f"/sales/{sale_id}/payment", data={
                "amount": "12", "method": "Bank Transfer", "reference": marker, "payment_date": date.today().isoformat()
            }, follow_redirects=False)
            check("final_payment_route", r.status_code == 303, r.status_code)
            db.expire_all()
            sale = db.get(Sale, sale_id)
            check("sale_paid", sale.status == "Paid" and abs(sale.amount_paid - 20) < 0.001, f"{sale.status} {sale.amount_paid}")

            r = client.post("/suppliers", data={
                "name": f"{marker} Supplier", "phone": "000", "email": "supplier@example.invalid", "address": "E2E", "notes": marker
            }, follow_redirects=False)
            check("supplier_create_route", r.status_code == 303, r.status_code)
            db.expire_all()
            supplier = db.scalar(select(Supplier).where(Supplier.business_id == bid, Supplier.name == f"{marker} Supplier"))
            check("supplier_persisted", supplier is not None)
            ids["supplier"] = supplier.id

            purchase_items = json.dumps([{"product_id": product.id, "qty": 3, "unit_cost": 6}])
            r = client.post("/purchases/new", data={
                "supplier_id": str(supplier.id), "supplier_invoice": marker, "amount_paid": "18", "payment_method": "Cash",
                "purchase_date": date.today().isoformat(), "notes": marker, "items_json": purchase_items
            }, follow_redirects=False)
            check("purchase_create_route", r.status_code == 303, r.status_code)
            db.expire_all()
            purchase = db.scalar(select(Purchase).where(Purchase.business_id == bid, Purchase.supplier_invoice == marker))
            check("purchase_persisted", purchase is not None)
            ids["purchase"] = purchase.id
            product = db.get(Product, product.id)
            check("purchase_stock_increase", abs(product.stock_qty - 11) < 0.001, product.stock_qty)
            check("purchase_cost_update", abs(product.cost_price - 6) < 0.001, product.cost_price)

            r = client.post("/jobs", data={
                "customer_id": str(customer.id), "title": f"{marker} Print Job", "job_type": "Printing", "quantity": "50",
                "size": "A4", "material": "Paper", "colour": "Full Colour", "sides": "Single-sided", "finishing": "Trim",
                "design_required": "on", "total_amount": "50", "deposit": "10", "due_date": date.today().isoformat(), "notes": marker
            }, follow_redirects=False)
            check("job_create_route", r.status_code == 303, r.status_code)
            db.expire_all()
            job = db.scalar(select(PrintJob).where(PrintJob.business_id == bid, PrintJob.title == f"{marker} Print Job"))
            check("job_persisted", job is not None and job.status == "New", getattr(job, "status", None))
            ids["job"] = job.id
            r = client.post(f"/jobs/{job.id}/status", data={"status": "Ready"}, follow_redirects=False)
            check("job_status_route", r.status_code == 303, r.status_code)
            db.expire_all()
            job = db.get(PrintJob, job.id)
            check("job_status_ready", job.status == "Ready", job.status)

            r = client.post("/expenses", data={
                "category": "E2E", "description": f"{marker} Expense", "amount": "7.5", "payment_method": "Cash",
                "expense_date": date.today().isoformat()
            }, follow_redirects=False)
            check("expense_create_route", r.status_code == 303, r.status_code)
            db.expire_all()
            expense = db.scalar(select(Expense).where(Expense.business_id == bid, Expense.description == f"{marker} Expense"))
            check("expense_persisted", expense is not None and abs(expense.amount - 7.5) < 0.001)
            ids["expense"] = expense.id

            for path, label in [("/customers", "customers_page"), ("/inventory", "inventory_page"), ("/sales", "sales_page"),
                                ("/suppliers", "suppliers_page"), ("/jobs", "jobs_page"), ("/expenses", "expenses_page"),
                                ("/cashbook", "cashbook_page"), ("/reports", "reports_page"), ("/users", "users_page")]:
                r = client.get(path)
                check(label, r.status_code == 200, r.status_code)

            r = client.get("/reports/sales.csv")
            check("sales_csv", r.status_code == 200 and "text/csv" in r.headers.get("content-type", ""), f"{r.status_code} {r.headers.get('content-type')}")
            r = client.get("/settings")
            settings_html = r.text
            check("settings_page", r.status_code == 200, r.status_code)
            check("branding_controls", all(x in settings_html for x in ['name="logo"', 'name="theme_primary"', 'name="theme_sidebar"', 'name="theme_background"']), "branding fields")
            check("jits_footer", "Power by Jits" in settings_html and "Smart Technology. Reliable Solutions" in settings_html)
            r = client.get("/health")
            check("health_v23", r.status_code == 200 and r.json().get("version") == "2.3", r.text[:100])
            r = client.get("/logout", follow_redirects=False)
            check("logout", r.status_code == 303 and r.headers.get("location") == "/login", f"{r.status_code} {r.headers.get('location')}")
            r = client.get("/", follow_redirects=False)
            check("auth_required_after_logout", r.status_code == 303 and r.headers.get("location") == "/login", f"{r.status_code} {r.headers.get('location')}")

        db.expire_all()
        check("neon_persistence_sale", db.get(Sale, ids["sale"]) is not None)
        check("neon_persistence_product", db.get(Product, ids["product"]) is not None)
        print("TECHBIZ_E2E_RESULT " + json.dumps({"ok": True, "checks": len(checks), "marker": marker}))

    except Exception as exc:
        print("TECHBIZ_E2E_RESULT " + json.dumps({"ok": False, "checks": checks, "marker": marker, "error": repr(exc)}))
        traceback.print_exc()
    finally:
        try:
            db.rollback()
            if ids.get("product"):
                db.execute(sa_delete(StockMovement).where(StockMovement.product_id == ids["product"]))
            if ids.get("sale"):
                db.execute(sa_delete(Payment).where(Payment.sale_id == ids["sale"]))
                db.execute(sa_delete(SaleItem).where(SaleItem.sale_id == ids["sale"]))
                db.execute(sa_delete(Sale).where(Sale.id == ids["sale"]))
            if ids.get("purchase"):
                db.execute(sa_delete(PurchaseItem).where(PurchaseItem.purchase_id == ids["purchase"]))
                db.execute(sa_delete(Purchase).where(Purchase.id == ids["purchase"]))
            if ids.get("job"):
                db.execute(sa_delete(PrintJob).where(PrintJob.id == ids["job"]))
            if ids.get("expense"):
                db.execute(sa_delete(Expense).where(Expense.id == ids["expense"]))
            if ids.get("supplier"):
                db.execute(sa_delete(Supplier).where(Supplier.id == ids["supplier"]))
            if ids.get("product"):
                db.execute(sa_delete(Product).where(Product.id == ids["product"]))
            if ids.get("customer"):
                db.execute(sa_delete(Customer).where(Customer.id == ids["customer"]))
            if ids.get("user"):
                db.execute(sa_delete(AuditLog).where(AuditLog.user_id == ids["user"]))
                db.execute(sa_delete(User).where(User.id == ids["user"]))
            db.commit()
            print("TECHBIZ_E2E_CLEANUP " + json.dumps({"ok": True, "marker": marker}))
        except Exception as cleanup_exc:
            db.rollback()
            print("TECHBIZ_E2E_CLEANUP " + json.dumps({"ok": False, "marker": marker, "error": repr(cleanup_exc)}))
        finally:
            db.close()


if os.getenv("TECHBIZ_TEMP_DEPLOY_E2E") == "1":
    _deployment_e2e_selftest()
