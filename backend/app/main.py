from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from app import models, schemas
from app.database import engine, get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
from app.deps import get_current_active_user, get_current_admin_user, get_current_labour_user
import uuid

# In production, use Alembic for migrations instead of create_all
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Dairy Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Dairy Management API"}

# --- Auth Endpoints ---

@app.post("/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register_business(request: schemas.BusinessRegistrationRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    if db.query(models.User).filter(models.User.phone_number == request.admin_phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")
        
    # Create Business
    new_business = models.DairyBusiness(business_name=request.business_name)
    db.add(new_business)
    db.flush()
    
    # Create Admin User
    new_user = models.User(
        business_id=new_business.id,
        role="ADMIN",
        phone_number=request.admin_phone_number,
        password_hash=get_password_hash(request.admin_password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(subject=new_user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone_number == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Farmer Endpoints ---
@app.post("/farmers/", response_model=schemas.FarmerResponse, status_code=status.HTTP_201_CREATED)
def create_farmer(farmer: schemas.FarmerCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.phone_number == farmer.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Create User
    new_user = models.User(
        business_id=current_user.business_id,
        role="FARMER",
        phone_number=farmer.phone_number,
        password_hash=get_password_hash(farmer.password)
    )
    db.add(new_user)
    db.flush() # Flush to get new_user.id
    
    # Create Farmer Profile
    new_farmer = models.FarmerProfile(
        user_id=new_user.id,
        full_name=farmer.full_name,
        bank_account=farmer.bank_account,
        ifsc_code=farmer.ifsc_code
    )
    db.add(new_farmer)
    db.commit()
    db.refresh(new_farmer)
    return new_farmer

@app.get("/farmers/{farmer_id}", response_model=schemas.FarmerResponse)
def get_farmer(farmer_id: uuid.UUID, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    farmer = db.query(models.FarmerProfile).filter(models.FarmerProfile.id == farmer_id).first()
    if not farmer or farmer.user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return farmer

# --- Phase 2: Labour Interface Endpoints ---

@app.post("/milk-collection/", response_model=schemas.MilkCollectionResponse, status_code=status.HTTP_201_CREATED)
def create_milk_collection(collection: schemas.MilkCollectionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_labour_user)):
    # 1. Verify farmer exists and belongs to same business
    farmer = db.query(models.FarmerProfile).filter(models.FarmerProfile.id == collection.farmer_id).first()
    if not farmer or farmer.user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Farmer not found")

    # 2. Auto-calculate Rate and Total Price
    rate_per_liter = (collection.fat_percentage * 6.5) + (collection.snf_percentage * 3.5)
    total_price = collection.quantity_liters * rate_per_liter

    # 3. Create collection entry
    new_collection = models.MilkCollection(
        farmer_id=collection.farmer_id,
        recorded_by_id=current_user.id,
        quantity_liters=collection.quantity_liters,
        fat_percentage=collection.fat_percentage,
        snf_percentage=collection.snf_percentage,
        water_percentage=collection.water_percentage,
        shift=collection.shift,
        rate_per_liter=round(rate_per_liter, 2),
        total_price=round(total_price, 2)
    )
    db.add(new_collection)
    db.commit()
    db.refresh(new_collection)
    return new_collection

@app.post("/inventory/", response_model=schemas.InventoryResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_item(item: schemas.InventoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    new_item = models.Inventory(**item.model_dump(), business_id=current_user.business_id)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@app.post("/feed-distribution/", response_model=schemas.FeedDistributionResponse, status_code=status.HTTP_201_CREATED)
def distribute_feed(distribution: schemas.FeedDistributionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_labour_user)):
    # 1. Check if farmer exists
    farmer = db.query(models.FarmerProfile).filter(models.FarmerProfile.id == distribution.farmer_id).first()
    if not farmer or farmer.user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Farmer not found")

    # 2. Check if inventory item exists and has enough stock
    inventory_item = db.query(models.Inventory).filter(models.Inventory.id == distribution.inventory_item_id).first()
    if not inventory_item or inventory_item.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    if inventory_item.stock_quantity_kg < distribution.quantity_kg:
        raise HTTPException(status_code=400, detail="Not enough stock available")

    # 3. Calculate cost and update stock
    total_cost = distribution.quantity_kg * inventory_item.unit_price
    inventory_item.stock_quantity_kg -= distribution.quantity_kg

    # 4. Create Feed Distribution record
    new_distribution = models.FeedDistribution(
        farmer_id=distribution.farmer_id,
        inventory_item_id=distribution.inventory_item_id,
        quantity_kg=distribution.quantity_kg,
        total_cost=round(total_cost, 2),
        status="PENDING" # Will be deducted during next payment cycle
    )

    db.add(new_distribution)
    db.commit()
    db.refresh(new_distribution)
    return new_distribution

# --- Phase 3: Farmer Dashboard Endpoints ---

# from datetime import datetime, timedelta (already imported)

@app.get("/farmers/{farmer_id}/dashboard/summary", response_model=schemas.FarmerDashboardSummary)
def get_farmer_dashboard_summary(farmer_id: uuid.UUID, days: int = 30, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    farmer = db.query(models.FarmerProfile).filter(models.FarmerProfile.id == farmer_id).first()
    if not farmer or farmer.user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Farmer not found")

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    # 1. Milk Aggregation
    milk_stats = db.query(
        func.sum(models.MilkCollection.quantity_liters).label('total_qty'),
        func.avg(models.MilkCollection.fat_percentage).label('avg_fat'),
        func.avg(models.MilkCollection.snf_percentage).label('avg_snf'),
        func.sum(models.MilkCollection.total_price).label('total_earnings')
    ).filter(
        models.MilkCollection.farmer_id == farmer_id,
        models.MilkCollection.collection_time >= period_start,
        models.MilkCollection.collection_time <= period_end
    ).first()

    total_qty = milk_stats.total_qty or 0.0
    avg_fat = milk_stats.avg_fat or 0.0
    avg_snf = milk_stats.avg_snf or 0.0
    total_earnings = milk_stats.total_earnings or 0.0

    # 2. Feed Expenses (Pending deductions)
    feed_expenses = db.query(
        func.sum(models.FeedDistribution.total_cost).label('total_feed')
    ).filter(
        models.FeedDistribution.farmer_id == farmer_id,
        models.FeedDistribution.status == "PENDING"
    ).first()

    total_feed = feed_expenses.total_feed or 0.0

    # 3. Calculate Net Payable
    net_payable = total_earnings - total_feed - farmer.current_loan_balance

    return schemas.FarmerDashboardSummary(
        total_milk_quantity=round(total_qty, 2),
        average_fat=round(avg_fat, 2),
        average_snf=round(avg_snf, 2),
        total_milk_earnings=round(total_earnings, 2),
        total_feed_expenses=round(total_feed, 2),
        current_loan_balance=round(farmer.current_loan_balance, 2),
        net_payable=round(net_payable, 2),
        period_start=period_start,
        period_end=period_end
    )

@app.get("/farmers/{farmer_id}/milk-collections", response_model=schemas.FarmerMilkCollectionList)
def get_farmer_milk_collections(farmer_id: uuid.UUID, limit: int = 50, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    farmer = db.query(models.FarmerProfile).filter(models.FarmerProfile.id == farmer_id).first()
    if not farmer or farmer.user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Farmer not found")

    collections = db.query(models.MilkCollection).filter(
        models.MilkCollection.farmer_id == farmer_id
    ).order_by(models.MilkCollection.collection_time.desc()).limit(limit).all()
    
    return schemas.FarmerMilkCollectionList(items=collections)

# --- Phase 4: Admin Dashboard & Financial Controls ---

@app.post("/loans/", response_model=schemas.LoanTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_loan_transaction(transaction: schemas.LoanTransactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    farmer = db.query(models.FarmerProfile).filter(models.FarmerProfile.id == transaction.farmer_id).first()
    if not farmer or farmer.user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Farmer not found")

    # Update farmer's current loan balance
    if transaction.transaction_type == "CREDIT":
        farmer.current_loan_balance += transaction.amount
    elif transaction.transaction_type == "DEBIT":
        farmer.current_loan_balance -= transaction.amount
    else:
        raise HTTPException(status_code=400, detail="Invalid transaction type. Must be CREDIT or DEBIT.")

    new_tx = models.LoanTransaction(**transaction.model_dump())
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    return new_tx

@app.post("/payments/process", response_model=schemas.PaymentResponse, status_code=status.HTTP_201_CREATED)
def process_payment(request: schemas.ProcessPaymentRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    farmer = db.query(models.FarmerProfile).filter(models.FarmerProfile.id == request.farmer_id).first()
    if not farmer or farmer.user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Farmer not found")

    # 1. Sum un-processed milk earnings for period
    milk_stats = db.query(
        func.sum(models.MilkCollection.total_price).label('total_earnings')
    ).filter(
        models.MilkCollection.farmer_id == request.farmer_id,
        models.MilkCollection.collection_time >= request.period_start,
        models.MilkCollection.collection_time <= request.period_end
    ).first()
    total_earnings = milk_stats.total_earnings or 0.0

    # 2. Sum and update pending feed distributions
    pending_feeds = db.query(models.FeedDistribution).filter(
        models.FeedDistribution.farmer_id == request.farmer_id,
        models.FeedDistribution.status == "PENDING",
        models.FeedDistribution.distribution_date <= request.period_end
    ).all()
    
    total_feed_deductions = sum(feed.total_cost for feed in pending_feeds)
    for feed in pending_feeds:
        feed.status = "DEDUCTED_FROM_PAYMENT"

    # 3. Deduct EMI
    if request.deduct_emi_amount > 0:
        if request.deduct_emi_amount > farmer.current_loan_balance:
            request.deduct_emi_amount = farmer.current_loan_balance
        
        # Create a loan DEBIT transaction automatically
        emi_tx = models.LoanTransaction(
            farmer_id=request.farmer_id,
            amount=request.deduct_emi_amount,
            transaction_type="DEBIT",
            description=f"EMI Deduction for period {request.period_start.date()} to {request.period_end.date()}"
        )
        db.add(emi_tx)
        farmer.current_loan_balance -= request.deduct_emi_amount

    # 4. Calculate Net
    net_payable = total_earnings - total_feed_deductions - request.deduct_emi_amount

    new_payment = models.Payment(
        farmer_id=request.farmer_id,
        total_milk_earnings=round(total_earnings, 2),
        total_feed_deductions=round(total_feed_deductions, 2),
        loan_emi_deduction=round(request.deduct_emi_amount, 2),
        net_payable=round(net_payable, 2),
        period_start=request.period_start,
        period_end=request.period_end,
        payment_status="PAID"
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return new_payment

@app.get("/admin/dashboard", response_model=schemas.AdminDashboardSummary)
def get_admin_dashboard(days: int = 30, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    # Global Milk Stats
    milk_stats = db.query(
        func.sum(models.MilkCollection.quantity_liters).label('total_qty'),
        func.sum(models.MilkCollection.total_price).label('total_rev')
    ).join(models.FarmerProfile).join(models.User).filter(
        models.User.business_id == current_user.business_id,
        models.MilkCollection.collection_time >= period_start,
        models.MilkCollection.collection_time <= period_end
    ).first()

    # Global Feed Sales
    feed_stats = db.query(
        func.sum(models.FeedDistribution.total_cost).label('total_feed')
    ).join(models.FarmerProfile).join(models.User).filter(
        models.User.business_id == current_user.business_id,
        models.FeedDistribution.distribution_date >= period_start,
        models.FeedDistribution.distribution_date <= period_end
    ).first()

    # Total Outstanding Loans across all farmers
    loan_stats = db.query(
        func.sum(models.FarmerProfile.current_loan_balance).label('total_loans')
    ).join(models.User).filter(
        models.User.business_id == current_user.business_id
    ).first()

    return schemas.AdminDashboardSummary(
        total_milk_collected_liters=round(milk_stats.total_qty or 0.0, 2),
        total_revenue_from_milk=round(milk_stats.total_rev or 0.0, 2),
        total_feed_sales=round(feed_stats.total_feed or 0.0, 2),
        total_active_loans=round(loan_stats.total_loans or 0.0, 2)
    )

# --- Phase 5: Analytics & Charts ---

@app.get("/analytics/milk-trend", response_model=schemas.MilkTrendResponse)
def get_milk_trend(days: int = 30, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    # Group by date
    daily_stats = db.query(
        cast(models.MilkCollection.collection_time, Date).label('collection_date'),
        func.sum(models.MilkCollection.quantity_liters).label('total_qty'),
        func.avg(models.MilkCollection.fat_percentage).label('avg_fat'),
        func.avg(models.MilkCollection.snf_percentage).label('avg_snf')
    ).join(models.FarmerProfile).join(models.User).filter(
        models.User.business_id == current_user.business_id,
        models.MilkCollection.collection_time >= period_start,
        models.MilkCollection.collection_time <= period_end
    ).group_by(
        cast(models.MilkCollection.collection_time, Date)
    ).order_by(
        cast(models.MilkCollection.collection_time, Date)
    ).all()

    trends = []
    for stat in daily_stats:
        trends.append(schemas.DailyMilkTrend(
            date=datetime.combine(stat.collection_date, datetime.min.time()),
            total_quantity=round(stat.total_qty or 0.0, 2),
            avg_fat=round(stat.avg_fat or 0.0, 2),
            avg_snf=round(stat.avg_snf or 0.0, 2)
        ))

    return schemas.MilkTrendResponse(trends=trends)

@app.get("/analytics/kpis", response_model=schemas.BusinessKPIs)
def get_business_kpis(days: int = 30, selling_price_per_liter: float = 55.0, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin_user)):
    """
    selling_price_per_liter: The rate at which the Dairy Owner sells the aggregated milk to the Main Dairy/Factory.
    """
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    milk_stats = db.query(
        func.sum(models.MilkCollection.quantity_liters).label('total_qty'),
        func.sum(models.MilkCollection.total_price).label('total_cost')
    ).join(models.FarmerProfile).join(models.User).filter(
        models.User.business_id == current_user.business_id,
        models.MilkCollection.collection_time >= period_start,
        models.MilkCollection.collection_time <= period_end
    ).first()

    total_qty = milk_stats.total_qty or 0.0
    total_cost = milk_stats.total_cost or 0.0  # What we paid to the farmers
    
    total_revenue = total_qty * selling_price_per_liter # What we earned
    gross_profit = total_revenue - total_cost
    
    profit_margin = 0.0
    if total_revenue > 0:
        profit_margin = (gross_profit / total_revenue) * 100

    avg_cost_per_liter = 0.0
    if total_qty > 0:
        avg_cost_per_liter = total_cost / total_qty

    return schemas.BusinessKPIs(
        total_milk_cost=round(total_cost, 2),
        total_milk_revenue=round(total_revenue, 2),
        gross_profit=round(gross_profit, 2),
        profit_margin_percentage=round(profit_margin, 2),
        average_cost_per_liter=round(avg_cost_per_liter, 2)
    )

# --- Phase 6: Automation & Background Jobs ---

def process_all_payments_task(period_start: datetime, period_end: datetime, default_emi: float, business_id: uuid.UUID):
    """
    Background task to iterate through all active farmers for a specific business and process their payments.
    In a real production system, this would be a Celery task hitting a Redis queue.
    """
    from sqlalchemy.orm import Session
    with Session(engine) as session:
            farmers = session.query(models.FarmerProfile).join(models.User).filter(models.User.business_id == business_id).all()
            for farmer in farmers:
                try:
                    # Reuse the logic we wrote in Phase 4 but inside the background context
                    # 1. Milk Earnings
                    milk_stats = session.query(func.sum(models.MilkCollection.total_price).label('total_earnings')).filter(
                        models.MilkCollection.farmer_id == farmer.id,
                        models.MilkCollection.collection_time >= period_start,
                        models.MilkCollection.collection_time <= period_end
                    ).first()
                    total_earnings = milk_stats.total_earnings or 0.0

                    if total_earnings == 0:
                        continue # Skip farmers with no milk supplied in this period

                    # 2. Feed Deductions
                    pending_feeds = session.query(models.FeedDistribution).filter(
                        models.FeedDistribution.farmer_id == farmer.id,
                        models.FeedDistribution.status == "PENDING",
                        models.FeedDistribution.distribution_date <= period_end
                    ).all()
                    total_feed_deductions = sum(feed.total_cost for feed in pending_feeds)
                    for feed in pending_feeds:
                        feed.status = "DEDUCTED_FROM_PAYMENT"

                    # 3. EMI
                    emi_to_deduct = default_emi
                    if emi_to_deduct > farmer.current_loan_balance:
                        emi_to_deduct = farmer.current_loan_balance
                    
                    if emi_to_deduct > 0:
                        emi_tx = models.LoanTransaction(
                            farmer_id=farmer.id,
                            amount=emi_to_deduct,
                            transaction_type="DEBIT",
                            description=f"Auto EMI Deduction {period_start.date()} to {period_end.date()}"
                        )
                        session.add(emi_tx)
                        farmer.current_loan_balance -= emi_to_deduct

                    # 4. Save Payment
                    net_payable = total_earnings - total_feed_deductions - emi_to_deduct
                    new_payment = models.Payment(
                        farmer_id=farmer.id,
                        total_milk_earnings=round(total_earnings, 2),
                        total_feed_deductions=round(total_feed_deductions, 2),
                        loan_emi_deduction=round(emi_to_deduct, 2),
                        net_payable=round(net_payable, 2),
                        period_start=period_start,
                        period_end=period_end,
                        payment_status="PAID"
                    )
                    session.add(new_payment)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    print(f"Failed to process payment for farmer {farmer.id}: {str(e)}")
                    # In production: Log the error, trigger an alert to Sentry, and continue to next farmer


@app.post("/admin/payments/bulk-process", response_model=schemas.BackgroundJobResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_bulk_payment_processing(request: schemas.BulkPaymentRequest, background_tasks: BackgroundTasks, current_user: models.User = Depends(get_current_admin_user)):
    job_id = uuid.uuid4()
    
    # Add task to FastAPI's background thread pool
    background_tasks.add_task(
        process_all_payments_task,
        period_start=request.period_start,
        period_end=request.period_end,
        default_emi=request.default_emi_deduction,
        business_id=current_user.business_id
    )
    
    return schemas.BackgroundJobResponse(
        message="Bulk payment processing has been started in the background. You will be notified when complete.",
        job_id=job_id
    )
