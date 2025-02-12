from rest_framework import serializers
from .models import Process

class ProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = ['account_status', 'payment_days', 'creditor_remark', 'dispute_letter_generated', 'account_category']

    # Make fields optional
    payment_days = serializers.IntegerField(required=False, allow_null=True)
    creditor_remark = serializers.CharField(required=False, allow_null=True)
    account_status = serializers.CharField(required=True)
    dispute_letter_generated = serializers.BooleanField(required=False)
    account_category = serializers.CharField(required=False, allow_null=True)
