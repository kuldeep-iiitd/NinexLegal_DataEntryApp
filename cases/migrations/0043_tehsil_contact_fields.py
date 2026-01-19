from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0042_add_pdd_document_pending_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='tehsil',
            name='contact_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='tehsil',
            name='contact_number',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
