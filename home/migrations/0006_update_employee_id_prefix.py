from django.db import migrations


OLD_EMPLOYEE_PREFIX = '22MQ1A'
NEW_EMPLOYEE_PREFIX = '22MQ1A0'


def update_employee_id_prefixes(apps, schema_editor):
    Employee = apps.get_model('home', 'Employee')
    database = schema_editor.connection.alias

    employees = Employee.objects.using(database).filter(
        employee_id__startswith=OLD_EMPLOYEE_PREFIX,
    ).exclude(
        employee_id__startswith=NEW_EMPLOYEE_PREFIX,
    )

    for employee in employees.iterator():
        employee.employee_id = (
            f'{NEW_EMPLOYEE_PREFIX}'
            f'{employee.employee_id[len(OLD_EMPLOYEE_PREFIX):]}'
        )
        employee.save(using=database, update_fields=['employee_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0005_employeeidconfiguration'),
    ]

    operations = [
        migrations.RunPython(
            update_employee_id_prefixes,
            migrations.RunPython.noop,
        ),
    ]
