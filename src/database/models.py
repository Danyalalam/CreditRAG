from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Report(Base):
    __tablename__ = 'reports'
    id = Column(Integer, primary_key=True)
    slug = Column(String(36))  # UUID format
    credit_scores = relationship("CreditScore", back_populates="report")
    summaries = relationship("Summary", back_populates="report")
    personal_information = relationship("PersonalInformation", back_populates="report")
    account_histories = relationship("AccountHistory", back_populates="report")
    inquiries = relationship("Inquiry", back_populates="report")
    credit_contacts = relationship("CreditContact", back_populates="report")
    data_furnishers = relationship("DataFurnisher", back_populates="report")
    

class CreditScore(Base):
    __tablename__ = 'credit_scores'
    id = Column(Integer, primary_key=True)  # Using ID from JSON
    status_id = Column(Integer)
    user_id = Column(Integer)
    user_type = Column(String)
    credit_bureau_id = Column(Integer)
    credit_score = Column(String)
    lender_rank = Column(String, nullable=True)
    score_scale = Column(String, nullable=True)
    type = Column(Integer)
    report_id = Column(Integer, ForeignKey('reports.id'))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    deleted_at = Column(DateTime, nullable=True)
    old_scores = Column(String)
    score_difference = Column(String)
    credit_reporting_agency = Column(JSON)
    report = relationship("Report", back_populates="credit_scores")

class Summary(Base):
    __tablename__ = 'summaries'
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'))
    credit_bureau_id = Column(Integer)
    total_accounts = Column(String)
    open_accounts = Column(String)
    closed_accounts = Column(String)
    collection = Column(String, nullable=True)
    delinquent = Column(String)
    derogatory = Column(String)
    balances = Column(String)
    payments = Column(String)
    public_records = Column(String)
    inquiries = Column(String)
    type = Column(Integer)
    credit_reporting_agency = Column(JSON)
    report = relationship("Report", back_populates="summaries")

class PersonalInformation(Base):
    __tablename__ = 'personal_information'
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'))
    credit_bureau_id = Column(Integer)
    name = Column(JSON)
    dob = Column(JSON)
    aka_name = Column(JSON)
    former = Column(String)
    current_addresses = Column(JSON)
    previous_addresses = Column(JSON)
    employers = Column(JSON)
    type = Column(String)
    credit_reporting_agency = Column(JSON)
    report = relationship("Report", back_populates="personal_information")

class AccountHistory(Base):
    __tablename__ = 'account_histories'
    id = Column(Integer, primary_key=True)  # Using ID from JSON
    account_unique_id = Column(String, nullable=True)
    user_id = Column(Integer)
    user_type = Column(String)
    credit_bureau_id = Column(Integer)
    furnisher_name = Column(String)
    account_number = Column(String)
    account_type = Column(String)
    account_detail = Column(String)
    bureau_code = Column(String)
    account_status = Column(String)
    monthly_payment = Column(String)
    date_opened = Column(String)
    balance = Column(String)
    number_of_months = Column(String)
    high_credit = Column(String)
    credit_limit = Column(String)
    past_due = Column(String)
    payment_status = Column(String)
    late_status = Column(String)
    last_reported = Column(String)
    comments = Column(String)
    date_last_active = Column(String)
    date_last_payment = Column(String)
    payment_history = Column(JSON)
    type = Column(Integer)
    report_id = Column(Integer, ForeignKey('reports.id'))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(Integer, nullable=True)
    contacted = Column(Integer)
    account_history_id = Column(Integer, nullable=True)
    bureau_dispute_status = Column(Integer, nullable=True)
    creditor_dispute_status = Column(Integer, nullable=True)
    text = Column(String)
    class_type = Column(String)
    credit_contact = Column(JSON)
    report = relationship("Report", back_populates="account_histories")

class Inquiry(Base):
    __tablename__ = 'inquiries'
    id = Column(Integer, primary_key=True)  # Using ID from JSON
    creditor_name = Column(String)
    type_of_business = Column(String)
    date_of_inquiry = Column(String)
    credit_bureau = Column(String)
    type = Column(Integer)
    is_deleted = Column(Integer, nullable=True)
    account_history_id = Column(Integer, nullable=True)
    bureau_dispute_status = Column(Integer)
    creditor_dispute_status = Column(Integer)
    class_type = Column(String)
    account_history = Column(JSON, nullable=True)
    credit_contact = Column(JSON)
    report_id = Column(Integer, ForeignKey('reports.id'))
    report = relationship("Report", back_populates="inquiries")

class CreditContact(Base):
    __tablename__ = 'credit_contacts'
    id = Column(Integer, primary_key=True)  # Using ID from JSON
    user_id = Column(Integer)
    user_type = Column(String)
    creditor_name = Column(String)
    address = Column(String)
    address_line = Column(String)
    city = Column(String)
    state = Column(String)
    zipcode = Column(String)
    phone = Column(String)
    fax_number = Column(String, nullable=True)
    type = Column(Integer)
    report_id = Column(Integer, ForeignKey('reports.id'))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    deleted_at = Column(DateTime, nullable=True)
    contacted = Column(Integer)
    report = relationship("Report", back_populates="credit_contacts")

class DataFurnisher(Base):
    __tablename__ = 'data_furnishers'
    # Composite primary key (id, report_id)
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'), primary_key=True)
    name = Column(String)
    description = Column(String)
    address_name = Column(String)
    street_address = Column(String)
    city = Column(String)
    state = Column(String)
    state_abbrev = Column(String)
    zipcode = Column(String)
    phone_number = Column(String)
    phone_number1 = Column(String)
    phone_number2 = Column(String)
    fax_number = Column(String)
    website = Column(String)
    links = Column(String)
    email = Column(String)
    logo_url = Column(String)
    category_id = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    is_report_free = Column(Integer)
    is_report_freeze = Column(Integer)
    checkbox = Column(Integer)
    selected_address = Column(Integer)
    type = Column(Integer)
    report = relationship("Report", back_populates="data_furnishers")

    __table_args__ = (
        UniqueConstraint('id', 'report_id', name='uix_data_furnisher'),
    )