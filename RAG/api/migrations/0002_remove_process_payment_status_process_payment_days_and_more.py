# Generated by Django 5.1.4 on 2025-01-15 18:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='process',
            name='payment_status',
        ),
        migrations.AddField(
            model_name='process',
            name='payment_days',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='process',
            name='account_status',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='process',
            name='creditor_remark',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]