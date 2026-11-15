from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0006_update_employee_id_prefix'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeIdConfiguration',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'year',
                    models.PositiveSmallIntegerField(
                        default=2026,
                    ),
                ),
            ],
        ),
    ]
