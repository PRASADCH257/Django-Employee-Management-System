import secrets
import logging
from datetime import timedelta
from smtplib import SMTPException, SMTPServerDisconnected
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.mail.message import BadHeaderError
from django.db.models import Count, Q
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .forms import (
    EmployeeProfessionalEditForm,
    EmployeeRegistrationForm,
    ManagerEmployeeEditForm,
)
from .department_assignment import department_assignment_filter
from .models import Employee

EMPLOYEE_SESSION_KEY = 'home_employee_id'
PASSWORD_RESET_TTL = timedelta(minutes=10)
PASSWORD_RESET_MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)

DEPARTMENTS = (
    {
        'slug': 'hr',
        'code': 'HR',
        'name': 'HR (Human Resources)',
        'description': 'Hiring employees, managing salaries and attendance.',
    },
    {
        'slug': 'development',
        'code': 'DEVELOPMENT',
        'name': 'Development',
        'description': 'Developing websites, applications and software.',
    },
    {
        'slug': 'testing-qa',
        'code': 'TESTING_QA',
        'name': 'Testing',
        'description': 'Finding bugs and testing software.',
    },
    {
        'slug': 'database-administration',
        'code': 'DATABASE_ADMINISTRATION',
        'name': 'Database Administration',
        'description': 'Managing databases and SQL queries.',
    },
    {
        'slug': 'it-support',
        'code': 'IT_SUPPORT',
        'name': 'IT Support',
        'description': 'Solving technical issues and maintaining systems.',
    },
)

DEPARTMENT_COUNT = len(DEPARTMENTS)

HOMEPAGE_DEPARTMENT_NAMES = {
    'hr': 'HR',
    'development': 'Development',
    'testing-qa': 'Testing',
    'database-administration': 'Database Administration',
    'it-support': 'IT Support',
}


def _department_employees_query():
    return Employee.objects.all()


def _department_cards():
    eligible_employees = _department_employees_query()

    aggregation_kwargs = {}
    for idx, dept in enumerate(DEPARTMENTS):
        aggregation_kwargs[f'dept_{idx}'] = Count(
            'pk',
            filter=department_assignment_filter(dept['code']),
            distinct=True,
        )

    counts = eligible_employees.aggregate(**aggregation_kwargs)

    return [
        {
            **dept,
            'employee_count': counts.get(f'dept_{idx}', 0),
        }
        for idx, dept in enumerate(DEPARTMENTS)
    ]


def get_current_employee(request):
    employee_id = request.session.get(EMPLOYEE_SESSION_KEY)
    if not employee_id:
        return None

    return Employee.objects.filter(pk=employee_id).first()


def _is_admin(employee):
    return (employee.account_type or '').upper() == 'ADMIN'


def _is_manager(employee):
    return (employee.account_type or '').upper() == 'MANAGER'


def _is_hr(employee):
    return (employee.account_type or '').upper() == 'HR'


def _employee_dashboard(employee):
    if _is_admin(employee):
        return 'profile'
    if _is_manager(employee):
        return 'manager_dashboard'
    if _is_hr(employee):
        return 'hr_dashboard'
    return 'profile'


def home(request):
    employee_count = _department_employees_query().count()
    departments = [
        {
            'slug': department['slug'],
            'name': HOMEPAGE_DEPARTMENT_NAMES[department['slug']],
            'employee_count': department['employee_count'],
        }
        for department in _department_cards()
    ]
    assigned_employee_count = sum(
        department['employee_count'] for department in departments
    )
    return render(
        request,
        'home.html',
        {
            'employee_count': employee_count,
            'department_count': len(departments),
            'departments': departments,
            'department_employee_total': assigned_employee_count,
            'unassigned_employee_count': (
                employee_count - assigned_employee_count
            ),
        },
    )


