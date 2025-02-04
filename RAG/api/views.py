import json
import os
import base64
import pdfkit  
import google.generativeai as genai
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import markdown
import logging

# Initialize Logger
logger = logging.getLogger(__name__)

# Initialize Google Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

class DisputeLetterGenerator:
    TEMPLATE_DIR = settings.BASE_DIR / "api/templates/dispute_letters"

    @staticmethod
    def select_template(account_category):
        account_category = account_category.lower().replace(" ", "_")
        # Added inquiry and public record account template mapping.
        template_mapping = {
            "positive_account": "Positive_Account_Dispute_Letter.md",
            "derogatory_account": "Derogatory_Account_Dispute_Letter.md",
            "delinquent_late_account": "Late_Payment_Dispute_Letter.md",
            "inquiry_account": "Inquiry_Dispute_Letter.md",
            "public_record_account": "Public_Record_Dispute_Letter.md"
        }
        return template_mapping.get(account_category, "generic_dispute.md")
    
    @staticmethod
    def load_template(template_name):
        template_path = os.path.join(DisputeLetterGenerator.TEMPLATE_DIR, template_name)
        try:
            with open(template_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            fallback_path = os.path.join(DisputeLetterGenerator.TEMPLATE_DIR, "generic_dispute.md")
            try:
                with open(fallback_path, "r") as file:
                    return file.read()
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Template {template_name} and fallback not found in {DisputeLetterGenerator.TEMPLATE_DIR}."
                )

    @staticmethod
    def generate_letter(account_details, account_category, disputed_accounts):
        template_name = DisputeLetterGenerator.select_template(account_category)
        template_content = DisputeLetterGenerator.load_template(template_name)
        prompt = f"""
You are a financial assistant helping to generate a dispute letter.
Use the following template and fill in the placeholders with the provided common account details and disputed accounts list.

**Template:**
{template_content}

**Common Account Details:**
{json.dumps(account_details, indent=2)}

**Disputes:**
{json.dumps(disputed_accounts, indent=2)}

**Instructions:**
- Replace placeholders like [Your Name], [Creditor Name], etc., with actual values.
- Generate a table for disputed accounts if applicable.
- Keep the markdown formatting intact.
        """
        # Add dynamic instructions based on category.
        if account_category == "delinquent_late_account":
            prompt += "\nEnsure the background section clearly explains the late payment issues."
        elif account_category == "derogatory_account":
            prompt += "\nHighlight the derogatory remarks and collection details in the letter."
        elif account_category == "positive_account":
            prompt += "\nEmphasize the positive payment history and current status."
        elif account_category == "inquiry_account":
            prompt += "\nMention that the inquiry was recently performed and its potential impact."
        elif account_category == "public_record_account":
            prompt += "\nReference the public record details such as bankruptcies, liens or judgments."
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        return response.text

