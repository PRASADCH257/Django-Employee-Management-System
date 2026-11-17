
import re
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404

from django.contrib import messages

from django.contrib.auth.hashers import (
    make_password,
    check_password
)

from django.views.decorators.http import require_POST

from home.models import Employee, EmployeeIdConfiguration
from home.forms import AdminEmployeeEditForm

DEPARTMENT_COUNT = 5


# ==========================================
# CHECK ADMIN LOGIN SESSION
# ==========================================

def get_admin(request):

    admin_id = request.session.get(
        'administration_admin_id'
    )

    if not admin_id:
        return None

    return Employee.objects.filter(
        account_type__iexact='ADMIN',
        pk=admin_id,
    ).first()


# ==========================================
# EMPLOYEE COUNT
# ==========================================

def get_employee_count():
    return Employee.objects.count()


def _is_manager_account(employee):
    return (employee.account_type or '').strip().upper() == 'MANAGER'


def _get_verified_employee(request, employee_id):
    selected_employee_id = request.session.get(
        'admin_selected_employee_id'
    )
    if str(selected_employee_id) != str(employee_id):
        return None

    return Employee.objects.filter(pk=employee_id).first()


# ==========================================
# ADMIN LOGIN
# ==========================================

def admin_login(request):
    request.session.pop('administration_admin_id', None)
    request.session.pop('admin_selected_employee_id', None)

    error = None

    if request.method == 'POST':

        username = request.POST.get(
            'username', ''
        ).strip()

        password = request.POST.get(
            'password', ''
        )

        admin = Employee.objects.filter(
            username__iexact=username,
            account_type__iexact='ADMIN',
        ).first()

        if admin and check_password(
            password,
            admin.password
        ):
            # Change session key without deleting
            # other application session information
            request.session.cycle_key()

            request.session.pop('home_employee_id', None)
            request.session.pop('admin_selected_employee_id', None)
            request.session[
                'administration_admin_id'
            ] = admin.pk

            return redirect('administration:admin_dashboard')

        error = 'Incorrect username or password.'

    return render(
        request,
        'administration/login.html',
        {
            'error': error
        }
    )


# ==========================================
# ADMIN DASHBOARD
# ==========================================

def admin_dashboard(request):

    admin = get_admin(request)

    if not admin:

        request.session.pop(
            'administration_admin_id',
            None
        )

        return redirect('administration:admin_login')

    current_year = date.today().year
    year_configuration, _ = EmployeeIdConfiguration.objects.get_or_create(
        pk=1,
        defaults={'year': current_year},
    )
    available_years = list(range(current_year - 5, current_year + 6))

    if request.method == 'POST':
        admin_password = request.POST.get('admin_password', '')
        submitted_year = request.POST.get('year', '')

        if not check_password(admin_password, admin.password):
            messages.error(request, 'Incorrect Administration password.')
            return redirect('administration:admin_dashboard')

        try:
            selected_year = int(submitted_year)
        except (TypeError, ValueError):
            selected_year = None

        if selected_year not in available_years:
            messages.error(request, 'Select a valid dashboard year.')
            return redirect('administration:admin_dashboard')

        year_configuration.year = selected_year
        year_configuration.save(update_fields=['year'])
        messages.success(
            request,
            f'Dashboard year changed to {selected_year}.',
        )
        return redirect('administration:admin_dashboard')

    # Get previously searched employee
    selected_employee_id = request.session.get(
        'admin_selected_employee_id'
    )

    employee = None

    if selected_employee_id:

        employee = Employee.objects.filter(
            pk=selected_employee_id
        ).first()

        if not employee:
            request.session.pop(
                'admin_selected_employee_id',
                None
            )

    dashboard_year = year_configuration.year
    if dashboard_year not in available_years:
        dashboard_year = current_year
        year_configuration.year = current_year
        year_configuration.save(update_fields=['year'])

    context = {
        'admin': admin,
        'employee_count': get_employee_count(),
        'department_count': DEPARTMENT_COUNT,
        'employee': employee,
        'dashboard_year': dashboard_year,
        'available_years': available_years,
    }

    return render(
        request,
        'administration/admin_dashboard.html',
        context
    )


# ==========================================
# SEARCH EMPLOYEE
# ==========================================

