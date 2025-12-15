from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('cases', '0017_case_assigned_sro_employee_allowed_districts_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='casedocument',
            name='is_final',
            field=models.BooleanField(default=False),
        ),
    ]