class UploadReportView(APIView):
    def post(self, request, format=None):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            file.seek(0)  # Reset file pointer before reading
            data = json.load(file)
        except Exception as e:
            return Response({"error": "Invalid JSON file."}, status=status.HTTP_400_BAD_REQUEST)
        
        reports_dir = settings.BASE_DIR / "api/reports"
        os.makedirs(reports_dir, exist_ok=True)
        file_path = reports_dir / "uploaded_report.json"
        with open(file_path, 'w') as f:
            json.dump(data, f)
        
        # Extract report data from the uploaded JSON
        personal_info = data.get("report", {}).get("personalInformation", [])
        if personal_info:
            personal = personal_info[0]
            your_name = personal.get("name", ["John Doe"])[0]
            your_address = personal.get("current_addresses", ["123 Main St"])[0]
            credit_bureau_name = personal.get("credit_reporting_agency", {}).get("name", "Experian")
        else:
            your_name = "John Doe"
            your_address = "123 Main St"
            credit_bureau_name = "Experian"
        
        extracted_account_details = {
            "your_name": your_name,
            "your_address": your_address,
            "city_state_zip": "",
            "credit_bureau_name": credit_bureau_name
        }
        
        # Extract disputed accounts from account histories
        account_histories = data.get("report", {}).get("accountHistories", [])
        extracted_disputed_accounts = []
        for account in account_histories:
            status_val = account.get("account_status", "").lower()
            if status_val not in ["closed", "paid"]:
                disputed_account = {
                    "creditor_name": account.get("furnisher_name", "Unknown"),
                    "account_number": account.get("account_number", ""),
                    "reason_for_dispute": account.get("reason_for_dispute", "Please review."),
                    "reported_late_payment_dates": account.get("date_last_payment", "")
                }
                extracted_disputed_accounts.append(disputed_account)
        
        # Extract inquiries and mark them as inquiry type.
        inquiries = data.get("report", {}).get("inquiries", [])
        for inquiry in inquiries:
            disputed_inquiry = {
                "creditor_name": inquiry.get("creditor_name", "Unknown"),
                "type_of_business": inquiry.get("type_of_business", ""),
                "credit_bureau": inquiry.get("credit_bureau", ""),
                "date_of_inquiry": inquiry.get("date_of_inquiry", ""),
                "account_type": "inquiry"
            }
            extracted_disputed_accounts.append(disputed_inquiry)
        
        # Extract public records from the "summary" section for Public Record Account.
        summary = data.get("summary", {})
        if summary:
            public_records = summary.get("public_records")
            if public_records is not None:
                disputed_public_record = {
                    "creditor_name": "Public Record",
                    "account_number": "",
                    "reason_for_dispute": f"Public records count: {public_records}",
                    "account_type": "public_record"
                }
                extracted_disputed_accounts.append(disputed_public_record)
        
        # Determine default category based on account histories; if none match, use inquiry if available.
        default_category = "generic_dispute"
        for account in account_histories:
            status_val = account.get("account_status", "").lower()
            if "late" in status_val or "delinquent" in status_val:
                default_category = "delinquent_late_account"
                break
            elif "derogatory" in status_val:
                default_category = "derogatory_account"
                break
        if default_category == "generic_dispute":
            if inquiries:
                default_category = "inquiry_account"
            elif summary and summary.get("public_records") is not None:
                default_category = "public_record_account"
        
        return Response({
            "message": "Report uploaded successfully.",
            "extracted_account_details": extracted_account_details,
            "extracted_disputed_accounts": extracted_disputed_accounts,
            "default_account_category": default_category
        }, status=status.HTTP_200_OK)

class CategorizeAccountsView(APIView):
    def get(self, request, format=None):
        account_status_list = request.query_params.getlist("account_status")
        payment_days_list = request.query_params.getlist("payment_days")
        creditor_remark_list = request.query_params.getlist("creditor_remark")
        if not account_status_list:
            return Response({"error": "Missing account_status parameter(s)"}, status=status.HTTP_400_BAD_REQUEST)
        classifications = []
        # Reuse classify_account from ProcessHelper.
        helper = ProcessHelper()
        for idx, account_status in enumerate(account_status_list):
            payment_days = payment_days_list[idx] if idx < len(payment_days_list) else "0"
            creditor_remark = creditor_remark_list[idx] if idx < len(creditor_remark_list) else None
            try:
                payment_days_int = int(payment_days)
            except ValueError:
                return Response({"error": f"payment_days at index {idx} must be a number"}, status=status.HTTP_400_BAD_REQUEST)
            result = helper.classify_account(account_status, payment_days_int, creditor_remark)
            classifications.append({
                "account_status": account_status,
                "payment_days": payment_days_int,
                "creditor_remark": creditor_remark,
                "category": result.get("category"),
                "reason": result.get("reason")
            })
        return Response({"classifications": classifications}, status=status.HTTP_200_OK)

