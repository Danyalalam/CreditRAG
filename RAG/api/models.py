from django.db import models

class Process(models.Model):
    payment_status = models.IntegerField()
    account_status = models.CharField(max_length=50)
    creditor_remark = models.TextField()
    dispute_letter_generated = models.BooleanField(default=False)

    def __str__(self):
        return f"Process {self.id}: {self.account_status}"