def search_employee(request):

    admin = get_admin(request)

    if not admin:
        return redirect('administration:admin_login')

    if request.method != 'POST':
        return redirect('administration:admin_dashboard')

    # Clear previous search result
    request.session.pop(
        'admin_selected_employee_id',
        None
    )

    employee_id = request.POST.get(
        'employee_id', ''
    ).strip()

    admin_password = request.POST.get('admin_password', '')
    manager_password = request.POST.get('manager_password', '')
    manager_verification = request.POST.get('manager_verification') == 'yes'

    if not employee_id:

        messages.error(
            request,
            'Please enter an Employee ID.'
        )

        return redirect('administration:admin_dashboard')

    # Find employee
    employee = Employee.objects.filter(
        employee_id__iexact=employee_id
    ).first()

    if not employee:

        messages.error(
            request,
            'Employee ID not found.'
        )

        return redirect('administration:admin_dashboard')

    if not admin_password:
        messages.error(
            request,
            'Enter your Administration password to continue.',
        )
        return redirect('administration:admin_dashboard')

    if not check_password(admin_password, admin.password):
        messages.error(
            request,
            'Incorrect Administration password.',
        )
        return redirect('administration:admin_dashboard')

    is_manager_account = _is_manager_account(employee)
    if is_manager_account and not manager_verification:

        messages.error(
            request,
            'Select the Manager verification checkbox to continue.',
        )
        return redirect('administration:admin_dashboard')

    if not is_manager_account and manager_verification:
        messages.error(
            request,
            'Manager verification is only for Manager accounts.',
        )
        return redirect('administration:admin_dashboard')

    if is_manager_account:
        if not manager_password:
            messages.error(
                request,
                'Enter the Manager password to continue.',
            )
            return redirect('administration:admin_dashboard')
        if not check_password(manager_password, employee.password):
            messages.error(
                request,
                'Incorrect Manager password.',
            )
            return redirect('administration:admin_dashboard')

    # Save selected employee
    request.session[
        'admin_selected_employee_id'
    ] = employee.pk

    messages.success(
        request,
        'Employee details found successfully.'
    )

    # Open employee details page
    return redirect('administration:admin_employee_details')


# ==========================================
# EMPLOYEE DETAILS
# ==========================================

def admin_employee_details(request):

    admin = get_admin(request)

    if not admin:
        return redirect('administration:admin_login')

    employee_id = request.session.get(
        'admin_selected_employee_id'
    )

    if not employee_id:

        messages.error(
            request,
            'Please search for an employee first.'
        )

        return redirect('administration:admin_dashboard')

    employee = _get_verified_employee(request, employee_id)
    if not employee:
        request.session.pop('admin_selected_employee_id', None)
        messages.error(request, 'Search and verify this account first.')
        return redirect('administration:admin_dashboard')

    return render(
        request,
        'administration/employee_details.html',
        {
            'admin': admin,
            'employee': employee,
        }
    )


# ==========================================
# EDIT EMPLOYEE
# ==========================================

def admin_edit_employee(request, id):

    admin = get_admin(request)

    if not admin:
        return redirect('administration:admin_login')

    employee = _get_verified_employee(request, id)
    if not employee:
        messages.error(request, 'Search and verify this account before editing.')
        return redirect('administration:admin_dashboard')

    if request.method == 'POST':

        form = AdminEmployeeEditForm(
            request.POST,
            request.FILES,
            instance=employee
        )
        if employee.pk == admin.pk:
            form.fields['employee_id'].disabled = True

        if form.is_valid():

            form.save()

            request.session[
                'admin_selected_employee_id'
            ] = employee.pk

            messages.success(
                request,
                'Employee details updated successfully.'
            )

            return redirect('administration:admin_employee_details')

        messages.error(
            request,
            'Please correct the errors in the form.'
        )

    else:

        form = AdminEmployeeEditForm(
            instance=employee
        )
        if employee.pk == admin.pk:
            form.fields['employee_id'].disabled = True

    return render(
        request,
        'administration/edit_employee.html',
        {
            'admin': admin,
            'employee': employee,
            'form': form,
        }
    )


# ==========================================
# DELETE EMPLOYEE
# ==========================================

