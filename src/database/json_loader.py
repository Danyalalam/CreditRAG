from models import Report, CreditScore, Summary, PersonalInformation, AccountHistory, Inquiry, CreditContact, DataFurnisher
from datetime import datetime
import json

class JsonLoader:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def load_json(self, file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        session = self.db_manager.get_session()
        try:
            # Create Report
            report = Report(
                slug=data['report']['slug']
            )
            session.add(report)
            session.flush()

            # Load Credit Scores
            for score in data['report']['creditScores']:
                credit_score = CreditScore(
                    id=score['id'],
                    status_id=score['status_id'],
                    user_id=score['user_id'],
                    user_type=score['user_type'],
                    credit_bureau_id=score['credit_bureau_id'],
                    credit_score=score['credit_score'],
                    lender_rank=score['lender_rank'],
                    score_scale=score['score_scale'],
                    type=score['type'],
                    report_id=score['report_id'],
                    created_at=datetime.fromisoformat(score['created_at']),
                    updated_at=datetime.fromisoformat(score['updated_at']),
                    deleted_at=datetime.fromisoformat(score['deleted_at']) if score['deleted_at'] else None,
                    old_scores=score['old_scores'],
                    score_difference=score['score_difference'],
                    credit_reporting_agency=score['credit_reporting_agency']
                )
                session.add(credit_score)

            # Load Summary

            for summary in data['report']['summary']:
                sum_entry = Summary(
                    report_id=report.id,
                    credit_bureau_id=summary['credit_bureau_id'],
                    total_accounts=summary['total_accounts'],
                    open_accounts=summary['open_accounts'],
                    closed_accounts=summary['closed_accounts'],
                    collection=summary['collection'],
                    delinquent=summary['delinquent'],
                    derogatory=summary['derogatory'],
                    balances=summary['balances'],
                    payments=summary['payments'],
                    public_records=summary['public_records'],
                    inquiries=summary['inquiries'],
                    type=summary['type'],
                    credit_reporting_agency=summary['credit_reporting_agency']
                )
                session.add(sum_entry)

            # Load Personal Information
            for info in data['report']['personalInformation']:
                personal_info = PersonalInformation(
                    report_id=report.id,
                    credit_bureau_id=info['credit_bureau_id'],
                    name=info['name'],
                    dob=info['dob'],
                    aka_name=info['aka_name'],
                    former=info['former'],
                    current_addresses=info['current_addresses'],
                    previous_addresses=info['previous_addresses'],
                    employers=info['employers'],
                    type=info['type'],
                    credit_reporting_agency=info['credit_reporting_agency']
                )
                session.add(personal_info)

            # Load Account Histories
            for account in data['report']['accountHistories']:
                account_history = AccountHistory(
                    id=account['id'],
                    account_unique_id=account.get('account_unique_id'),
                    user_id=account['user_id'],
                    user_type=account['user_type'],
                    credit_bureau_id=account['credit_bureau_id'],
                    furnisher_name=account['furnisher_name'],
                    account_number=account['account_number'],
                    account_type=account['account_type'],
                    account_detail=account['account_detail'],
                    bureau_code=account['bureau_code'],
                    account_status=account['account_status'],
                    monthly_payment=account['monthly_payment'],
                    date_opened=account['date_opened'],
                    balance=account['balance'],
                    number_of_months=account['number_of_months'],
                    high_credit=account['high_credit'],
                    credit_limit=account['credit_limit'],
                    past_due=account['past_due'],
                    payment_status=account['payment_status'],
                    late_status=account['late_status'],
                    last_reported=account['last_reported'],
                    comments=account['comments'],
                    date_last_active=account['date_last_active'],
                    date_last_payment=account['date_last_payment'],
                    payment_history=account['payment_history'],
                    type=account['type'],
                    report_id=report.id,
                    created_at=datetime.fromisoformat(account['created_at']),
                    updated_at=datetime.fromisoformat(account['updated_at']),
                    deleted_at=datetime.fromisoformat(account['deleted_at']) if account['deleted_at'] else None,
                    is_deleted=account['is_deleted'],
                    contacted=account['contacted'],
                    account_history_id=account['account_history_id'],
                    bureau_dispute_status=account['bureau_dispute_status'],
                    creditor_dispute_status=account['creditor_dispute_status'],
                    text=account['text'],
                    class_type=account['class_type'],
                    credit_contact=account['credit_contact']
                )
                session.add(account_history)

            # Load Inquiries
            for inquiry in data['report']['inquiries']:
                inq = Inquiry(
                    id=inquiry['id'],
                    creditor_name=inquiry['creditor_name'],
                    type_of_business=inquiry['type_of_business'],
                    date_of_inquiry=inquiry['date_of_inquiry'],
                    credit_bureau=inquiry['credit_bureau'],
                    type=inquiry['type'],
                    is_deleted=inquiry['is_deleted'],
                    account_history_id=inquiry['account_history_id'],
                    bureau_dispute_status=inquiry['bureau_dispute_status'],
                    creditor_dispute_status=inquiry['creditor_dispute_status'],
                    class_type=inquiry['class_type'],
                    account_history=inquiry['account_history'],
                    credit_contact=inquiry['credit_contact'],
                    report_id=report.id
                )
                session.add(inq)

            # Load Credit Contacts
            for contact in data['report']['creditContacts']:
                credit_contact = CreditContact(
                    id=contact['id'],
                    user_id=contact['user_id'],
                    user_type=contact['user_type'],
                    creditor_name=contact['creditor_name'],
                    address=contact['address'],
                    address_line=contact['address_line'],
                    city=contact['city'],
                    state=contact['state'],
                    zipcode=contact['zipcode'],
                    phone=contact['phone'],
                    fax_number=contact['fax_number'],
                    type=contact['type'],
                    report_id=contact['report_id'],
                    created_at=datetime.fromisoformat(contact['created_at']),
                    updated_at=datetime.fromisoformat(contact['updated_at']),
                    deleted_at=datetime.fromisoformat(contact['deleted_at']) if contact['deleted_at'] else None,
                    contacted=contact['contacted']
                )
                session.add(credit_contact)

            # Load Data Furnishers
            for furnisher in data['report']['dataFurnishers']:
                data_furnisher = DataFurnisher(
                    id=furnisher['id'],
                    name=furnisher['name'],
                    description=furnisher['description'],
                    address_name=furnisher['address_name'],
                    street_address=furnisher['street_address'],
                    city=furnisher['city'],
                    state=furnisher['state'],
                    state_abbrev=furnisher['state_abbrev'],
                    zipcode=furnisher['zipcode'],
                    phone_number=furnisher['phone_number'],
                    phone_number1=furnisher['phone_number1'],
                    phone_number2=furnisher['phone_number2'],
                    fax_number=furnisher['fax_number'],
                    website=furnisher['website'],
                    links=furnisher['links'],
                    email=furnisher['email'],
                    logo_url=furnisher['logo_url'],
                    category_id=furnisher['category_id'],
                    created_at=datetime.fromisoformat(furnisher['created_at']),
                    updated_at=datetime.fromisoformat(furnisher['updated_at']),
                    is_report_free=furnisher['is_report_free'],
                    is_report_freeze=furnisher['is_report_freeze'],
                    checkbox=furnisher['checkbox'],
                    selected_address=furnisher['selected_address'],
                    type=furnisher['type'],
                    report_id=report.id
                )
                session.add(data_furnisher)

            session.commit()
            print(f"Successfully loaded data from {file_path}")
            
        except Exception as e:
            session.rollback()
            print(f"Error loading file: {str(e)}")
        finally:
            session.close()