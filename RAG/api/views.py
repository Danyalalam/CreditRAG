import json
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

class ProcessView(APIView):
    def load_json(self, filename):
        """ Load the specified JSON file. """
        json_file_path = settings.BASE_DIR / f'api/{filename}'
        with open(json_file_path, 'r') as file:
            return json.load(file)

    def find_matching_account(self, json_data, account_status):
        """ Find account with matching status in accountHistories """
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

    def evaluate_dispute_letter_needed(self, account_status, payment_status=None, creditor_remark=None):
        """
        Determines if a dispute letter is needed.
        """
        if account_status.lower() in ['closed', 'paid']:
            return False
            
        if account_status.lower() == 'open':
            return False if payment_status and payment_status <= 30 else True
            
        if account_status.lower() == 'derogatory':
            if not creditor_remark:
                return True
            return False if creditor_remark.lower() == 'valid' else True

        return True


    def get_payment_days(self, payment_status):
        status_mapping = {
            "Current": 0,
            "30 Days Late": 30,
            "60 Days Late": 60,
            "90 Days Late": 90,
            "120 Days Late": 120
        }
        return status_mapping.get(payment_status, 0)

    