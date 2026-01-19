# Generated migration to add pdd_document_pending status

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0032_case_assigned_sro_alter_case_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='case',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('quotation', 'Quotation'),
                    ('positive', 'Positive'),
                    ('negative', 'Negative'),
                    ('on_hold', 'On Hold'),
                    ('on_query', 'On Query'),
                    ('query', 'Query'),
                    ('document_pending', 'Document Pending'),
                    ('sro_document_pending', 'SRO Document Pending'),
                    ('pdd_document_pending', 'PDD Document Pending'),
                    ('positive_subject_tosearch', 'Positive Subject to Search'),
                    ('draft_positive_subject_tosearch', 'Draft Positive Subject to Search'),
                    ('pending_assignment', 'Pending Assignment'),
                    ('pending', 'Pending'),
                    ('done', 'Done'),
                ],
                default='pending',
                max_length=50
            ),
        ),
    ]
