
from datetime import date

from django.db import models

from .department_assignment import resolve_employee_department


ROLE_CHOICES = (
    ('HR', 'HR'),
    ('EMPLOYEE', 'Employee'),
    ('ADMINISTRATION', 'Administration'),
)


def normalize_role(value):
    normalized = ' '.join((value or '').strip().upper().split())
    if normalized in {'ADMIN', 'ADMINISTRATION'}:
        return 'ADMINISTRATION'
    if normalized == 'HR':
        return 'HR'
    return 'EMPLOYEE'


class EmployeeIdConfiguration(models.Model):
    year = models.PositiveSmallIntegerField(default=date.today().year)


class Employee(models.Model):

    DEPARTMENT_CHOICES = [
        ('', 'Not assigned'),
        ('HR', 'HR (Human Resources)'),
        ('DEVELOPMENT', 'Development'),
        ('TESTING_QA', 'Testing'),
        ('DATABASE_ADMINISTRATION', 'Database Administration'),
        ('IT_SUPPORT', 'IT Support'),
    ]

    # ==========================================
    # ACCOUNT TYPE CHOICES
    # ==========================================

    ACCOUNT_CHOICES = [
        ('ADMIN', 'Admin'),
        ('HR', 'HR'),
        ('MANAGER', 'Manager'),
        ('EMPLOYEE', 'Employee'),
    ]
    ROLE_CHOICES = ROLE_CHOICES

    # ==========================================
    # EMPLOYEE ID
    # ==========================================

    employee_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True
    )

    # ==========================================
    # PERSONAL DETAILS
    # ==========================================

    full_name = models.CharField(
        max_length=100
    )

    username = models.CharField(
        max_length=100,
        unique=True
    )

    email = models.EmailField(
        unique=True
    )

    password = models.CharField(
        max_length=255
    )

    phone = models.CharField(
        max_length=15
    )

    address = models.TextField()

    # ==========================================
    # UPLOAD DETAILS
    # ==========================================

    photo = models.ImageField(
        upload_to='employees/photos/',
        blank=True,
        null=True
    )

    resume = models.FileField(
        upload_to='employees/resumes/',
        blank=True,
        null=True
    )

    document = models.FileField(
        upload_to='employees/documents/',
        blank=True,
        null=True
    )

    video = models.FileField(
        upload_to='employees/videos/',
        blank=True,
        null=True
    )

    # ==========================================
    # PROFESSIONAL DETAILS
    # ==========================================

    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    role = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    current_project = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    team_number = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    department = models.CharField(
        max_length=30,
        choices=DEPARTMENT_CHOICES,
        blank=True,
        default='',
    )

    # ==========================================
    # ACCOUNT TYPE
    # ==========================================

    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_CHOICES,
        default='EMPLOYEE'
    )

    # ==========================================
    # AUTOMATIC EMPLOYEE ID GENERATION
    # ==========================================

    def save(self, *args, **kwargs):
        if self.role is not None and isinstance(self.role, str):
            self.role = self.role.strip()
        if self.department is not None and isinstance(self.department, str):
            self.department = self.department.strip()
        elif self.department is None:
            self.department = ''

        if not self.employee_id:

            is_manager = (self.account_type or '').upper() == 'MANAGER'
            configuration, _ = EmployeeIdConfiguration.objects.get_or_create(
                pk=1,
                defaults={'year': date.today().year},
            )
            year_prefix = f'{configuration.year % 100:02d}MQ1'
            employees = Employee.objects.filter(
                employee_id__startswith=year_prefix,
            )
            highest_number = 100

            for employee in employees:
                employee_prefix = employee.employee_id[:len(year_prefix) + 2]
                if employee_prefix not in (
                    f'{year_prefix}A0',
                    f'{year_prefix}G0',
                ):
                    continue

                try:
                    number = int(
                        employee.employee_id[len(employee_prefix):]
                    )

                    if number > highest_number:
                        highest_number = number

                except (ValueError, TypeError):
                    continue

            new_number = highest_number + 1
            id_prefix = f'{year_prefix}{"G" if is_manager else "A"}0'

            self.employee_id = f"{id_prefix}{new_number:03d}"

        super().save(*args, **kwargs)

    # ==========================================
    # DISPLAY EMPLOYEE NAME
    # ==========================================

    def __str__(self):

        return self.full_name

    @property
    def is_department_counted(self):
        return resolve_employee_department(self) is not None

    @property
    def display_role(self):
        return dict(ROLE_CHOICES)[normalize_role(self.role)]

    @property
    def display_department(self):
        if not self.department or not self.department.strip():
            return "Not Assigned"
        return dict(self.DEPARTMENT_CHOICES).get(self.department, self.department)