class GenerateDisputeView(APIView):
    def determine_category(self, disputed_accounts):
        """
        Determine overall account category based on each disputed account's data.
        Rules:
          - If an account has "inquiry" type then category = inquiry_account.
          - If an account has "public_record" type then category = public_record_account.
          - Otherwise, if reason contains derogatory keywords then derogatory_account.
          - Otherwise, if reason contains late indicators then delinquent_late_account.
          - Otherwise, positive_account.
        """
        category_priority = {
            "public_record_account": 5,
            "inquiry_account": 4,
            "derogatory_account": 3,
            "delinquent_late_account": 2,
            "positive_account": 1
        }
        overall = "positive_account"
        for account in disputed_accounts:
            if account.get("account_type") == "inquiry":
                current = "inquiry_account"
            elif account.get("account_type") == "public_record":
                current = "public_record_account"
            else:
                reason = account.get("reason_for_dispute", "").lower()
                if any(kw in reason for kw in ["charge-off", "collection", "repossession", "foreclosure", "settled"]):
                    current = "derogatory_account"
                elif any(kw in reason for kw in ["late", "past due"]):
                    current = "delinquent_late_account"
                else:
                    current = "positive_account"
            if category_priority[current] > category_priority[overall]:
                overall = current
        return overall

    def post(self, request, format=None):
        received_data = request.data
        account_details = received_data.get("account_details")
        # account_category provided by the UI can be overridden by system categorization.
        provided_category = received_data.get("account_category")
        disputed_accounts = received_data.get("disputed_accounts")
        if not account_details or disputed_accounts is None:
            return Response({"error": "Missing required fields."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Re-categorize disputed accounts based on predefined criteria.
        computed_category = self.determine_category(disputed_accounts)
        overall_category = computed_category
        
        # Generate the dispute letter using the determined category.
        dispute_letter_markdown = DisputeLetterGenerator.generate_letter(
            account_details, overall_category, disputed_accounts
        )
        return Response({"dispute_markdown": dispute_letter_markdown}, status=status.HTTP_200_OK)

class DownloadPDFView(APIView):
    def get(self, request, format=None):
        # Inform users that PDF conversion functionality is no longer available.
        return Response(
            {"error": "PDF conversion functionality has been removed."},
            status=status.HTTP_400_BAD_REQUEST
        )

class ProcessHelper(APIView):
    def load_json(self, filename):
        json_file_path = settings.BASE_DIR / f'api/{filename}'
        try:
            with open(json_file_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            logger.error(f"Error loading JSON: {e}")
            return {}

    def find_matching_account(self, json_data, account_status):
        account_histories = json_data.get('report', {}).get('accountHistories', [])
        normalized_status = account_status.title()
        for account in account_histories:
            if account.get('account_status') == normalized_status:
                return account
        return None

    def classify_account(self, account_status, payment_status=None, creditor_remark=None):
        credit_data = self.load_json("identityiq_1.json")
        knowledge_base = self.load_json("output_data.json")
        prompt = f"""
        You are a financial expert analyzing credit reports. Categorize the given account into one of:
        - Positive Account
        - Derogatory Account
        - Delinquent/Late Account
        - Inquiry Account
        - Public Record Account

        Based on the following credit report details:
        - Account Status: {account_status}
        - Payment Status: {payment_status}
        - Creditor Remark: {creditor_remark}

        Additionally, use this **Knowledge Base** to help improve classification:
        {json.dumps(knowledge_base, indent=2)}

        **IMPORTANT:**
        - Only respond in **pure JSON format**.
        - Do **NOT** include any explanations or extra text outside the JSON.
        - Return the JSON in this **exact format**:

        ```json
        {{
            "category": "Categorized Account Type",
            "reason": "Short explanation for classification"
        }}
        ```
        """
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        try:
            json_start = response.text.find("{")
            json_end = response.text.rfind("}") + 1
            cleaned_json = response.text[json_start:json_end]
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            logger.error("LLM response could not be parsed into JSON.")
            return {"category": "Uncategorized", "reason": "LLM response could not be parsed"}