@require_POST
def admin_delete_employee(request, id):

    admin = get_admin(request)

    if not admin:
        return redirect('administration:admin_login')

    employee = _get_verified_employee(request, id)
    if not employee:
        messages.error(request, 'Search and verify this account before deleting.')
        return redirect('administration:admin_dashboard')

    # Admin cannot delete their own account
    if employee.pk == admin.pk:

        messages.error(
            request,
            'You cannot delete your own Admin account.'
        )

        return redirect('administration:admin_dashboard')

    employee.delete()

    # Clear selected employee
    request.session.pop(
        'admin_selected_employee_id',
        None
    )

    messages.success(
        request,
        'Employee deleted successfully.'
    )

    return redirect('administration:admin_dashboard')


# ==========================================
# SET UP MANAGER ACCOUNT
# ==========================================

def admin_setup_manager(request):

    admin = get_admin(request)

    if not admin:
        return redirect('administration:admin_login')

    error = None

    if request.method == 'POST':

        employee_id = request.POST.get(
            'employee_id', ''
        ).strip()

        if employee_id:
            employee = Employee.objects.filter(
                employee_id__iexact=employee_id
            ).first()

            if not employee:
                error = 'No employee was found with that Employee ID.'
            elif (employee.account_type or '').strip().upper() != 'EMPLOYEE':
                error = 'Only a normal employee account can be promoted.'
            else:
                id_match = re.fullmatch(
                    r'(\d{2}MQ1)A(0\d+)',
                    employee.employee_id.upper(),
                )

                if not id_match:
                    error = (
                        'This employee ID cannot be converted to a manager ID.'
                    )
                else:
                    manager_id = (
                        f'{id_match.group(1)}G{id_match.group(2)}'
                    )
                    manager_id_exists = Employee.objects.filter(
                        employee_id__iexact=manager_id
                    ).exclude(pk=employee.pk).exists()

                    if manager_id_exists:
                        error = (
                            'The matching manager ID is already in use, '
                            'so this employee cannot be promoted.'
                        )
                    else:
                        employee.employee_id = manager_id
                        employee.account_type = 'MANAGER'
                        employee.save(update_fields=[
                            'employee_id',
                            'account_type',
                        ])
                        messages.success(
                            request,
                            f'{employee.full_name} was promoted to Manager. '
                            f'Employee ID changed to {manager_id}.',
                        )
                        return redirect(
                            'administration:admin_dashboard'
                        )

            return render(
                request,
                'setup_manager.html',
                {
                    'admin': admin,
                    'error': error,
                    'employee_id': employee_id,
                }
            )

        full_name = request.POST.get(
            'full_name', ''
        ).strip()

        username = request.POST.get(
            'username', ''
        ).strip()

        email = request.POST.get(
            'email', ''
        ).strip()

        phone = request.POST.get(
            'phone', ''
        ).strip()

        address = request.POST.get(
            'address', ''
        ).strip()

        password = request.POST.get(
            'password', ''
        )

        confirm_password = request.POST.get(
            'confirm_password', ''
        )

        # Check required fields
        if not all([
            full_name,
            username,
            email,
            phone,
            address,
            password,
            confirm_password
        ]):

            error = 'Please fill in all required fields.'

        # Check password
        elif password != confirm_password:

            error = 'Passwords do not match.'

        # Check username
        elif Employee.objects.filter(
            username__iexact=username
        ).exists():

            error = 'Username already exists.'

        # Check email
        elif Employee.objects.filter(
            email__iexact=email
        ).exists():

            error = 'Email already exists.'

        else:

            # Create Manager account
            Employee.objects.create(
                full_name=full_name,
                username=username,
                email=email,
                phone=phone,
                address=address,
                password=make_password(password),
                account_type='MANAGER',
            )

            messages.success(
                request,
                'Manager account created successfully.'
            )

            return redirect('administration:admin_dashboard')

    return render(
        request,
        'setup_manager.html',
        {
            'admin': admin,
            'error': error,
            'employee_id': request.POST.get('employee_id', '').strip(),
        }
    )


# ==========================================
# ADMIN LOGOUT
# ==========================================

def admin_logout(request):

    request.session.pop(
        'administration_admin_id',
        None
    )

    request.session.pop(
        'admin_selected_employee_id',
        None
    )

    messages.success(
        request,
        'Logged out successfully.'
    )

    return redirect('administration:admin_login')
