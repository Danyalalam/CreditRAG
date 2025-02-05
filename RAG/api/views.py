import json
import os
import base64
from pinecone import Pinecone, ServerlessSpec
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Pinecone as LangchainPinecone
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import markdown
import logging
import openai

# Initialize Logger
logger = logging.getLogger(__name__)

# Initialize OpenAI
openai.api_key = settings.OPENAI_API_KEY

# Initialize Pinecone with new API style
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX)

class DisputeLetterGenerator:
    TEMPLATE_DIR = settings.BASE_DIR / "api/templates/dispute_letters"

    @staticmethod
    def get_relevant_regulations(account_details, account_category):
        """Query Pinecone for relevant regulations based on account details"""
        try:
            query = f"""
            Find regulations relevant to disputing a {account_category} where:
            - Account Status: {account_details.get('account_status')}
            - Payment History: {account_details.get('payment_history')}
            - Creditor: {account_details.get('creditor_name')}
            - Dispute Reason: {account_details.get('reason_for_dispute')}
            """
            
            embeddings = OpenAIEmbeddings()
            vectorstore = LangchainPinecone(index, embeddings.embed_query, "text")
            
            relevant_docs = vectorstore.similarity_search(query, k=3)
            
            regulations = []
            for doc in relevant_docs:
                regulations.append({
                    'content': doc.page_content,
                    'source': f"{doc.metadata['filename']} - Page {doc.metadata['page_number']}"
                })
                
            return regulations
        except Exception as e:
            logger.error(f"Error retrieving regulations: {str(e)}")
            return []

    @staticmethod
    def select_template(account_category):
        account_category = account_category.lower().replace(" ", "_")
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
        regulations = DisputeLetterGenerator.get_relevant_regulations(account_details, account_category)
        template_name = DisputeLetterGenerator.select_template(account_category)
        template_content = DisputeLetterGenerator.load_template(template_name)

        regulations_text = "\n".join([
            f"From {reg['source']}:\n{reg['content']}" 
            for reg in regulations
        ])

        prompt = f"""
You are a financial assistant and credit repair expert generating a dispute letter.

**Template:**
{template_content}

**Account Details:**
{json.dumps(account_details, indent=2)}

**Disputed Accounts:**
{json.dumps(disputed_accounts, indent=2)}

**Relevant Regulations and Laws:**
{regulations_text}

Instructions:
1. Use the template structure but customize it
2. Reference specific regulations supporting the dispute
3. For each disputed item, clearly state:
   - What is being disputed
   - Why it's being disputed
   - Supporting evidence or regulation
4. Maintain professional tone
5. Include all relevant information
6. Keep markdown formatting
"""
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial assistant helping to generate a dispute letter."},
                {"role": "user", "content": prompt}
            ]
        )
        return response['choices'][0]['message']['content']

class UploadReportView(APIView):
    def post(self, request, format=None):
        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            file.seek(0)
            data = json.load(file)
            
            # Extract personal information
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
            
            # Extract accounts
            account_histories = data.get("report", {}).get("accountHistories", [])
            extracted_disputed_accounts = []
            
            for account in account_histories:
                status_val = account.get("account_status", "").lower()
                if status_val not in ["closed", "paid"]:
                    disputed_account = {
                        "creditor_name": account.get("furnisher_name", "Unknown"),
                        "account_number": account.get("account_number", ""),
                        "reason_for_dispute": account.get("reason_for_dispute", "Please review."),
                        "reported_late_payment_dates": account.get("date_last_payment", ""),
                        "account_status": status_val,
                        "payment_history": account.get("payment_history", ""),
                        "current_balance": account.get("current_balance", "")
                    }
                    extracted_disputed_accounts.append(disputed_account)
            
            # Save report for future reference
            reports_dir = settings.BASE_DIR / "api/reports"
            os.makedirs(reports_dir, exist_ok=True)
            file_path = reports_dir / "uploaded_report.json"
            with open(file_path, 'w') as f:
                json.dump(data, f)
            
            return Response({
                "message": "Report uploaded successfully.",
                "extracted_account_details": extracted_account_details,
                "extracted_disputed_accounts": extracted_disputed_accounts,
                "default_account_category": "delinquent_late_account"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing report: {str(e)}")
            return Response(
                {"error": f"Error processing report: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class CategorizeAccountsView(APIView):
    def get(self, request, format=None):
        try:
            account_status_list = request.query_params.getlist("account_status")
            payment_days_list = request.query_params.getlist("payment_days")
            creditor_remark_list = request.query_params.getlist("creditor_remark")
            
            if not account_status_list:
                return Response(
                    {"error": "Missing account_status parameter(s)"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            classifications = []
            embeddings = OpenAIEmbeddings()
            vectorstore = LangchainPinecone(index, embeddings.embed_query, "text")
            
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
                
                # Query Pinecone
                query = f"""
                Classification criteria for credit account with:
                Status: {account_status}
                Payment Days Late: {payment_days}
                Remark: {creditor_remark}
                """
                
                relevant_docs = vectorstore.similarity_search(query, k=2)
                regulations_text = "\n".join([doc.page_content for doc in relevant_docs])
                
                # Use OpenAI for classification
                classification_prompt = f"""
                Based on these details and regulations:

                Account Status: {account_status}
                Days Late: {payment_days}
                Creditor Remark: {creditor_remark}

                Relevant Regulations:
                {regulations_text}

                Classify as one of:
                - Positive Account
                - Derogatory Account
                - Delinquent/Late Account
                - Inquiry Account
                - Public Record Account

                Respond in JSON format:
                {{"category": "category_name", "reason": "detailed_reason"}}
                """

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a credit report analysis expert."},
                        {"role": "user", "content": classification_prompt}
                    ]
                )
                
                result = json.loads(response['choices'][0]['message']['content'])
                classifications.append({
                    "account_status": account_status,
                    "payment_days": payment_days_int,
                    "creditor_remark": creditor_remark,
                    "category": result["category"],
                    "reason": result["reason"]
                })
            
            return Response({"classifications": classifications}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in account categorization: {str(e)}")
            return Response(
                {"error": "Failed to categorize accounts"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
        provided_category = received_data.get("account_category")  # Ensure this is passed correctly
        disputed_accounts = received_data.get("disputed_accounts")
        if not account_details or disputed_accounts is None:
            return Response({"error": "Missing required fields."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Use the provided category or compute it if not provided
        overall_category = provided_category if provided_category else self.determine_category(disputed_accounts)
        
        # Generate the dispute letter using the determined category
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
        model = genai.GenerativeModel("gpt-3.5-turbo")
        response = model.generate_content(prompt)
        try:
            json_start = response.text.find("{")
            json_end = response.text.rfind("}") + 1
            cleaned_json = response.text[json_start:json_end]
            return json.loads(cleaned_json)
        except json.JSONDecodeError:
            logger.error("LLM response could not be parsed into JSON.")
            return {"category": "Uncategorized", "reason": "LLM response could not be parsed"}