def department_detail(request, department_slug):
    slug_normalized = (department_slug or '').strip().lower()
    department = next(
        (
            department
            for department in DEPARTMENTS
            if department['slug'] == slug_normalized
            or department.get('code', '').lower() == slug_normalized
            or (slug_normalized in ('testing', 'testing-qa') and department['slug'] == 'testing-qa')
        ),
        None,
    )
    if department is None:
        raise Http404('Department not found.')

    employees = (
        _department_employees_query()
        .filter(department_assignment_filter(department['code']))
        .distinct()
        .order_by('full_name', 'employee_id')
    )
    employees = list(employees)

    return render(
        request,
        'department_detail.html',
        {
            'department': department,
            'employees': employees,
            'employee_count': len(employees),
            'departments': DEPARTMENTS,
        },
    )


def login(request):
    error = None
    if request.method == 'POST':
        login_id = request.POST.get('login_id', '').strip()
        password = request.POST.get('password', '')
        employee = Employee.objects.filter(
            Q(employee_id__iexact=login_id)
            | Q(username__iexact=login_id)
            | Q(email__iexact=login_id)
        ).first()

        if employee and check_password(password, employee.password):
            request.session.cycle_key()
            request.session.pop('administration_admin_id', None)
            request.session.pop('admin_selected_employee_id', None)
            request.session[EMPLOYEE_SESSION_KEY] = employee.pk
            return redirect(_employee_dashboard(employee))

        error = 'Incorrect Employee ID, username or password.'

    return render(request, 'login.html', {'error': error})


def register(request):
    if request.method == 'POST':
        form = EmployeeRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            employee = form.save(commit=False)
            try:
                validate_password(form.cleaned_data['password'], employee)
            except ValidationError as error:
                form.add_error('password', error)
            else:
                employee.password = make_password(
                    form.cleaned_data['password']
                )
                employee.account_type = 'EMPLOYEE'
                employee.save()
                messages.success(
                    request,
                    'Your account was created. You can now sign in.',
                )
                return redirect('login')
    else:
        form = EmployeeRegistrationForm()

    return render(request, 'register.html', {'form': form})


def logout(request):
    request.session.pop(EMPLOYEE_SESSION_KEY, None)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


def profile(request):
    employee = get_current_employee(request)
    if not employee:
        return redirect('login')
    return render(request, 'profile.html', {'employee': employee})


def manager_dashboard(request):
    manager = get_current_employee(request)
    if not manager or not _is_manager(manager):
        messages.error(request, 'Manager access is required.')
        return redirect('login')

    employees = Employee.objects.order_by('full_name')
    context = {
        'manager': manager,
        'employees': employees,
        'total_accounts': employees.count(),
        'total_employees': employees.filter(
            account_type__iexact='EMPLOYEE'
        ).count(),
        'total_hr': employees.filter(account_type__iexact='HR').count(),
        'total_admins': employees.filter(account_type__iexact='ADMIN').count(),
        'total_departments': DEPARTMENT_COUNT,
    }
    return render(request, 'manager_dashboard.html', context)


def hr_dashboard(request):
    employee = get_current_employee(request)
    if not employee or not _is_hr(employee):
        messages.error(request, 'HR access is required.')
        return redirect('login')

    employee_count = Employee.objects.filter(
        account_type__iexact='EMPLOYEE'
    ).count()
    return render(
        request,
        'hr_dashboard.html',
        {
            'employee': employee,
            'total_employees': employee_count,
            'total_departments': DEPARTMENT_COUNT,
            'active_employees': employee_count,
            'departments': _department_cards(),
        },
    )


def employee_detail(request):
    current_employee = get_current_employee(request)
    if not current_employee:
        return redirect('login')
    if not (_is_manager(current_employee) or _is_hr(current_employee)):
        messages.error(request, 'You do not have permission to search employees.')
        return redirect('profile')

    search_id = request.GET.get('employee_id', '').strip()
    employee = None
    error = None
    if search_id:
        employee = Employee.objects.filter(
            employee_id__iexact=search_id
        ).first()
        if employee is None:
            error = 'No employee was found with that ID.'
        elif _is_hr(current_employee) and (
            employee.account_type or ''
        ).upper() != 'EMPLOYEE':
            employee = None
            error = 'HR can view employee accounts only.'

    return render(
        request,
        'employee_details.html',
        {
            'employee': employee,
            'search_id': search_id,
            'error': error,
            'is_manager': _is_manager(current_employee),
            'manager_id': (
                current_employee.pk
                if _is_manager(current_employee)
                else None
            ),
            'is_hr': _is_hr(current_employee),
        },
    )


