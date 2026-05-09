import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Float, DateTime, ForeignKey, Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class DairyBusiness(Base):
    """
    SaaS Tenant Model. Each dairy owner gets one DairyBusiness.
    """
    __tablename__ = "dairy_businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    business_name = Column(String(255), nullable=False)
    subscription_status = Column(String(50), default="TRIAL") # TRIAL, ACTIVE, CANCELLED, PAST_DUE
    stripe_customer_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to Users
    users = relationship("User", back_populates="business")

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    business_id = Column(UUID(as_uuid=True), ForeignKey("dairy_businesses.id"), index=True, nullable=False)
    role = Column(String(50), nullable=False) # ADMIN, LABOUR, FARMER
    phone_number = Column(String(15), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    business = relationship("DairyBusiness", back_populates="users")
    farmer_profile = relationship("FarmerProfile", back_populates="user", uselist=False)

class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    full_name = Column(String(255), nullable=False)
    bank_account = Column(String(50))
    ifsc_code = Column(String(20))
    current_loan_balance = Column(Float, default=0.0)

    # Relationships
    user = relationship("User", back_populates="farmer_profile")
    milk_collections = relationship("MilkCollection", back_populates="farmer")
    feed_distributions = relationship("FeedDistribution", back_populates="farmer")
    loan_transactions = relationship("LoanTransaction", back_populates="farmer")
    payments = relationship("Payment", back_populates="farmer")

class MilkCollection(Base):
    __tablename__ = "milk_collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    farmer_id = Column(UUID(as_uuid=True), ForeignKey("farmer_profiles.id"), index=True)
    recorded_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id")) # ID of the labour who recorded
    quantity_liters = Column(Float, nullable=False)
    fat_percentage = Column(Float, nullable=False)
    snf_percentage = Column(Float, nullable=False)
    water_percentage = Column(Float, default=0.0)
    rate_per_liter = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    collection_time = Column(DateTime, default=datetime.utcnow, index=True)
    shift = Column(String(10)) # MORNING, EVENING

    # Relationships
    farmer = relationship("FarmerProfile", back_populates="milk_collections")

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    business_id = Column(UUID(as_uuid=True), ForeignKey("dairy_businesses.id"), index=True, nullable=False)
    item_name = Column(String(255), nullable=False)
    stock_quantity_kg = Column(Float, default=0.0)
    unit_price = Column(Float, nullable=False)
    low_stock_threshold = Column(Float, default=10.0)

    # Relationships
    business = relationship("DairyBusiness")
    feed_distributions = relationship("FeedDistribution", back_populates="inventory_item")

class FeedDistribution(Base):
    __tablename__ = "feed_distributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    farmer_id = Column(UUID(as_uuid=True), ForeignKey("farmer_profiles.id"), index=True)
    inventory_item_id = Column(UUID(as_uuid=True), ForeignKey("inventory.id"))
    quantity_kg = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    distribution_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="PENDING") # PENDING, DEDUCTED_FROM_PAYMENT

    # Relationships
    farmer = relationship("FarmerProfile", back_populates="feed_distributions")
    inventory_item = relationship("Inventory", back_populates="feed_distributions")

class LoanTransaction(Base):
    __tablename__ = "loan_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    farmer_id = Column(UUID(as_uuid=True), ForeignKey("farmer_profiles.id"), index=True)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50)) # CREDIT (Given), DEBIT (Repaid)
    description = Column(String(255))
    transaction_date = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("FarmerProfile", back_populates="loan_transactions")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    farmer_id = Column(UUID(as_uuid=True), ForeignKey("farmer_profiles.id"), index=True)
    total_milk_earnings = Column(Float, nullable=False)
    total_feed_deductions = Column(Float, default=0.0)
    loan_emi_deduction = Column(Float, default=0.0)
    net_payable = Column(Float, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    payment_status = Column(String(50), default="PENDING") # PENDING, PAID
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("FarmerProfile", back_populates="payments")
