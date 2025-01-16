from django.db import models

class Process(models.Model):
    account_status = models.CharField(max_length=100)
    payment_days = models.IntegerField(null=True, blank=True)
    creditor_remark = models.CharField(max_length=100, null=True, blank=True)
    dispute_type = models.CharField(max_length=100, null=True, blank=True)
    dispute_letter_generated = models.BooleanField(default=False)
    dispute_letter = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True) 
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)      

    def __str__(self):
        return f"{self.account_status} - Dispute: {self.dispute_letter_generated}"