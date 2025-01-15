from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import os
import json
from django.conf import settings
from .models import Process
from .serializers import ProcessSerializer


class ProcessView(APIView):
    PAYMENT_STATUS_MAPPING = {
        "Current": 0,
        "Late 30 Days": 30,
        "Late 60 Days": 60,
        "Late 90 Days": 90,
        "Late 120 Days": 120
    }

    def get(self, request, format=None):
        # Path to the JSON file
        json_file_path = os.path.join(settings.BASE_DIR, 'api', 'identityiq_1.json')

        # Load JSON data with error handling
        try:
            with open(json_file_path, 'r') as file:
                data = json.load(file)

            # Navigate to accountHistories
            account_histories = data.get("report", {}).get("accountHistories", [])
            if not account_histories:
                return Response({"error": "No accountHistories found in the JSON file."}, status=status.HTTP_400_BAD_REQUEST)

        except FileNotFoundError:
            return Response({"error": "identityiq_1.json not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON format in identityiq_1.json."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Extract query parameters
        payment_status = request.query_params.get("payment_status")
        account_status = request.query_params.get("account_status")
        creditor_remark = request.query_params.get("creditor_remark", "")

        # Validate payment_status
        if not payment_status or payment_status not in self.PAYMENT_STATUS_MAPPING:
            return Response(
                {"error": f"Invalid or missing payment_status: {payment_status}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Convert payment_status to numerical value
        payment_status_value = self.PAYMENT_STATUS_MAPPING[payment_status]

        # Validate account_status
        if not account_status:
            return Response({"error": "Missing account_status."}, status=status.HTTP_400_BAD_REQUEST)

        # Filter relevant records from accountHistories
        matching_entries = []
        for entry in account_histories:
            if (
                entry.get("paymentStatus") == payment_status and
                entry.get("accountStatus") == account_status
            ):
                matching_entries.append(entry)

        # Business logic
        dispute_letter_generated = payment_status_value >= 30 and account_status.lower() == "paid"

        # Prepare response data
        response_data = {
            "payment_status": payment_status_value,  # Convert string to integer
            "account_status": account_status,
            "creditor_remark": creditor_remark,
            "dispute_letter_generated": dispute_letter_generated,
            "matching_entries": matching_entries
        }

        # Save to the database (if needed)
        serializer = ProcessSerializer(data=response_data)
        if serializer.is_valid():
            serializer.save()
            message = "Dispute letter generated." if dispute_letter_generated else "Conditions not met for dispute letter."
            return Response({"message": message, "data": serializer.data}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
