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
import google.generativeai as genai

# Initialize Logger
logger = logging.getLogger(__name__)

# Initialize OpenAI
openai.api_key = settings.OPENAI_API_KEY

# Initialize Pinecone with new API style
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX)

class DisputeLetterGenerator:
    # Update to point to the html_letters directory
    TEMPLATE_DIR = settings.BASE_DIR / "api/templates/html_letters"

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
        # Update mapping to use HTML templates
        template_mapping = {
            "positive_account": "Positive_Account_Dispute_Letter Template.html",
            "derogatory_account": "Derogatory Account Dispute Letter Template.html",
            "delinquent_late_account": "Late Payment Dispute Letter Template.html",
            "inquiry_account": "Inquiry Dispute Letter Template.html",
            "public_record_account": "Public Record Dispute Letter Template.html"
        }
        return template_mapping.get(account_category, "generic_dispute_letter.html")

    @staticmethod
    def load_template(template_name):
        template_path = os.path.join(DisputeLetterGenerator.TEMPLATE_DIR, template_name)
        try:
            with open(template_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            fallback_path = os.path.join(DisputeLetterGenerator.TEMPLATE_DIR, "generic_dispute_letter.html")
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

        # Optionally, build a table of disputed accounts if needed
        disputed_accounts_text = ""
        if disputed_accounts:
            header = "Creditor\tAccount Number/Type\tReported Date\tReason for Dispute"
            rows = []
            for acc in disputed_accounts:
                if acc.get("account_type") == "inquiry":
                    creditor = acc.get("creditor_name", "N/A")
                    account_info = acc.get("type_of_business", "N/A")
                    date_field = acc.get("date_of_inquiry", "N/A")
                    reason = acc.get("credit_bureau", "N/A")
                elif acc.get("account_type") == "public_record":
                    creditor = acc.get("creditor_name", "N/A")
                    account_info = "-" 
                    date_field = "-"
                    reason = acc.get("reason_for_dispute", "N/A")
                else:
                    creditor = acc.get("creditor_name", "N/A")
                    account_info = acc.get("account_number", "N/A")
                    date_field = acc.get("reported_late_payment_dates", "N/A")
                    reason = acc.get("reason_for_dispute", "N/A")
                rows.append(f"{creditor}\t{account_info}\t{date_field}\t{reason}")
            disputed_accounts_text = "\n".join([header] + rows)
            disputed_accounts_text = f"<p>Details of the Disputed Account(s):<br>{disputed_accounts_text.replace(chr(9), '&nbsp;&nbsp;&nbsp;')}</p>"

        prompt = f"""
You are a financial assistant and credit repair expert generating a dispute letter in HTML format.

<strong>Template:</strong>
{template_content}

<strong>Account Details:</strong>
<pre>{json.dumps(account_details, indent=2)}</pre>

{disputed_accounts_text}
<strong>Relevant Regulations and Laws:</strong>
<pre>{regulations_text}</pre>

Instructions:
0. Do add the complete info of the user including the name, account number, and address.
1. Use the template structure but customize it.
2. Reference specific regulations supporting the dispute.
3. Clearly state what is being disputed and why.
4. Maintain a professional tone.
5. Include all relevant information.
6. Return the final letter as valid HTML.
"""
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a financial assistant helping to generate a dispute letter in HTML format."},
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
            file.seek(0)  # Reset file pointer before reading
            data = json.load(file)
        except Exception as e:
            return Response({"error": "Invalid JSON file."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Save report for future reference
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
            helper = ProcessHelper()
            
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
                
                # Query Pinecone for relevant regulations to flag violations
                query = f"""
                Classification criteria for credit account with:
                Status: {account_status}
                Payment Days Late: {payment_days}
                Remark: {creditor_remark}
                """
                relevant_docs = vectorstore.similarity_search(query, k=2)
                regulations_text = "\n".join([doc.page_content for doc in relevant_docs])
                
                # Use Gemini (through ProcessHelper) for classification with assigned rules and knowledge base.
                result = helper.classify_account(account_status, payment_status=payment_days, creditor_remark=creditor_remark)
                
                # Append flagged regulations to the classification reason
                result["reason"] += f" | Flagged Regulations: {regulations_text}" if regulations_text else ""
                
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
    def post(self, request, format=None):
        received_data = request.data
        account_details = received_data.get("account_details")
        provided_category = received_data.get("account_category")
        # Get disputed accounts from the report data if available
        disputed_accounts = received_data.get("extracted_disputed_accounts", [])
        if not account_details:
            return Response({"error": "Missing required field: account_details."}, status=status.HTTP_400_BAD_REQUEST)
        
        overall_category = provided_category if provided_category else "delinquent_late_account"
        dispute_letter_markdown = DisputeLetterGenerator.generate_letter(
            account_details, overall_category, disputed_accounts
        )
        return Response({"dispute_markdown": dispute_letter_markdown}, status=status.HTTP_200_OK)

class DownloadPDFView(APIView):
    def get(self, request, format=None):
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
        # Normalize input values
        acc_status = account_status.lower() if account_status else ""
        pay_status = payment_status.lower() if payment_status else ""
        remarks = creditor_remark.lower() if creditor_remark else ""

        # Build prompt with explicit rules for the Gemini model.
        prompt = f"""
You are a financial expert analyzing credit reports. Use the following classification rules:

1. Positive Account:
   - Account Status: Open, Paid, or any other positive account status.
   - Payment Status: Current or Paid As Agreed.
   - Late Status: No late payments.
   - Report Comments: No derogatory remarks.
   Example: IF account_status = "current" AND no late_payments AND no derogatory_remarks THEN Positive Account

2. Derogatory Account:
   - Account Status: Derogatory, Indeterminate, etc.
   - Payment Status: Charge-off, Collection, Repossession, Foreclosure.
   - Report Comments: Contains charge-off or collection remarks.
   Example: IF account_status IN ["charge-off", "collection", "settled", "repossession"] OR derogatory_remarks EXISTS THEN Derogatory Account

3. Inquiry:
   - Type: Inquiry (hard or soft) and if the inquiry date is within 2 years.
   Example: IF account_type = "inquiry" THEN Inquiry

4. Delinquent or Late Account:
   - Payment Status: Late payments (e.g., 30_days_late, 60_days_late, 90_days_late) or account_status equals "past_due".
   Example: IF payment_status IN ["30_days_late", "60_days_late", "90_days_late"] OR account_status = "past_due" THEN Delinquent or Late Account

5. Public Record:
   - Type: Public Record (including bankruptcies, liens, judgments).
   Example: IF account_type = "public_record" THEN Public Record

Given the following details:
- Account Status: {account_status}
- Payment Status: {payment_status}
- Creditor Remark: {creditor_remark}

Return a JSON object exactly in the following format without any extra text:
{{
    "category": "Categorized Account Type",
    "reason": "Explanation for classification"
}}
"""
        # Call the Gemini model with the prompt
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        try:
            json_start = response.text.find("{")
            json_end = response.text.rfind("}") + 1
            cleaned_json = response.text[json_start:json_end]
            gemini_result = json.loads(cleaned_json)
        except Exception as e:
            logger.error("Error parsing gemini response: " + str(e))
            gemini_result = None

        # Apply rule-based logic independently.
        if acc_status == "inquiry":
            rule_result = {"category": "Inquiry Account", "reason": "Account type is inquiry."}
        elif acc_status == "public record":
            rule_result = {"category": "Public Record Account", "reason": "Account type is public record."}
        elif acc_status in ["charge-off", "collection", "settled", "repossession"] or ("charge-off" in remarks or "collection" in remarks):
            rule_result = {"category": "Derogatory Account", "reason": "Account status or remarks indicate derogatory activity."}
        elif acc_status in ["current", "open", "paid"] and \
             pay_status in ["current", "paid as agreed", "paid_as_agreed"] and \
             "late" not in pay_status and \
             ("charge-off" not in remarks and "collection" not in remarks):
            rule_result = {"category": "Positive Account", "reason": "Account is in good standing with no late or derogatory indicators."}
        elif pay_status in ["30_days_late", "60_days_late", "90_days_late"] or acc_status == "past_due":
            rule_result = {"category": "Delinquent/Late Account", "reason": "Account shows evidence of late or delinquent payments."}
        else:
            rule_result = {"category": "Uncategorized", "reason": "No matching criteria found based on account details."}

        # If Gemini result exists and differs from the rule-based result, combine the insights.
        if gemini_result and gemini_result.get("category") != rule_result.get("category"):
            combined_result = {
                "category": rule_result.get("category"),
                "reason": f"Rule-based: {rule_result.get('reason')} | Gemini-based: {gemini_result.get('reason')}"
            }
            return combined_result
        elif gemini_result:
            return gemini_result
        else:
            return rule_result
