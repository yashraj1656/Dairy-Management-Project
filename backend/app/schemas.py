from pydantic import BaseModel, UUID4
from typing import Optional, List
from datetime import datetime

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[UUID4] = None
    role: Optional[str] = None

# --- Business Registration ---
class BusinessRegistrationRequest(BaseModel):
    business_name: str
    admin_phone_number: str
    admin_password: str
    admin_full_name: str

# --- User Schemas ---
class UserBase(BaseModel):
    phone_number: str
    role: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID4
    created_at: datetime

    class Config:
        from_attributes = True

# --- Farmer Schemas ---
class FarmerBase(BaseModel):
    full_name: str
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None

class FarmerCreate(FarmerBase):
    phone_number: str
    password: str

class FarmerResponse(FarmerBase):
    id: UUID4
    user_id: UUID4
    current_loan_balance: float

    class Config:
        from_attributes = True

# --- Milk Collection Schemas ---
class MilkCollectionBase(BaseModel):
    quantity_liters: float
    fat_percentage: float
    snf_percentage: float
    water_percentage: float = 0.0
    shift: str # MORNING, EVENING
    
class MilkCollectionCreate(MilkCollectionBase):
    farmer_id: UUID4
    # rate_per_liter and total_price are calculated automatically

class MilkCollectionResponse(MilkCollectionBase):
    id: UUID4
    farmer_id: UUID4
    recorded_by_id: UUID4
    rate_per_liter: float
    total_price: float
    collection_time: datetime

    class Config:
        from_attributes = True

# --- Inventory Schemas ---
class InventoryBase(BaseModel):
    item_name: str
    stock_quantity_kg: float
    unit_price: float
    low_stock_threshold: float = 10.0

class InventoryCreate(InventoryBase):
    pass

class InventoryResponse(InventoryBase):
    id: UUID4

    class Config:
        from_attributes = True

# --- Feed Distribution Schemas ---
class FeedDistributionBase(BaseModel):
    quantity_kg: float

class FeedDistributionCreate(FeedDistributionBase):
    farmer_id: UUID4
    inventory_item_id: UUID4

class FeedDistributionResponse(FeedDistributionBase):
    id: UUID4
    farmer_id: UUID4
    inventory_item_id: UUID4
    total_cost: float
    distribution_date: datetime
    status: str

    class Config:
        from_attributes = True

# --- Phase 3: Farmer Dashboard Schemas ---
class FarmerDashboardSummary(BaseModel):
    total_milk_quantity: float
    average_fat: float
    average_snf: float
    total_milk_earnings: float
    total_feed_expenses: float
    current_loan_balance: float
    net_payable: float
    period_start: datetime
    period_end: datetime

class FarmerMilkCollectionList(BaseModel):
    items: List[MilkCollectionResponse]

# --- Phase 4: Admin & Financial Schemas ---

class LoanTransactionCreate(BaseModel):
    farmer_id: UUID4
    amount: float
    transaction_type: str # CREDIT, DEBIT
    description: Optional[str] = None

class LoanTransactionResponse(LoanTransactionCreate):
    id: UUID4
    transaction_date: datetime

    class Config:
        from_attributes = True

class ProcessPaymentRequest(BaseModel):
    farmer_id: UUID4
    period_start: datetime
    period_end: datetime
    deduct_emi_amount: float = 0.0

class PaymentResponse(BaseModel):
    id: UUID4
    farmer_id: UUID4
    total_milk_earnings: float
    total_feed_deductions: float
    loan_emi_deduction: float
    net_payable: float
    period_start: datetime
    period_end: datetime
    payment_status: str

    class Config:
        from_attributes = True

class AdminDashboardSummary(BaseModel):
    total_milk_collected_liters: float
    total_revenue_from_milk: float
    total_feed_sales: float
    total_active_loans: float

# --- Phase 5: Analytics & Charts ---

class DailyMilkTrend(BaseModel):
    date: datetime
    total_quantity: float
    avg_fat: float
    avg_snf: float

    class Config:
        from_attributes = True

class MilkTrendResponse(BaseModel):
    trends: List[DailyMilkTrend]

class BusinessKPIs(BaseModel):
    total_milk_cost: float # What we paid to farmers
    total_milk_revenue: float # What we earned selling to Main Dairy
    gross_profit: float
    profit_margin_percentage: float
    average_cost_per_liter: float

# --- Phase 6: Automation & Background Jobs ---

class BulkPaymentRequest(BaseModel):
    period_start: datetime
    period_end: datetime
    default_emi_deduction: float = 0.0

class BackgroundJobResponse(BaseModel):
    message: str
    job_id: UUID4
