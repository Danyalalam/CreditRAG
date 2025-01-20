from django.db import models

class Process(models.Model):
    account_status = models.CharField(max_length=100)
    payment_days = models.IntegerField(null=True, blank=True)
    creditor_remark = models.CharField(max_length=100, null=True, blank=True)
    dispute_letter_generated = models.BooleanField(default=False)
    account_category = models.CharField(max_length=50, null=True, blank=True)  # New field

    def __str__(self):
        return f"{self.account_status} - {self.account_category} - Dispute: {self.dispute_letter_generated}"
