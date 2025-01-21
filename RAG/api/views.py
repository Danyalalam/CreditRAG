import json
import os
import google.generativeai as genai
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Process
from .serializers import ProcessSerializer

# Initialize Google Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

class DisputeLetterGenerator:
    TEMPLATE_DIR = settings.BASE_DIR / "api/templates/dispute_letters"

    @staticmethod
    def select_template(account_category):
        """Select the appropriate template based on account category."""
        # Normalize the account category to match the keys in template_mapping
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
        print(f"Loading template from: {template_path}")  # Debug statement
        try:
            with open(template_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            print(f"Template not found: {template_name}")  # Debug statement
            # Fallback to a default template or raise a meaningful error
            fallback_path = os.path.join(DisputeLetterGenerator.TEMPLATE_DIR, "generic_dispute.md")
            try:
                with open(fallback_path, "r") as file:
                    return file.read()
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Neither the requested template ({template_name}) nor the fallback template (generic_dispute.md) was found in {DisputeLetterGenerator.TEMPLATE_DIR}."
                )

    @staticmethod
    def generate_letter(account_details, account_category):
        """Generate a dispute letter using the selected template and LLM."""
        # Select and load the template
        template_name = DisputeLetterGenerator.select_template(account_category)
        template_content = DisputeLetterGenerator.load_template(template_name)

        # Prepare the prompt for the LLM
        prompt = f"""
        You are a financial assistant helping to generate a dispute letter.  
        Use the following template and fill in the placeholders with the provided account details:  

        **Template:**  
        {template_content}  

        **Account Details:**  
        {json.dumps(account_details, indent=2)}  

        **Instructions:**  
        - Replace placeholders like [Your Name], [Creditor Name], etc., with the actual values.  
        - Replace [Date] with today's date in the format "Month Day, Year".  
        - Replace [Reason for Dispute] with a concise explanation based on the account details.  
        - Keep the markdown formatting intact.  
        - Do not add any extra text or explanations.  
        """

        # Call the LLM to generate the letter
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(prompt)

        # Extract the generated letter
        return response.text

class ProcessView(APIView):
    def load_json(self, filename):
        """Load the specified JSON file."""
        json_file_path = settings.BASE_DIR / f'api/{filename}'
        with open(json_file_path, 'r') as file:
            return json.load(file)

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
        # Load both JSON files
        credit_data = self.load_json("identityiq_1.json")
        knowledge_base = self.load_json("output_data.json")  # The actual knowledge base

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

        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(prompt)

        # Extract only the JSON response from Gemini
        try:
            json_start = response.text.find("{")
            json_end = response.text.rfind("}") + 1
            cleaned_json = response.text[json_start:json_end]  # Extract the JSON part

            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            return {"category": "Uncategorized", "reason": "LLM response could not be parsed"}

    def evaluate_dispute_letter_needed(self, account_status, payment_status=None, creditor_remark=None):
        """
        Determines if a dispute letter is needed based on the provided criteria.
        """
        account_status = account_status.lower()

        # No dispute letter needed for closed or paid accounts
        if account_status in ['closed', 'paid']:
            return False

        # For open accounts
        if account_status == 'open':
            if payment_status is not None and payment_status <= 30:
                return False  # No dispute letter needed if payment status <= 30 days
            return True  # Dispute letter needed if payment status > 30 days

        # For derogatory accounts
        if account_status == 'derogatory':
            if creditor_remark and creditor_remark.lower() == 'valid':
                return False  # No dispute letter needed if creditor remark is valid
            return True  # Dispute letter needed if creditor remark is invalid or missing

        # Default to no dispute letter
        return False

    def get(self, request, format=None):
        """
        Handle GET requests to classify accounts using Google Gemini with the Knowledge Base.
        """
        account_status = request.query_params.get("account_status")
        payment_days = request.query_params.get("payment_days")
        creditor_remark = request.query_params.get("creditor_remark")

        if not account_status:
            return Response(
                {"error": "Missing account_status parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        credit_data = self.load_json("identityiq_1.json")
        matched_history = self.find_matching_account(credit_data, account_status)

        if matched_history:
            payment_days_int = None
            if payment_days:
                try:
                    payment_days_int = int(payment_days)
                except ValueError:
                    return Response(
                        {"error": "payment_days must be a number"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Call Gemini for classification using Credit Data + Knowledge Base
            gemini_result = self.classify_account(account_status, payment_days_int, creditor_remark)
            account_category = gemini_result["category"]
            reason = gemini_result["reason"]

            dispute_letter_needed = self.evaluate_dispute_letter_needed(
                account_status=account_status,
                payment_status=payment_days_int,
                creditor_remark=creditor_remark
            )

            response_data = {
                "account_status": account_status,
                "payment_days": payment_days_int,
                "creditor_remark": creditor_remark,
                "account_category": account_category,
                "reason": reason,
                "dispute_letter_generated": dispute_letter_needed,
                "account_details": {
                    "furnisher_name": matched_history.get('furnisher_name'),
                    "account_number": matched_history.get('account_number'),
                    "account_type": matched_history.get('account_type'),
                    "balance": matched_history.get('balance'),
                    "last_reported": matched_history.get('last_reported')
                }
            }

            # Generate dispute letter if needed
            if dispute_letter_needed:
                account_details = {
                    "your_name": "John Doe",  # Replace with actual user details
                    "your_address": "123 Main St",
                    "city_state_zip": "City, State, ZIP",
                    "creditor_name": matched_history.get('furnisher_name'),
                    "creditor_address": "Creditor Address",  # Replace with actual creditor address
                    "account_number": matched_history.get('account_number'),
                    "account_status": account_status,
                    "payment_status": payment_days_int,
                    "creditor_remark": creditor_remark,
                    "reason_for_dispute": "Incorrect account status or payment history.",  # Add a reason for dispute
                }

                dispute_letter = DisputeLetterGenerator.generate_letter(account_details, account_category)
                response_data["dispute_letter"] = dispute_letter

            serializer = ProcessSerializer(data=response_data)
            if serializer.is_valid():
                serializer.save()
                message = f"Account categorized as {account_category}. "
                if dispute_letter_needed:
                    message += "Dispute letter generated."
                else:
                    message += "No dispute letter needed."

                return Response({"message": message, "data": response_data}, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"error": "No matching account history found."},
            status=status.HTTP_404_NOT_FOUND
        )