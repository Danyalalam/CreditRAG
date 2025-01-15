import json
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Process
from .serializers import ProcessSerializer

class ProcessView(APIView):
    def load_json(self):
        json_file_path = settings.BASE_DIR / 'api/identityiq_1.json'
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

        # Validate required parameters
        if not account_status:
            return Response(
                {"error": "Missing account_status parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Load JSON data
        json_data = self.load_json()
        
        # Correctly navigate the JSON structure
        account_histories = json_data.get('report', {}).get('accountHistories', [])

        # Find matching account history
        matched_history = None
        for history in account_histories:
            if history.get('account_status') == account_status:
                matched_history = history
                # If payment_days wasn't provided in URL, get it from JSON
                if not payment_days and history.get('payment_status'):
                    payment_days = str(self.get_payment_days(history['payment_status']))
                break

        if matched_history:
            # Convert payment_days to integer if present
            payment_days_int = None
            if payment_days:
                try:
                    payment_days_int = int(payment_days)
                except ValueError:
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

            # Prepare response data
            response_data = {
                "account_status": account_status,
                "payment_days": payment_days_int,
                "creditor_remark": creditor_remark,
                "dispute_letter_generated": dispute_letter_needed,
                "account_details": {
                    "furnisher_name": matched_history.get('furnisher_name'),
                    "account_number": matched_history.get('account_number'),
                    "account_type": matched_history.get('account_type'),
                    "balance": matched_history.get('balance'),
                    "last_reported": matched_history.get('last_reported')
                }
            }

            # Save to database
            serializer = ProcessSerializer(data=response_data)
            if serializer.is_valid():
                serializer.save()
                message = "Dispute letter generated." if dispute_letter_needed else "No dispute letter needed."
                return Response(
                    {"message": message, "data": response_data},
                    status=status.HTTP_200_OK
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"error": "No matching account history found."},
            status=status.HTTP_404_NOT_FOUND
        )