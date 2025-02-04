import json
import os
import base64
import pdfkit  
import google.generativeai as genai
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Process
from .serializers import ProcessSerializer
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
        """Select the appropriate template based on account category."""
        account_category = account_category.lower().replace(" ", "_").replace("/", "_")
        template_mapping = {
            "derogatory_account": "Derogatory_Account_Dispute_Letter.md",
            "delinquent_late_account": "Late_Payment_Dispute_Letter.md",
            "bankruptcy_account": "Bankruptcy_Dispute_Letter.md",
            "personal_information_account": "Personal_Information_Dispute_Letter.md",
            "security_freeze_request": "Security_Freeze_Request_Letter.md",
            "opt_out_request": "Opt-Out_Request_Template.md",
            "consumer_disclosure_request": "Consumer_Disclosure_Report_Request.md",
        }
        return template_mapping.get(account_category, "generic_dispute.md")

    @staticmethod
    def load_template(template_name):
        """Load the template content from the file."""
        template_path = os.path.join(DisputeLetterGenerator.TEMPLATE_DIR, template_name)
        logger.info(f"Loading template from: {template_path}")
        try:
            with open(template_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            logger.error(f"Template not found: {template_name}")
            fallback_path = os.path.join(DisputeLetterGenerator.TEMPLATE_DIR, "generic_dispute.md")
            logger.info(f"Loading fallback template from: {fallback_path}")
            try:
                with open(fallback_path, "r") as file:
                    return file.read()
            except FileNotFoundError:
                logger.critical("Fallback template not found.")
                raise FileNotFoundError(
                    f"Neither the requested template ({template_name}) nor the fallback template (generic_dispute.md) was found in {DisputeLetterGenerator.TEMPLATE_DIR}."
                )

    @staticmethod
    def generate_letter(account_details, account_category, disputed_accounts):
        """
        Generate a dispute letter for one or more accounts.
        The template will include the common account details along with a table for disputed accounts.
        For late payment dispute letters, dynamically customize the 'Background' section.
        """
        template_name = DisputeLetterGenerator.select_template(account_category)
        template_content = DisputeLetterGenerator.load_template(template_name)

        # Build the basic prompt using the template and provided data.
        prompt = f"""
        You are a financial assistant helping to generate a dispute letter.
        Use the following template and fill in the placeholders with the provided common account details and disputed accounts list.

        **Template:**
        {template_content}

        **Common Account Details:**
        {json.dumps(account_details, indent=2)}

        **Disputed Accounts List:**
        {json.dumps(disputed_accounts, indent=2)}

        **Instructions:**
        - Replace placeholders like [Your Name], [Creditor Name], etc., with the actual values.
        - For the disputed accounts, generate a table with a row for each disputed account.
        - Replace [Date] with today's date in the format "Month Day, Year".
        - Replace [Reason for Dispute] with the explanation provided for each disputed account.
        - Keep the markdown formatting intact.
        - Do not add any extra text or explanations.
        """

        # For late payment dispute letters, instruct the model to dynamically modify
        # the 'Background' section of the template.
        if account_category.lower().replace(" ", "_") == "delinquent_late_account":
            dynamic_instructions = """
            
Additionally, dynamically update the 'Background' section of the letter.
Replace the standard text:

    The late payment(s) reported for the account(s) listed above are inaccurate for the following reasons:  

    - [Reason 1: Example: Payment was made on time, as shown by the attached bank statements.]  
    - [Reason 2: Example: This account was paid in full before the due date.]

with personalized and detailed reasons based on the account data provided.
            """
            prompt += dynamic_instructions

        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        return response.text

class ProcessView(APIView):
    def load_json(self, filename):
        """Load the specified JSON file."""
        json_file_path = settings.BASE_DIR / f'api/{filename}'
        try:
            with open(json_file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            logger.error(f"JSON file not found: {filename}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"JSON file is malformed: {filename}")
            return {}

    def find_matching_account(self, json_data, account_status):
        """Find account with matching status in accountHistories."""
        account_histories = json_data.get('report', {}).get('accountHistories', [])
        normalized_status = account_status.title()
        for account in account_histories:
            if account.get('account_status') == normalized_status:
                return account
        return None

    def classify_account(self, account_status, payment_status=None, creditor_remark=None):
        """
        Uses Google Gemini API to classify an account using both Credit Data and Knowledge Base.
        """
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

    def evaluate_dispute_letter_needed(self, account_status, payment_status=None, creditor_remark=None):
        """
        Determines if a dispute letter is needed based on the provided criteria.
        """
        account_status = account_status.lower()
        if account_status in ['closed', 'paid']:
            return False
        if account_status == 'open':
            if payment_status is not None and payment_status <= 30:
                return False
            return True
        if account_status == 'derogatory':
            if creditor_remark and creditor_remark.lower() == 'valid':
                return False
            return True
        return False

    def convert_markdown_to_pdf(self, markdown_content):
        """Convert Markdown content to PDF with precise formatting."""
        html_content = markdown.markdown(markdown_content, extensions=['tables'])
        css = """
        <style>
            @page {
                margin: 1in;
                size: Letter;
            }
            body {
                font-family: 'Times New Roman', serif;
                font-size: 12pt;
                line-height: 1.5;
                margin: 0;
                color: #000000;
            }
            h1 {
                font-size: 14pt;
                font-weight: bold;
                margin: 18pt 0 6pt 0;
                text-align: center;
            }
            h2 {
                font-size: 12pt;
                font-weight: bold;
                margin: 12pt 0 6pt 0;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 12pt 0;
                page-break-inside: avoid;
            }
            th, td {
                border: 1pt solid #000000;
                padding: 6pt;
                vertical-align: top;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            .header-info {
                margin-bottom: 24pt;
            }
            .signature-block {
                margin-top: 36pt;
            }
            .footer {
                font-size: 10pt;
                color: #666666;
                margin-top: 24pt;
                border-top: 1pt solid #000000;
                padding-top: 6pt;
            }
            ul {
                padding-left: 24pt;
            }
            .legal-reference {
                font-style: italic;
                margin: 6pt 0;
            }
        </style>
        """
        html_template = f"""
        <html>
            <head>
                <meta charset="utf-8">
                {css}
            </head>
            <body>
                {html_content}
                <div class="footer">
                    Generated by CreditRAG Dispute System | Confidential Document
                </div>
            </body>
        </html>
        """
        try:
            options = {
                'encoding': 'UTF-8',
                'quiet': '',
                'print-media-type': '',
                'margin-top': '0.5in',
                'margin-right': '0.5in',
                'margin-bottom': '0.5in',
                'margin-left': '0.5in'
            }
            pdf_config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
            pdf = pdfkit.from_string(
                html_template,
                False,
                configuration=pdf_config,
                options=options
            )
            return base64.b64encode(pdf).decode('utf-8')
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
            return None

    def get(self, request, format=None):
        """
        Handle GET requests to classify accounts and generate a dispute letter PDF for multiple accounts.
        Expect multiple query parameters using the same key:
         - account_status
         - payment_days
         - creditor_remark
        """
        account_status_list = request.query_params.getlist("account_status")
        payment_days_list = request.query_params.getlist("payment_days")
        creditor_remark_list = request.query_params.getlist("creditor_remark")

        if not account_status_list:
            return Response(
                {"error": "Missing account_status parameter(s)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        disputed_accounts = []
        overall_account_category = "Uncategorized"
        overall_reason = []

        credit_data = self.load_json("identityiq_1.json")

        # Process each account provided in the query parameters
        # In the for loop processing each account, update the disputed_accounts entry as follows:
        for idx, account_status in enumerate(account_status_list):
            payment_days = payment_days_list[idx] if idx < len(payment_days_list) else "0"
            creditor_remark = creditor_remark_list[idx] if idx < len(creditor_remark_list) else None

            try:
                payment_days_int = int(payment_days)
            except ValueError:
                return Response(
                    {"error": f"payment_days at index {idx} must be a number"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            matched_history = self.find_matching_account(credit_data, account_status)
            if not matched_history:
                continue

            gemini_result = self.classify_account(account_status, payment_days_int, creditor_remark)
            account_category_for_this = gemini_result.get("category", "Uncategorized")
            overall_account_category = account_category_for_this  # You may aggregate if needed.
            reason = gemini_result.get("reason", "")
            overall_reason.append(reason)

            if self.evaluate_dispute_letter_needed(account_status, payment_days_int, creditor_remark):
                disputed_account = {
                    "creditor_name": matched_history.get("furnisher_name"),
                    "account_number": matched_history.get("account_number"),
                    "reason_for_dispute": reason or "Incorrect account status or payment history."
                }
                # Add reported late payment dates only for late payment dispute letters.
                if account_category_for_this.lower() == "delinquent/late account":
                    disputed_account["reported_late_payment_dates"] = matched_history.get("date_last_payment")
                disputed_accounts.append(disputed_account)

        # Get common personal info from credit report
        personal_info = credit_data.get("report", {}).get("personalInformation", [])
        if personal_info and len(personal_info) > 0:
            personal = personal_info[0]
            your_name = personal.get("name", [""])[0]
            your_address = personal.get("current_addresses", [""])[0]
            credit_bureau_name = personal.get("credit_reporting_agency", {}).get("name", "")
        else:
            your_name = "John Doe"
            your_address = "123 Main St"
            credit_bureau_name = ""

        common_account_details = {
            "your_name": your_name,
            "your_address": your_address,
            "city_state_zip": "",
            "credit_bureau_name": credit_bureau_name
        }

        # Update response_data keys to match the ProcessSerializer expectations
        response_data = {
    "account_status": ", ".join(account_status_list),
    "payment_days": int(payment_days_list[0]) if payment_days_list else 0,
    "creditor_remark": ", ".join(creditor_remark_list) if creditor_remark_list and any(creditor_remark_list) else "Not Provided",
    "account_category": overall_account_category,
    "reason": "; ".join(overall_reason),
    "dispute_letter_generated": bool(disputed_accounts),
    "account_details": common_account_details,
    "disputed_accounts": disputed_accounts,
    "disputed_accounts_count": len(disputed_accounts)
}

        # Generate dispute letter if there is at least one disputed account
        if disputed_accounts:
            dispute_letter_markdown = DisputeLetterGenerator.generate_letter(
                common_account_details, overall_account_category, disputed_accounts
            )
            dispute_letter_pdf = self.convert_markdown_to_pdf(dispute_letter_markdown)
            if dispute_letter_pdf:
                response_data["dispute_letter_pdf"] = dispute_letter_pdf
            else:
                response_data["dispute_letter_pdf"] = "Failed to generate PDF."
            message = f"{len(disputed_accounts)} disputed account(s) processed. Dispute letter generated as PDF."
        else:
            message = "No disputed accounts require a dispute letter."

        serializer = ProcessSerializer(data=response_data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": message, "data": response_data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)