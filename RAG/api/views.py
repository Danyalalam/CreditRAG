import json
import os
import sys
import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Process
from .serializers import ProcessSerializer
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class ProcessView(APIView):
    def load_json(self):
        json_file_path = os.path.join(settings.BASE_DIR, 'api', 'identityiq_1.json')
        with open(json_file_path, 'r') as file:
            return json.load(file)

    def evaluate_dispute_letter_needed(self, account_status, payment_status=None, creditor_remark=None):
        """
        Determines if a dispute letter is needed based on the flowchart logic.
        Returns: (bool) whether a dispute letter should be generated
        """
        # Direct "No" paths
        if account_status.lower() in ['closed', 'paid']:
            return False
            
        # Open account path
        if account_status.lower() == 'open':
            if payment_status and payment_status <= 30:
                return False
            return True
            
        # Derogatory account path
        if account_status.lower() == 'derogatory':
            if not creditor_remark:
                return True
            if creditor_remark.lower() == 'valid':
                return False
            if creditor_remark.lower() == 'invalid':
                return True
            
        # Default case - if we can't determine, we'll err on the side of generating a letter
        return True

    def evaluate_dispute_type(self, account_status, payment_status=None, creditor_remark=None):
        """
        Determine the dispute type based on the account status and creditor remark.
        Returns: (str) dispute type key
        """
        status_lower = account_status.lower()
        remark_lower = creditor_remark.lower() if creditor_remark else ''

        if status_lower == 'derogatory':
            if remark_lower == 'valid':
                return "derogatory_valid"
            elif remark_lower in ['invalid', 'unverified']:
                return "derogatory_invalid"
            else:
                return "derogatory_account"
        else:
            # Since only 'closed' and 'paid' do not require dispute letters,
            # any other status not 'derogatory' falls under 'general_dispute'
            return "general_dispute"

    def generate_dispute_letter(self, template_name, context):
        """
        Generates an HTML dispute letter using Jinja2 templates.
        """
        templates_path = os.path.join(settings.BASE_DIR, 'api', 'templates', 'dispute_letters')
        env = Environment(loader=FileSystemLoader(templates_path))
        template = env.get_template(template_name)
        return template.render(context)

    def get_payment_days(self, payment_status):
        """
        Convert payment_status string to number of days
        """
        status_mapping = {
            "Current": 0,
            "30 Days Late": 30,
            "60 Days Late": 60,
            "90 Days Late": 90,
            "120 Days Late": 120
        }
        return status_mapping.get(payment_status, 0)

    def get(self, request, format=None):
        # Extract query parameters
        account_status = request.query_params.get("account_status")
        payment_days = request.query_params.get("payment_days")
        creditor_remark = request.query_params.get("creditor_remark")

        logger.debug(f"Received request with account_status={account_status}, payment_days={payment_days}, creditor_remark={creditor_remark}")

        # Validate required parameters
        if not account_status:
            logger.error("Missing account_status parameter")
            return Response(
                {"error": "Missing account_status parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load JSON data
        try:
            json_data = self.load_json()
            logger.debug("JSON data loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading JSON data: {e}")
            return Response(
                {"error": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Navigate the JSON structure
        account_histories = json_data.get('report', {}).get('accountHistories', [])

        # Find matching account history
        matched_history = None
        for history in account_histories:
            if history.get('account_status', '').lower() == account_status.lower():
                matched_history = history
                # If payment_days wasn't provided in URL, get it from JSON
                if not payment_days and history.get('payment_status'):
                    payment_days = str(self.get_payment_days(history['payment_status']))
                break

        if matched_history:
            logger.debug("Matched account history found.")
            # Convert payment_days to integer if present
            payment_days_int = None
            if payment_days:
                try:
                    payment_days_int = int(payment_days)
                except ValueError:
                    logger.error("Invalid payment_days parameter")
                    return Response(
                        {"error": "payment_days must be a number"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Determine if dispute letter is needed
            dispute_letter_needed = self.evaluate_dispute_letter_needed(
                account_status=account_status,
                payment_status=payment_days_int,
                creditor_remark=creditor_remark
            )
            logger.debug(f"Dispute letter needed: {dispute_letter_needed}")

            # Determine dispute type if letter is needed
            if dispute_letter_needed:
                dispute_type = self.evaluate_dispute_type(
                    account_status=account_status,
                    payment_status=payment_days_int,
                    creditor_remark=creditor_remark
                )
                logger.debug(f"Determined dispute_type: {dispute_type}")

                # Mapping of dispute types to their respective templates
                TEMPLATE_MAPPING = {
                    "derogatory_account": "derogatory_account.html",
                    "derogatory_valid": "derogatory_valid.html",
                    "derogatory_invalid": "derogatory_invalid.html",
                    "general_dispute": "general_dispute.html"  # Optional: Handle unexpected statuses
                }

                template_name = TEMPLATE_MAPPING.get(dispute_type, "general_dispute.html")
                logger.debug(f"Using template: {template_name}")

                # Prepare context for the template
                letter_context = {
                    "current_date": datetime.now().strftime("%Y-%m-%d"),
                    "account_status": account_status,
                    "payment_days": payment_days_int,
                    "creditor_remark": creditor_remark,
                    "account_details": {
                        "furnisher_name": matched_history.get('furnisher_name'),
                        "account_number": matched_history.get('account_number'),
                        "account_type": matched_history.get('account_type'),
                        "balance": matched_history.get('balance'),
                        "last_reported": matched_history.get('last_reported')
                    }
                }

                try:
                    dispute_letter = self.generate_dispute_letter(template_name, letter_context)
                    logger.debug("Dispute letter generated successfully.")
                except Exception as e:
                    logger.error(f"Error generating dispute letter: {e}")
                    return Response(
                        {"error": "Error generating dispute letter."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                dispute_type = None
                logger.debug("No dispute letter needed based on input parameters.")

            # Prepare response data
            response_data = {
                "account_status": account_status,
                "payment_days": payment_days_int,
                "creditor_remark": creditor_remark,
                "dispute_type": dispute_type if dispute_letter_needed else None,
                "dispute_letter_generated": dispute_letter_needed,
                "account_details": {
                    "furnisher_name": matched_history.get('furnisher_name'),
                    "account_number": matched_history.get('account_number'),
                    "account_type": matched_history.get('account_type'),
                    "balance": matched_history.get('balance'),
                    "last_reported": matched_history.get('last_reported')
                }
            }

            if dispute_letter_needed:
                response_data["dispute_letter"] = dispute_letter

            # Save to database
            serializer = ProcessSerializer(data=response_data)
            if serializer.is_valid():
                serializer.save()
                message = "Dispute letter generated." if dispute_letter_needed else "No dispute letter needed."
                logger.info(message)
                return Response(
                    {"message": message, "data": response_data},
                    status=status.HTTP_200_OK
                )
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        logger.error("No matching account history found.")
        return Response(
            {"error": "No matching account history found."},
            status=status.HTTP_404_NOT_FOUND
        )