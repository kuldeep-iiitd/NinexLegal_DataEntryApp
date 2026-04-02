from django.db import migrations, models
from django.utils import timezone


def backfill_mail_flags(apps, schema_editor):
    Case = apps.get_model('cases', 'Case')
    CaseDocument = apps.get_model('cases', 'CaseDocument')
    now = timezone.now()

    # Mark existing completed cases as already mailed for advocate
    Case.objects.filter(completed_at__isnull=False).update(
        advocate_mail_sent=True,
        advocate_mail_sent_at=now,
    )

    # Mark existing receipt cases as already mailed for SRO
    receipt_case_ids = CaseDocument.objects.filter(is_receipt=True).values_list('case_id', flat=True).distinct()
    Case.objects.filter(id__in=list(receipt_case_ids)).update(
        sro_mail_sent=True,
        sro_mail_sent_at=now,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0043_tehsil_contact_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='advocate_mail_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='case',
            name='advocate_mail_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='case',
            name='sro_mail_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='case',
            name='sro_mail_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_mail_flags, migrations.RunPython.noop),
    ]
