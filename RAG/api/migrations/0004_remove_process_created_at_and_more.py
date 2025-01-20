# Generated by Django 5.1.4 on 2025-01-20 10:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_process_created_at_process_dispute_letter_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='process',
            name='created_at',
        ),
        migrations.RemoveField(
            model_name='process',
            name='dispute_letter',
        ),
        migrations.RemoveField(
            model_name='process',
            name='dispute_type',
        ),
        migrations.RemoveField(
            model_name='process',
            name='updated_at',
        ),
        migrations.AddField(
            model_name='process',
            name='account_category',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