def edit_employee(request, id):
    manager = get_current_employee(request)
    if not manager or not _is_manager(manager):
        messages.error(request, 'Manager access is required.')
        return redirect('login')

    employee = get_object_or_404(Employee, pk=id)

    form = ManagerEmployeeEditForm(
        request.POST or None,
        request.FILES or None,
        instance=employee,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Employee details updated successfully.')
        return redirect('manager_dashboard')

    return render(
        request,
        'edit_employee.html',
        {'employee': employee, 'form': form},
    )


@require_POST
def delete_employee(request, employee_id):
    manager = get_current_employee(request)
    if not manager or not _is_manager(manager):
        messages.error(request, 'Manager access is required.')
        return redirect('login')

    employee = get_object_or_404(Employee, employee_id__iexact=employee_id)
    if employee.pk == manager.pk:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('manager_dashboard')

    employee.delete()
    messages.success(request, 'Employee account deleted successfully.')
    return redirect('manager_dashboard')


def hr_edit_employee(request, id):
    hr_employee = get_current_employee(request)
    if not hr_employee or not _is_hr(hr_employee):
        messages.error(request, 'HR access is required.')
        return redirect('login')

    employee = get_object_or_404(
        Employee,
        pk=id,
        account_type__iexact='EMPLOYEE',
    )
    form = EmployeeProfessionalEditForm(
        request.POST or None,
        instance=employee,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Employee details updated successfully.')
        return HttpResponseRedirect(
            f"{reverse('employee_detail')}?"
            f"{urlencode({'employee_id': employee.employee_id})}"
        )

    return render(
        request,
        'hr_edit_employee.html',
        {'employee': employee, 'form': form},
    )


@require_POST
def hr_delete_employee(request, id):
    hr_employee = get_current_employee(request)
    if not hr_employee or not _is_hr(hr_employee):
        messages.error(request, 'HR access is required.')
        return redirect('login')

    employee = get_object_or_404(
        Employee,
        pk=id,
        account_type__iexact='EMPLOYEE',
    )
    employee.delete()
    messages.success(request, 'Employee account deleted successfully.')
    return redirect('hr_dashboard')


def forgot_password(request):
    step = 'email'
    error = None
    success = None

    if request.method == 'GET':
        if request.session.get('password_reset_otp'):
            if _password_reset_is_expired(request):
                _clear_password_reset_session(request)
                error = 'Your reset code expired. Please request a new one.'
            elif request.session.get('password_reset_verified'):
                step = 'reset'
            else:
                step = 'otp'

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'send_otp':
            _clear_password_reset_session(request)
            email = request.POST.get('email', '').strip()
            employee = Employee.objects.filter(
                email__iexact=email
            ).exclude(account_type__iexact='ADMIN').first()
            if not employee:
                error = 'No employee account is registered with that email.'
            elif not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
                error = (
                    'Email sending is not configured. Set the '
                    'DJANGO_GMAIL_ADDRESS and DJANGO_GMAIL_APP_PASSWORD '
                    'environment variables, then try again.'
                )
            else:
                otp = f'{secrets.randbelow(900000) + 100000:06d}'
                try:
                    sent_count = send_mail(
                        'Employee Management password reset code',
                        f'Your password reset code is {otp}. It expires in 10 minutes.',
                        settings.DEFAULT_FROM_EMAIL,
                        [employee.email],
                        fail_silently=False,
                    )
                except (BadHeaderError, OSError, SMTPException) as mail_error:
                    logger.exception('Could not send password reset code.')
                    error = _password_reset_send_error(mail_error)
                else:
                    if sent_count:
                        request.session['password_reset_email'] = employee.email
                        request.session['password_reset_otp'] = make_password(otp)
                        request.session['password_reset_expires'] = (
                            timezone.now() + PASSWORD_RESET_TTL
                        ).isoformat()
                        request.session['password_reset_verified'] = False
                        request.session['password_reset_attempts'] = 0
                        step = 'otp'
                        success = 'A reset code has been sent to your email.'
                    else:
                        error = (
                            'We could not send the reset code. Please check '
                            'the email configuration and try again.'
                        )
        elif action == 'verify_otp':
            otp_hash = request.session.get('password_reset_otp')
            if (
                not otp_hash
                or _password_reset_is_expired(request)
            ):
                error = 'Your reset code expired. Please request a new one.'
                _clear_password_reset_session(request)
            elif (
                request.session.get('password_reset_attempts', 0)
                >= PASSWORD_RESET_MAX_ATTEMPTS
            ):
                error = 'Too many incorrect codes. Please request a new one.'
                _clear_password_reset_session(request)
            elif check_password(request.POST.get('otp', ''), otp_hash):
                request.session['password_reset_verified'] = True
                step = 'reset'
            else:
                attempts = request.session.get('password_reset_attempts', 0) + 1
                if attempts >= PASSWORD_RESET_MAX_ATTEMPTS:
                    error = 'Too many incorrect codes. Please request a new one.'
                    _clear_password_reset_session(request)
                else:
                    request.session['password_reset_attempts'] = attempts
                    error = 'The reset code is incorrect.'
                    step = 'otp'
        elif action == 'reset_password':
            if not request.session.get('password_reset_verified'):
                error = 'Verify your reset code before changing your password.'
                step = (
                    'otp'
                    if request.session.get('password_reset_otp')
                    else 'email'
                )
            elif _password_reset_is_expired(request):
                error = 'Your reset code expired. Please request a new one.'
                _clear_password_reset_session(request)
                step = 'email'
            else:
                password = request.POST.get('password', '')
                confirm_password = request.POST.get('confirm_password', '')
                if password != confirm_password:
                    error = 'Passwords do not match.'
                    step = 'reset'
                else:
                    employee = Employee.objects.filter(
                        email__iexact=request.session.get(
                            'password_reset_email', ''
                        )
                    ).exclude(account_type__iexact='ADMIN').first()
                    if not employee:
                        error = 'The account could not be found.'
                        _clear_password_reset_session(request)
                    else:
                        try:
                            validate_password(password, employee)
                        except ValidationError as password_error:
                            error = ' '.join(password_error.messages)
                            step = 'reset'
                        else:
                            employee.password = make_password(password)
                            employee.save(update_fields=['password'])
                            _clear_password_reset_session(request)
                            return render(
                                request,
                                'forgot_password.html',
                                {
                                    'step': 'email',
                                    'success': (
                                        'Password changed. You can now log in.'
                                    ),
                                },
                            )
        else:
            error = 'Please restart the password reset process.'

    return render(
        request,
        'forgot_password.html',
        {'step': step, 'error': error, 'success': success},
    )


def _password_reset_send_error(mail_error):
    detail = str(mail_error)
    gmail_rejected_login = (
        isinstance(mail_error, SMTPServerDisconnected)
        or 'BadCredentials' in detail
        or 'Username and Password not accepted' in detail
        or '5.7.8' in detail
        or 'Application-specific password' in detail
        or '534' in detail
    )
    if gmail_rejected_login:
        return (
            'Gmail refused the login, so the OTP was not sent. '
            'DJANGO_GMAIL_APP_PASSWORD must be a 16-character Gmail App Password. '
            'The normal Gmail password cannot send this mail. '
            'Create an App Password in your Google Account under Security, '
            'update that setting, and restart the server.'
        )
    return (
        'We could not send the reset code. Please check the '
        'email configuration and try again.'
    )


def _password_reset_is_expired(request):
    expires = request.session.get('password_reset_expires')
    expires_at = parse_datetime(expires) if expires else None
    if expires_at is None:
        return True
    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(
            expires_at,
            timezone.get_current_timezone(),
        )
    return timezone.now() >= expires_at


def _clear_password_reset_session(request):
    for key in (
        'password_reset_email',
        'password_reset_otp',
        'password_reset_expires',
        'password_reset_verified',
        'password_reset_attempts',
    ):
        request.session.pop(key, None)
