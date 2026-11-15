from datetime import date, timedelta
from io import BytesIO
import re
from smtplib import SMTPServerDisconnected
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.files.base import ContentFile
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Employee, EmployeeIdConfiguration


class EmployeePortalTests(TestCase):
    def test_public_page_routes_are_available(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('login'))
        self.assertContains(response, reverse('register'))
        self.assertContains(
            response,
            reverse('administration:admin_login'),
        )
        self.assertNotContains(response, 'Our Departments')
        self.assertContains(response, 'class="department-wrapper"')
        self.assertContains(response, 'class="stat-card department-card"')
        self.assertContains(response, 'class="department-dropdown"')
        self.assertNotContains(response, '<details')
        for department_name in (
            'HR',
            'Development',
            'Testing',
            'Database Administration',
            'IT Support',
        ):
            self.assertContains(response, department_name)
        self.assertNotContains(response, 'HR (Human Resources)')
        self.assertNotContains(response, 'Testing / QA')
        self.assertNotContains(
            response,
            'Hiring employees, managing salaries and attendance.',
        )
        for department_slug in (
            'hr',
            'development',
            'testing-qa',
            'database-administration',
            'it-support',
        ):
            self.assertContains(
                response,
                reverse('department_detail', args=[department_slug]),
            )

    def test_department_detail_lists_only_assigned_employees(self):
        development_employee = Employee.objects.create(
            full_name='Development Team Member',
            username='developmentmember',
            email='developmentmember@example.com',
            password='employee-password',
            phone='1234567890',
            address='Employee address',
            role='Developer',
            department='DEVELOPMENT',
        )
        Employee.objects.create(
            full_name='QA Team Member',
            username='qatmember',
            email='qatmember@example.com',
            password='employee-password',
            phone='1234567891',
            address='Employee address',
            department='TESTING_QA',
        )

        department_response = self.client.get(
            reverse('department_detail', args=['development'])
        )
        self.assertEqual(department_response.status_code, 200)
        self.assertContains(department_response, development_employee.employee_id)
        self.assertContains(department_response, 'Development Team Member')
        self.assertNotContains(department_response, 'QA Team Member')
        self.assertEqual(department_response.context['employee_count'], 1)

    def test_department_detail_returns_not_found_for_unknown_department(self):
        response = self.client.get(
            reverse('department_detail', args=['unknown'])
        )
        self.assertEqual(response.status_code, 404)

    def test_hr_dashboard_department_stat_opens_department_cards(self):
        hr_employee = Employee.objects.create(
            full_name='HR Dashboard User',
            username='hrdashboarduser',
            email='hrdashboarduser@example.com',
            password='employee-password',
            phone='1234567890',
            address='HR address',
            account_type='HR',
            role='HR',
            department='HR',
        )
        Employee.objects.create(
            full_name='Department Team Member',
            username='departmentmember',
            email='departmentmember@example.com',
            password='employee-password',
            phone='1234567891',
            address='Employee address',
            role='Developer',
            department='DEVELOPMENT',
        )
        session = self.client.session
        session['home_employee_id'] = hr_employee.pk
        session.save()

        response = self.client.get(reverse('hr_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="#departments"')
        for department_name in (
            'HR (Human Resources)',
            'Development',
            'Testing',
            'Database Administration',
            'IT Support',
        ):
            self.assertContains(response, department_name)
        self.assertNotContains(
            response,
            'Hiring employees, managing salaries and attendance.',
        )
        self.assertNotContains(response, 'department-section')
        self.assertEqual(
            {
                department['code']: department['employee_count']
                for department in response.context['departments']
            },
            {
                'HR': 0,
                'DEVELOPMENT': 1,
                'TESTING_QA': 0,
                'DATABASE_ADMINISTRATION': 0,
                'IT_SUPPORT': 0,
            },
        )

    def test_home_displays_employee_count_and_fixed_department_count(self):
        Employee.objects.create(
            full_name='Public Count Employee',
            username='publiccount',
            email='publiccount@example.com',
            password=make_password('A-unique-password-482!'),
            phone='1234567890',
            address='Test address',
        )

        response = self.client.get(reverse('home'))

        self.assertContains(response, '<h2>1</h2>', html=True)
        self.assertContains(response, '<h2>5</h2>', html=True)
        self.assertEqual(response.context['department_employee_total'], 0)
        self.assertEqual(response.context['unassigned_employee_count'], 1)
        self.assertTrue(
            all(
                department['employee_count'] == 0
                for department in response.context['departments']
            )
        )
        self.assertContains(response, '0 Employees')
        self.assertContains(response, 'Unassigned Employees')
        self.assertContains(response, '<span>1 Employee</span>', html=True)

    def test_home_department_dropdown_shows_employee_counts_and_total(self):
        employee_data = {
            'password': 'employee-password',
            'phone': '1234567890',
            'address': 'Test address',
            'role': 'Employee',
        }
        Employee.objects.create(
            full_name='HR Employee',
            username='count_hr_employee',
            email='count_hr_employee@example.com',
            department='HR',
            **employee_data,
        )
        for suffix in ('one', 'two'):
            Employee.objects.create(
                full_name=f'Development Employee {suffix}',
                username=f'count_development_{suffix}',
                email=f'count_development_{suffix}@example.com',
                department='DEVELOPMENT',
                **employee_data,
            )
        Employee.objects.create(
            full_name='Testing Employee',
            username='count_testing_employee',
            email='count_testing_employee@example.com',
            department='TESTING_QA',
            **employee_data,
        )
        Employee.objects.create(
            full_name='Database Employee',
            username='count_database_employee',
            email='count_database_employee@example.com',
            department='DATABASE_ADMINISTRATION',
            **employee_data,
        )
        Employee.objects.create(
            full_name='IT Employee',
            username='count_it_employee',
            email='count_it_employee@example.com',
            department='IT_SUPPORT',
            **employee_data,
        )
        Employee.objects.create(
            full_name='Position Only Employee',
            username='count_position_only',
            email='count_position_only@example.com',
            **{**employee_data, 'role': 'Python Developer'},
        )
        Employee.objects.create(
            full_name='HR Staff Account',
            username='count_hr_staff',
            email='count_hr_staff@example.com',
            account_type='HR',
            department='HR',
            **employee_data,
        )
        Employee.objects.create(
            full_name='Manager Account',
            username='count_manager',
            email='count_manager@example.com',
            account_type='MANAGER',
            department='DATABASE_ADMINISTRATION',
            **employee_data,
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['department_count'], 5)
        self.assertEqual(response.context['department_employee_total'], 7)
        self.assertEqual(response.context['unassigned_employee_count'], 0)
        self.assertEqual(
            {
                department['name']: department['employee_count']
                for department in response.context['departments']
            },
            {
                'HR': 1,
                'Development': 3,
                'Testing': 1,
                'Database Administration': 1,
                'IT Support': 1,
            },
        )
        self.assertContains(response, '1 Employee')
        self.assertContains(response, '3 Employees')
        self.assertContains(response, '<span>7</span>', html=True)
        self.assertContains(response, 'Total Assigned Employees')

    def test_role_infers_department_only_when_department_is_blank(self):
        developer = Employee.objects.create(
            full_name='Role Inferred Developer',
            username='roleinferreddeveloper',
            email='roleinferreddeveloper@example.com',
            password='employee-password',
            phone='1234567890',
            address='Employee address',
            role='Software Engineer',
        )
        Employee.objects.create(
            full_name='Unmatched Role Employee',
            username='unmatchedroleemployee',
            email='unmatchedroleemployee@example.com',
            password='employee-password',
            phone='1234567891',
            address='Employee address',
            role='Operations Specialist',
        )
        Employee.objects.create(
            full_name='Explicit Department Employee',
            username='explicitdepartmentemployee',
            email='explicitdepartmentemployee@example.com',
            password='employee-password',
            phone='1234567892',
            address='Employee address',
            role='Support Specialist',
            department='HR',
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.context['employee_count'], 3)
        self.assertEqual(response.context['department_employee_total'], 2)
        self.assertEqual(response.context['unassigned_employee_count'], 1)
        counts = {
            department['name']: department['employee_count']
            for department in response.context['departments']
        }
        self.assertEqual(counts['Development'], 1)
        self.assertEqual(counts['HR'], 1)

        detail_response = self.client.get(
            reverse('department_detail', args=['development'])
        )
        self.assertEqual(detail_response.context['employee_count'], 1)
        self.assertContains(detail_response, developer.full_name)

    def test_role_and_department_changes_recalculate_counts_and_delete(self):
        employee = Employee.objects.create(
            full_name='Changing Assignment Employee',
            username='changingassignmentemployee',
            email='changingassignmentemployee@example.com',
            password='employee-password',
            phone='1234567890',
            address='Employee address',
            role='Python Developer',
        )

        def assert_assignment(department_counts, total, assigned, unassigned):
            response = self.client.get(reverse('home'))
            counts = {
                department['name']: department['employee_count']
                for department in response.context['departments']
            }
            self.assertEqual(counts, department_counts)
            self.assertEqual(response.context['employee_count'], total)
            self.assertEqual(
                response.context['department_employee_total'],
                assigned,
            )
            self.assertEqual(
                response.context['unassigned_employee_count'],
                unassigned,
            )
            self.assertEqual(total, assigned + unassigned)

        empty_counts = {
            'HR': 0,
            'Development': 0,
            'Testing': 0,
            'Database Administration': 0,
            'IT Support': 0,
        }
        assert_assignment(
            {**empty_counts, 'Development': 1},
            1,
            1,
            0,
        )

        employee.role = 'Tester'
        employee.save(update_fields=['role'])
        assert_assignment({**empty_counts, 'Testing': 1}, 1, 1, 0)

        employee.department = 'HR'
        employee.save(update_fields=['department'])
        assert_assignment({**empty_counts, 'HR': 1}, 1, 1, 0)

        employee.role = 'Operations Specialist'
        employee.save(update_fields=['role'])
        assert_assignment({**empty_counts, 'HR': 1}, 1, 1, 0)

        employee.department = ''
        employee.save(update_fields=['department'])
        assert_assignment(empty_counts, 1, 0, 1)

        employee.role = 'HR'
        employee.save(update_fields=['role'])
        assert_assignment({**empty_counts, 'HR': 1}, 1, 1, 0)

        employee.role = ''
        employee.save(update_fields=['role'])
        assert_assignment(empty_counts, 1, 0, 1)

        employee.delete()
        assert_assignment(empty_counts, 0, 0, 0)

    def test_exact_role_mapping_and_account_type_exclusions(self):
        role_mapping = {
            'HR': ('HR', 'HR Executive', 'HR Officer'),
            'DEVELOPMENT': (
                'Developer',
                'Python Developer',
                'Software Developer',
                'Backend Developer',
                'Frontend Developer',
                'Full Stack Developer',
                'Software Engineer',
            ),
            'TESTING_QA': (
                'Tester',
                'QA',
                'QA Engineer',
                'Software Tester',
                'Test Engineer',
            ),
            'DATABASE_ADMINISTRATION': (
                'Admin',
                'DBA',
                'Database Administrator',
                'Database Administration',
                'SQL Developer',
                'Database Engineer',
                'Database Admin',
                'DB Admin',
                'DB Administrator',
            ),
            'IT_SUPPORT': (
                'IT Support',
                'IT Technician',
                'Technical Support',
                'System Administrator',
            ),
        }
        base_kwargs = {
            'password': 'employee-password',
            'phone': '1234567890',
            'address': 'Employee address',
        }
        role_index = 0
        for role, department_code in role_mapping.items():
            for title in department_code:
                role_value = title
                if title == 'Admin':
                    role_value = 'ADMIN'
                elif title == 'DB Admin':
                    role_value = '  dB   AdMiN  '
                employee = Employee.objects.create(
                    full_name=f'Role Mapping Employee {role_index}',
                    username=f'role_mapping_{role_index}',
                    email=f'role_mapping_{role_index}@example.com',
                    role=role_value,
                    **base_kwargs,
                )
                if title == 'Admin':
                    database_admin_employee = employee
                role_index += 1

        explicit_department_employee = Employee.objects.create(
            full_name='Explicit Department Wins',
            username='explicitdepartmentwins',
            email='explicitdepartmentwins@example.com',
            role='ADMIN',
            department='HR',
            **base_kwargs,
        )
        department_only_employee = Employee.objects.create(
            full_name='Department Without Role',
            username='departmentwithoutrole',
            email='departmentwithoutrole@example.com',
            department='TESTING_QA',
            **base_kwargs,
        )
        Employee.objects.create(
            full_name='Unrecognized Role',
            username='unrecognizedrole',
            email='unrecognizedrole@example.com',
            role='Operations Specialist',
            **base_kwargs,
        )
        Employee.objects.create(
            full_name='No Role Or Department',
            username='noroleordepartment',
            email='noroleordepartment@example.com',
            **base_kwargs,
        )
        for account_type in ('HR', 'ADMIN', 'MANAGER'):
            Employee.objects.create(
                full_name=f'{account_type} Account',
                username=f'{account_type.lower()}_excluded',
                email=f'{account_type.lower()}_excluded@example.com',
                role=(
                    'ADMIN' if account_type == 'ADMIN'
                    else 'Python Developer'
                ),
                department=(
                    '' if account_type == 'ADMIN' else 'DEVELOPMENT'
                ),
                account_type=account_type,
                **base_kwargs,
            )

        response = self.client.get(reverse('home'))
        counts = {
            department['name']: department['employee_count']
            for department in response.context['departments']
        }
        self.assertEqual(response.context['employee_count'], 32)
        self.assertEqual(counts, {
            'HR': 4,
            'Development': 7,
            'Testing': 6,
            'Database Administration': 9,
            'IT Support': 4,
        })
        self.assertEqual(response.context['department_employee_total'], 30)
        self.assertEqual(response.context['unassigned_employee_count'], 2)
        self.assertEqual(
            response.context['employee_count'],
            response.context['department_employee_total']
            + response.context['unassigned_employee_count'],
        )
        self.assertTrue(explicit_department_employee.is_department_counted)

        human_resources_page = self.client.get(
            reverse('department_detail', args=['hr'])
        )
        self.assertContains(
            human_resources_page,
            explicit_department_employee.full_name,
        )
        database_page = self.client.get(
            reverse('department_detail', args=['database-administration'])
        )
        self.assertContains(database_page, database_admin_employee.full_name)
        self.assertNotContains(
            database_page,
            explicit_department_employee.full_name,
        )
        self.assertNotContains(database_page, 'HR Account')
        self.assertNotContains(database_page, 'ADMIN Account')
        self.assertNotContains(database_page, 'MANAGER Account')
        testing_page = self.client.get(
            reverse('department_detail', args=['testing'])
        )
        self.assertContains(testing_page, department_only_employee.full_name)
        self.assertNotContains(testing_page, 'Unrecognized Role')

    def test_manager_ids_use_manager_prefix_and_sequence_from_101(self):
        manager = Employee.objects.create(
            full_name='First New Manager',
            username='firstnewmanager',
            email='firstnewmanager@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        second_manager = Employee.objects.create(
            full_name='Second New Manager',
            username='secondnewmanager',
            email='secondnewmanager@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567891',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )

        year_prefix = f'{date.today().year % 100:02d}MQ1G0'
        self.assertEqual(manager.employee_id, f'{year_prefix}101')
        self.assertEqual(second_manager.employee_id, f'{year_prefix}102')

    def test_new_employee_ids_use_employee_prefix_from_101(self):
        employee = Employee.objects.create(
            full_name='First New Employee',
            username='firstnewemployee',
            email='firstnewemployee@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        second_employee = Employee.objects.create(
            full_name='Second New Employee',
            username='secondnewemployee',
            email='secondnewemployee@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567891',
            address='Employee address',
            account_type='EMPLOYEE',
        )

        year_prefix = f'{date.today().year % 100:02d}MQ1A0'
        self.assertEqual(employee.employee_id, f'{year_prefix}101')
        self.assertEqual(second_employee.employee_id, f'{year_prefix}102')

    def test_changing_id_year_changes_only_future_employee_ids(self):
        configuration, _ = EmployeeIdConfiguration.objects.get_or_create(
            pk=1,
            defaults={'year': date.today().year},
        )
        configuration.year = 2022
        configuration.save(update_fields=['year'])
        previous_employee = Employee.objects.create(
            full_name='Existing Year Employee',
            username='existingyearemployee',
            email='existingyear@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        self.assertEqual(previous_employee.employee_id, '22MQ1A0101')

        configuration.year = 2026
        configuration.save(update_fields=['year'])
        new_employee = Employee.objects.create(
            full_name='New Year Employee',
            username='newyearemployee',
            email='newyear@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567891',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        manager = Employee.objects.create(
            full_name='New Year Manager',
            username='newyearmanager',
            email='newyearmanager@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567892',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )

        previous_employee.refresh_from_db()
        self.assertEqual(previous_employee.employee_id, '22MQ1A0101')
        self.assertEqual(new_employee.employee_id, '26MQ1A0101')
        self.assertEqual(manager.employee_id, '26MQ1G0102')

    def test_employee_and_manager_ids_share_one_sequence(self):
        configuration, _ = EmployeeIdConfiguration.objects.get_or_create(
            pk=1,
            defaults={'year': date.today().year},
        )
        configuration.year = 2022
        configuration.save(update_fields=['year'])
        Employee.objects.create(
            employee_id='22MQ1A0504',
            full_name='Existing Sequence Employee',
            username='existingsequenceemployee',
            email='existingsequenceemployee@example.com',
            password='employee-password',
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
        )

        employee = Employee.objects.create(
            full_name='Next Sequence Employee',
            username='nextsequenceemployee',
            email='nextsequenceemployee@example.com',
            password='employee-password',
            phone='1234567891',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        manager = Employee.objects.create(
            full_name='Next Sequence Manager',
            username='nextsequencemanager',
            email='nextsequencemanager@example.com',
            password='manager-password',
            phone='1234567892',
            address='Manager address',
            account_type='MANAGER',
        )

        self.assertEqual(employee.employee_id, '22MQ1A0505')
        self.assertEqual(manager.employee_id, '22MQ1G0506')

    def test_home_never_shows_dashboard_links(self):
        employee = Employee.objects.create(
            full_name='Home Page Employee',
            username='homepageemployee',
            email='homepageemployee@example.com',
            password=make_password('A-unique-password-482!'),
            phone='1234567890',
            address='Employee address',
        )
        session = self.client.session
        session['home_employee_id'] = employee.pk
        session.save()

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'My Dashboard')
        self.assertNotContains(response, 'Open Dashboard')
        self.assertContains(
            response,
            f'href="{reverse("administration:admin_login")}"',
        )

    def test_employee_details_show_separated_personal_and_professional_info(self):
        manager = Employee.objects.create(
            full_name='Details Manager',
            username='detailsmanager',
            email='detailsmanager@example.com',
            password=make_password('A-unique-password-482!'),
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        employee = Employee.objects.create(
            full_name='Details Employee',
            username='detailsemployee',
            email='detailsemployee@example.com',
            password=make_password('A-unique-password-482!'),
            phone='0987654321',
            address='Employee address',
            role='Developer',
            department='DEVELOPMENT',
            current_project='Staff Portal',
            team_number='Team 4',
        )
        session = self.client.session
        session['home_employee_id'] = manager.pk
        session.save()

        response = self.client.get(
            reverse('employee_detail'),
            {'employee_id': employee.employee_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Details Employee')
        self.assertContains(response, 'Personal Details')
        self.assertContains(response, 'Professional Details')
        self.assertContains(response, 'Employee address')
        self.assertContains(response, 'Development')
        self.assertContains(response, 'Staff Portal')

    def test_registration_hashes_password_and_login_opens_profile(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="role"')
        self.assertNotContains(response, 'name="department"')

        response = self.client.post(
            reverse('register'),
            {
                'full_name': 'Test Employee',
                'username': 'testemployee',
                'email': 'employee@example.com',
                'phone': '1234567890',
                'address': 'Test address',
                'role': 'Developer',
                'department': 'DEVELOPMENT',
                'password': 'A-very-unique-password-438!',
                'confirm_password': 'A-very-unique-password-438!',
            },
        )
        self.assertRedirects(response, reverse('login'))
        employee = Employee.objects.get(username='testemployee')
        self.assertEqual(employee.department, '')
        self.assertIsNone(employee.role)
        self.assertEqual(employee.account_type, 'EMPLOYEE')
        self.assertTrue(
            check_password('A-very-unique-password-438!', employee.password)
        )

        response = self.client.post(
            reverse('login'),
            {
                'login_id': employee.employee_id,
                'password': 'A-very-unique-password-438!',
            },
        )
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)

    def test_registration_shows_reason_when_username_is_already_registered(self):
        Employee.objects.create(
            full_name='Existing Employee',
            username='existingemployee',
            email='existing@example.com',
            password=make_password('A-unique-password-482!'),
            phone='1234567890',
            address='Existing address',
        )

        response = self.client.post(
            reverse('register'),
            {
                'full_name': 'New Employee',
                'username': 'ExistingEmployee',
                'email': 'new@example.com',
                'phone': '1234567891',
                'address': 'New address',
                'password': 'A-different-password-482!',
                'confirm_password': 'A-different-password-482!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Username: This username is already registered.')

    def test_registration_shows_password_policy_errors(self):
        response = self.client.post(
            reverse('register'),
            {
                'full_name': 'New Employee',
                'username': 'newemployee',
                'email': 'new@example.com',
                'phone': '1234567891',
                'address': 'New address',
                'password': '123',
                'confirm_password': '123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Password: This password is too short.')
        self.assertFalse(Employee.objects.filter(username='newemployee').exists())

    def test_registration_allows_password_matching_username(self):
        response = self.client.post(
            reverse('register'),
            {
                'full_name': 'Melissa Example',
                'username': 'melissa-2026',
                'email': 'melissa@example.com',
                'phone': '1234567891',
                'address': 'Example address',
                'password': 'melissa-2026',
                'confirm_password': 'melissa-2026',
            },
        )

        self.assertRedirects(response, reverse('login'))
        employee = Employee.objects.get(username='melissa-2026')
        self.assertTrue(check_password('melissa-2026', employee.password))

    def test_hr_and_manager_can_assign_employee_department(self):
        manager = Employee.objects.create(
            full_name='Department Manager',
            username='departmentmanager',
            email='departmentmanager@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        hr_employee = Employee.objects.create(
            full_name='Department HR',
            username='departmenthr',
            email='departmenthr@example.com',
            password=make_password('A-hr-password-482!'),
            phone='1234567891',
            address='HR address',
            account_type='HR',
            role='HR',
        )
        employee = Employee.objects.create(
            full_name='Department Assignment Employee',
            username='departmentassignmentemployee',
            email='departmentassignmentemployee@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567892',
            address='Employee address',
            role='Software Engineer',
        )

        session = self.client.session
        session['home_employee_id'] = manager.pk
        session.save()
        response = self.client.get(
            reverse('edit_employee', args=[employee.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="department"')
        self.assertContains(response, 'Development')
        self.assertContains(response, 'class="employee-photo-placeholder"')
        self.assertContains(response, 'class="employee-edit-photo"')
        self.assertContains(response, 'home/css/edit_employee.css')
        self.assertContains(response, 'name="photo"')
        self.assertContains(response, 'name="resume"')
        self.assertContains(response, 'name="document"')
        self.assertContains(response, 'name="video"')
        self.assertNotContains(response, 'View current resume')
        self.assertNotContains(response, 'Currently:')

        response = self.client.post(
            reverse('edit_employee', args=[employee.pk]),
            {
                'full_name': employee.full_name,
                'username': employee.username,
                'email': employee.email,
                'phone': employee.phone,
                'address': employee.address,
                'account_type': 'EMPLOYEE',
                'role': 'Software Engineer',
                'department': 'DEVELOPMENT',
                'current_project': '',
                'team_number': '',
                'salary': '',
            },
        )
        self.assertRedirects(response, reverse('manager_dashboard'))
        employee.refresh_from_db()
        self.assertEqual(employee.department, 'DEVELOPMENT')
        self.assertEqual(employee.account_type, 'EMPLOYEE')
        self.assertEqual(employee.role, 'Software Engineer')

        response = self.client.get(reverse('home'))
        self.assertEqual(
            {
                item['name']: item['employee_count']
                for item in response.context['departments']
            }['Development'],
            1,
        )
        self.assertEqual(response.context['department_employee_total'], 1)

        session = self.client.session
        session['home_employee_id'] = hr_employee.pk
        session.save()
        response = self.client.get(
            reverse('hr_edit_employee', args=[employee.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="department"')
        self.assertContains(response, 'Testing')
        self.assertContains(response, 'class="hr-employee-photo-container"')
        self.assertContains(response, 'class="hr-employee-photo-placeholder"')
        self.assertContains(response, 'home/css/hr_edit_employee.css')

        response = self.client.post(
            reverse('hr_edit_employee', args=[employee.pk]),
            {
                'salary': '',
                'role': 'Software Engineer',
                'department': 'TESTING_QA',
                'current_project': '',
                'team_number': '',
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('employee_detail')}?employee_id={employee.employee_id}",
        )
        employee.refresh_from_db()
        self.assertEqual(employee.department, 'TESTING_QA')
        self.assertEqual(employee.account_type, 'EMPLOYEE')
        self.assertEqual(employee.role, 'Software Engineer')

        response = self.client.get(reverse('home'))
        department_counts = {
            item['name']: item['employee_count']
            for item in response.context['departments']
        }
        self.assertEqual(department_counts['Development'], 0)
        self.assertEqual(department_counts['Testing'], 1)
        self.assertEqual(response.context['department_employee_total'], 1)

    def test_manager_and_hr_edits_cannot_assign_privileged_roles(self):
        manager = Employee.objects.create(
            full_name='Role Protection Manager',
            username='roleprotectionmanager',
            email='roleprotectionmanager@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        employee = Employee.objects.create(
            full_name='Role Protection Employee',
            username='roleprotectionemployee',
            email='roleprotectionemployee@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567891',
            address='Employee address',
            role='Software Engineer',
        )
        session = self.client.session
        session['home_employee_id'] = manager.pk
        session.save()

        response = self.client.post(
            reverse('edit_employee', args=[employee.pk]),
            {
                'full_name': employee.full_name,
                'username': employee.username,
                'email': employee.email,
                'phone': employee.phone,
                'address': employee.address,
                'account_type': 'ADMIN',
                'role': 'ADMIN',
                'department': 'DEVELOPMENT',
                'salary': '',
                'current_project': '',
                'team_number': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.account_type, 'EMPLOYEE')
        self.assertEqual(employee.role, 'Software Engineer')

        hr = Employee.objects.create(
            full_name='Role Protection HR',
            username='roleprotectionhr',
            email='roleprotectionhr@example.com',
            password=make_password('A-hr-password-482!'),
            phone='1234567892',
            address='HR address',
            account_type='HR',
            role='HR',
        )
        session = self.client.session
        session['home_employee_id'] = hr.pk
        session.save()
        response = self.client.post(
            reverse('hr_edit_employee', args=[employee.pk]),
            {
                'salary': '',
                'role': 'ADMIN',
                'department': 'DEVELOPMENT',
                'current_project': '',
                'team_number': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.account_type, 'EMPLOYEE')
        self.assertEqual(employee.role, 'Software Engineer')

    def test_department_counts_support_role_fallback_and_department_without_role(self):
        employee_data = {
            'password': 'employee-password',
            'phone': '1234567890',
            'address': 'Test address',
        }
        assigned_employee = Employee.objects.create(
            full_name='Fully Assigned Employee',
            username='fullyassignedemployee',
            email='fullyassignedemployee@example.com',
            role='Developer',
            department='DEVELOPMENT',
            **employee_data,
        )
        Employee.objects.create(
            full_name='Role Without Department',
            username='rolewithoutdepartment',
            email='rolewithoutdepartment@example.com',
            role='Tester',
            **employee_data,
        )
        Employee.objects.create(
            full_name='Department Without Role',
            username='departmentwithoutrole',
            email='departmentwithoutrole@example.com',
            department='TESTING_QA',
            **employee_data,
        )
        Employee.objects.create(
            full_name='Neither Assigned',
            username='neitherassigned',
            email='neitherassigned@example.com',
            role=None,
            **employee_data,
        )

        def assert_counts(development, testing, assigned_total, total):
            response = self.client.get(reverse('home'))
            counts = {
                department['name']: department['employee_count']
                for department in response.context['departments']
            }
            self.assertEqual(counts['Development'], development)
            self.assertEqual(counts['Testing'], testing)
            self.assertEqual(
                response.context['department_employee_total'],
                assigned_total,
            )
            self.assertEqual(response.context['employee_count'], total)
            self.assertEqual(
                response.context['employee_count'],
                assigned_total + response.context['unassigned_employee_count'],
            )

        assert_counts(1, 2, 3, 4)

        assigned_employee.department = 'TESTING_QA'
        assigned_employee.save(update_fields=['department'])
        assert_counts(0, 3, 3, 4)

        assigned_employee.role = ''
        assigned_employee.save(update_fields=['role'])
        assert_counts(0, 3, 3, 4)

        assigned_employee.role = 'Developer'
        assigned_employee.department = ''
        assigned_employee.save(update_fields=['role', 'department'])
        assert_counts(1, 2, 3, 4)

        assigned_employee.department = 'DEVELOPMENT'
        assigned_employee.save(update_fields=['department'])
        assert_counts(1, 2, 3, 4)

        assigned_employee.delete()
        assert_counts(0, 2, 2, 3)

    def test_automatic_department_counting_business_logic(self):
        """
        Verify automatic department employee counting specifications:
        - Explicit departments take priority over recognized role mappings.
        - A recognized role can assign an employee when Department is blank.
        - Explicit department alone is sufficient, even when Role is blank.
        - Only account_type == 'EMPLOYEE' is counted.
        - All 5 departments: HR, Development, Testing, Database Administration, IT Support.
        - Case 1: New employee with role & dept -> count increases.
        - Case 2: Existing employee assigned dept -> count increases.
        - Case 3: Department change -> old dept -1, new dept +1.
        - Role removal leaves explicit department assignment intact.
        - Department removal falls back to a recognized role.
        - Case 6: Employee deletion -> dept count -1, total count -1.
        - Non-employee accounts (Admin, HR, Manager) excluded from department counts.
        - No employee counted twice.
        """
        base_kwargs = {
            'password': 'test-password',
            'phone': '1234567890',
            'address': 'Test address',
        }

        # Baseline: initial home check
        res = self.client.get(reverse('home'))
        self.assertEqual(res.context['employee_count'], 0)
        self.assertEqual(res.context['department_employee_total'], 0)

        # Case 1: New Employee with both Role and Department
        dev_emp = Employee.objects.create(
            full_name='Dev Alice',
            username='alice_dev',
            email='alice@example.com',
            role='Software Engineer',
            department='DEVELOPMENT',
            account_type='EMPLOYEE',
            **base_kwargs,
        )
        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Development'], 1)
        self.assertEqual(counts['HR'], 0)
        self.assertEqual(counts['Testing'], 0)
        self.assertEqual(counts['Database Administration'], 0)
        self.assertEqual(counts['IT Support'], 0)
        self.assertEqual(res.context['department_employee_total'], 1)
        self.assertEqual(res.context['employee_count'], 1)

        # Role-only employees use the role mapping.
        role_only = Employee.objects.create(
            full_name='Role Only Bob',
            username='bob_role',
            email='bob@example.com',
            role='QA Engineer',
            department='',
            account_type='EMPLOYEE',
            **base_kwargs,
        )
        # An explicit department is enough even without a role.
        dept_only = Employee.objects.create(
            full_name='Dept Only Carol',
            username='carol_dept',
            email='carol@example.com',
            role='',
            department='TESTING_QA',
            account_type='EMPLOYEE',
            **base_kwargs,
        )
        # Employees with neither field remain unassigned.
        neither = Employee.objects.create(
            full_name='Neither Dave',
            username='dave_neither',
            email='dave@example.com',
            role=None,
            department=None,
            account_type='EMPLOYEE',
            **base_kwargs,
        )
        # A blank role does not prevent an explicit department assignment.
        ws_role = Employee.objects.create(
            full_name='Whitespace Role',
            username='ws_role',
            email='ws_role@example.com',
            role='   ',
            department='HR',
            account_type='EMPLOYEE',
            **base_kwargs,
        )
        ws_dept = Employee.objects.create(
            full_name='Whitespace Dept',
            username='ws_dept',
            email='ws_dept@example.com',
            role='HR Specialist',
            department='   ',
            account_type='EMPLOYEE',
            **base_kwargs,
        )
        # Non-employee account types (Admin, HR, Manager) must not be counted in departments
        admin_acc = Employee.objects.create(
            full_name='Admin User',
            username='admin_acc',
            email='admin_acc@example.com',
            role='System Administrator',
            department='IT_SUPPORT',
            account_type='ADMIN',
            **base_kwargs,
        )
        manager_acc = Employee.objects.create(
            full_name='Manager User',
            username='manager_acc',
            email='manager_acc@example.com',
            role='Project Manager',
            department='DEVELOPMENT',
            account_type='MANAGER',
            **base_kwargs,
        )
        hr_acc = Employee.objects.create(
            full_name='HR User',
            username='hr_acc',
            email='hr_acc@example.com',
            role='HR Manager',
            department='HR',
            account_type='HR',
            **base_kwargs,
        )

        # QA Engineer maps to Testing; HR on an explicit department still counts.
        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Development'], 1)
        self.assertEqual(counts['Testing'], 2)
        self.assertEqual(counts['HR'], 1)
        self.assertEqual(counts['Database Administration'], 0)
        self.assertEqual(counts['IT Support'], 0)
        self.assertEqual(res.context['department_employee_total'], 4)
        # Total EMPLOYEE count: dev_emp, role_only, dept_only, neither, ws_role, ws_dept = 6
        self.assertEqual(res.context['employee_count'], 6)

        # Case 2: Department Assignment
        # When role_only is assigned a department, Testing count increases automatically
        role_only.department = 'TESTING_QA'
        role_only.save(update_fields=['department'])
        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Development'], 1)
        self.assertEqual(counts['Testing'], 2)
        self.assertEqual(counts['HR'], 1)
        self.assertEqual(res.context['department_employee_total'], 4)

        # Case 3: Department Change
        # When an employee moves from Development to Testing:
        # Development decreases by 1, Testing increases by 1
        dev_emp.department = 'TESTING_QA'
        dev_emp.save(update_fields=['department'])
        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Development'], 0)
        self.assertEqual(counts['Testing'], 3)
        self.assertEqual(counts['HR'], 1)
        self.assertEqual(res.context['department_employee_total'], 4)

        # Case 4: Role removal does not erase an explicit department assignment.
        dev_emp.role = ''
        dev_emp.save(update_fields=['role'])
        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Testing'], 3)
        self.assertEqual(counts['HR'], 1)
        self.assertEqual(res.context['department_employee_total'], 4)

        # Case 5: Removing Department falls back to the recognized Role.
        role_only.department = ''
        role_only.save(update_fields=['department'])
        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Testing'], 3)
        self.assertEqual(counts['HR'], 1)
        self.assertEqual(res.context['department_employee_total'], 4)

        # Assign employees to all 5 departments to test all departments
        dev_emp.role = 'Frontend Dev'
        dev_emp.department = 'DEVELOPMENT'
        dev_emp.save(update_fields=['role', 'department'])

        role_only.role = 'QA Tester'
        role_only.department = 'TESTING_QA'
        role_only.save(update_fields=['role', 'department'])

        dept_only.role = 'HR Officer'
        dept_only.department = 'HR'
        dept_only.save(update_fields=['role', 'department'])

        db_emp = Employee.objects.create(
            full_name='DB Admin Edward',
            username='edward_db',
            email='edward@example.com',
            role='DBA',
            department='DATABASE_ADMINISTRATION',
            account_type='EMPLOYEE',
            **base_kwargs,
        )
        it_emp = Employee.objects.create(
            full_name='IT Tech Frank',
            username='frank_it',
            email='frank@example.com',
            role='IT Technician',
            department='IT_SUPPORT',
            account_type='EMPLOYEE',
            **base_kwargs,
        )

        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Development'], 1)
        self.assertEqual(counts['Testing'], 1)
        self.assertEqual(counts['HR'], 2)
        self.assertEqual(counts['Database Administration'], 1)
        self.assertEqual(counts['IT Support'], 1)
        self.assertEqual(res.context['department_employee_total'], 6)
        # Total employees: 6 earlier + 2 new = 8
        self.assertEqual(res.context['employee_count'], 8)

        # Verify department_detail pages reflect dynamic counts
        hr_detail = self.client.get(reverse('department_detail', args=['hr']))
        self.assertEqual(hr_detail.context['employee_count'], 2)
        self.assertContains(hr_detail, dept_only.full_name)

        # Case 6: Employee Deletion
        # When an employee is deleted: automatically decrease department count by 1 and update total employee count
        db_emp.delete()
        res = self.client.get(reverse('home'))
        counts = {d['name']: d['employee_count'] for d in res.context['departments']}
        self.assertEqual(counts['Database Administration'], 0)
        self.assertEqual(res.context['department_employee_total'], 5)
        self.assertEqual(res.context['employee_count'], 7)

    def test_login_page_prompts_again_and_uses_entered_employee_credentials(self):
        first_employee = Employee.objects.create(
            full_name='Previously Signed In',
            username='previoususer',
            email='previous@example.com',
            password=make_password('A-previous-password-482!'),
            phone='1234567890',
            address='First address',
        )
        selected_employee = Employee.objects.create(
            full_name='Selected Employee',
            username='selecteduser',
            email='selected@example.com',
            password=make_password('A-selected-password-482!'),
            phone='0987654321',
            address='Second address',
        )
        session = self.client.session
        session['home_employee_id'] = first_employee.pk
        session.save()

        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Account Login')
        self.assertContains(response, 'name="login_id"')
        self.assertContains(response, 'name="password"')

        response = self.client.post(
            reverse('login'),
            {
                'login_id': selected_employee.username,
                'password': 'A-selected-password-482!',
            },
        )

        self.assertRedirects(response, reverse('profile'))
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selected Employee')
        self.assertNotContains(response, 'Previously Signed In')

    def test_role_login_redirects_to_correct_dashboard(self):
        for role, route in (
            ('MANAGER', 'manager_dashboard'),
            ('HR', 'hr_dashboard'),
        ):
            employee = Employee.objects.create(
                full_name=f'{role} User',
                username=f'{role.lower()}user',
                email=f'{role.lower()}@example.com',
                password=make_password('A-unique-password-482!'),
                phone='1234567890',
                address='Test address',
                account_type=role,
                role=role,
            )
            response = self.client.post(
                reverse('login'),
                {
                    'login_id': employee.username,
                    'password': 'A-unique-password-482!',
                },
            )
            self.assertRedirects(response, reverse(route))
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
            self.client.get(reverse('logout'))

    def test_manager_can_view_edit_and_delete_admin_accounts(self):
        manager = Employee.objects.create(
            full_name='Account Manager',
            username='accountmanager',
            email='accountmanager@example.com',
            password=make_password('A-unique-password-482!'),
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        admin = Employee.objects.create(
            full_name='Dashboard Admin',
            username='dashboardadmin',
            email='dashboardadmin@example.com',
            password=make_password('A-unique-password-482!'),
            phone='0987654321',
            address='Admin address',
            account_type='ADMIN',
            role='ADMIN',
        )
        session = self.client.session
        session['home_employee_id'] = manager.pk
        session.save()

        response = self.client.get(reverse('manager_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, admin.full_name)
        self.assertContains(response, admin.email)
        self.assertContains(
            response,
            reverse('edit_employee', args=[admin.pk]),
        )
        self.assertContains(
            response,
            reverse('delete_employee', args=[admin.employee_id]),
        )
        self.assertContains(response, '<p>Total Accounts</p>', html=True)
        self.assertContains(response, '<p>Total Admins</p>', html=True)
        self.assertEqual(response.context['total_accounts'], 2)
        self.assertEqual(response.context['total_admins'], 1)

        response = self.client.get(
            reverse('employee_detail'),
            {'employee_id': admin.employee_id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, admin.full_name)
        self.assertContains(
            response,
            reverse('edit_employee', args=[admin.pk]),
        )

        response = self.client.post(
            reverse('edit_employee', args=[admin.pk]),
            {
                'full_name': 'Updated Admin',
                'username': 'updatedadmin',
                'email': 'updatedadmin@example.com',
                'phone': '1112223333',
                'address': 'Updated admin address',
                'account_type': 'ADMIN',
                'salary': '100000',
                'role': 'System Administrator',
                'current_project': 'Admin Console',
                'team_number': 'Leadership',
            },
        )
        self.assertRedirects(response, reverse('manager_dashboard'))
        admin.refresh_from_db()
        self.assertEqual(admin.full_name, 'Updated Admin')
        self.assertEqual(admin.account_type, 'ADMIN')
        self.assertEqual(str(admin.salary), '100000.00')

        response = self.client.post(
            reverse('delete_employee', args=[admin.employee_id]),
        )
        self.assertRedirects(response, reverse('manager_dashboard'))
        self.assertFalse(Employee.objects.filter(pk=admin.pk).exists())


class AdministrationPortalTests(TestCase):
    def setUp(self):
        self.admin = Employee.objects.create(
            full_name='Site Admin',
            username='siteadmin',
            email='admin@example.com',
            password=make_password('A-unique-admin-password-482!'),
            phone='1234567890',
            address='Admin address',
            account_type='ADMIN',
            role='ADMIN',
        )

    def _select_employee_for_admin(self, employee):
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session['admin_selected_employee_id'] = employee.pk
        session.save()

    def _employee_edit_data(self, employee, **updates):
        data = {
            'employee_id': employee.employee_id,
            'full_name': employee.full_name,
            'username': employee.username,
            'email': employee.email,
            'phone': employee.phone,
            'address': employee.address,
            'account_type': employee.account_type,
            'salary': employee.salary or '',
            'role': employee.role or '',
            'department': employee.department,
            'current_project': employee.current_project or '',
            'team_number': employee.team_number or '',
        }
        data.update(updates)
        return data

    def test_admin_can_update_all_employee_details_and_replace_files(self):
        employee = Employee.objects.create(
            full_name='Original Employee',
            username='originalemployee',
            email='originalemployee@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1111111111',
            address='Original address',
            account_type='EMPLOYEE',
            role='Developer',
            department='DEVELOPMENT',
        )
        self._select_employee_for_admin(employee)

        image_buffer = BytesIO()
        Image.new('RGB', (2, 2), color='blue').save(image_buffer, format='PNG')
        image_upload = SimpleUploadedFile(
            'updated-photo.png',
            image_buffer.getvalue(),
            content_type='image/png',
        )
        pdf_content = b'%PDF-1.4\n%%EOF'
        uploads = {
            'photo': image_upload,
            'resume': SimpleUploadedFile(
                'updated-resume.pdf',
                pdf_content,
                content_type='application/pdf',
            ),
            'document': SimpleUploadedFile(
                'updated-document.pdf',
                pdf_content,
                content_type='application/pdf',
            ),
            'video': SimpleUploadedFile(
                'updated-video.mp4',
                b'video data',
                content_type='video/mp4',
            ),
        }
        data = self._employee_edit_data(
            employee,
            employee_id='UPDATED-EMP-0101',
            full_name='Updated Employee',
            username='updatedemployee',
            email='updatedemployee@example.com',
            phone='2222222222',
            address='Updated address',
            account_type='MANAGER',
            salary='95000.50',
            role='Engineering Lead',
            department='DEVELOPMENT',
            current_project='New Project',
            team_number='Team 9',
            **uploads,
        )

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse(
                        'administration:admin_edit_employee',
                        args=[employee.pk],
                    ),
                    data,
                    follow=True,
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Updated Employee')
                employee.refresh_from_db()
                self.assertEqual(employee.employee_id, 'UPDATED-EMP-0101')
                self.assertEqual(employee.username, 'updatedemployee')
                self.assertEqual(employee.email, 'updatedemployee@example.com')
                self.assertEqual(employee.phone, '2222222222')
                self.assertEqual(employee.address, 'Updated address')
                self.assertEqual(employee.account_type, 'MANAGER')
                self.assertEqual(str(employee.salary), '95000.50')
                self.assertEqual(employee.role, 'Engineering Lead')
                self.assertEqual(employee.department, 'DEVELOPMENT')
                self.assertEqual(employee.current_project, 'New Project')
                self.assertEqual(employee.team_number, 'Team 9')
                self.assertEqual(employee.photo.name, 'employees/photos/updated-photo.png')
                self.assertEqual(employee.resume.name, 'employees/resumes/updated-resume.pdf')
                self.assertEqual(employee.document.name, 'employees/documents/updated-document.pdf')
                self.assertEqual(employee.video.name, 'employees/videos/updated-video.mp4')
                self.assertContains(response, employee.photo.url)

    def test_admin_edit_preserves_files_when_no_replacement_is_uploaded(self):
        image_buffer = BytesIO()
        Image.new('RGB', (2, 2), color='green').save(image_buffer, format='PNG')
        employee = Employee.objects.create(
            full_name='Existing Files Employee',
            username='existingfilesemployee',
            email='existingfilesemployee@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
        )

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                employee.photo.save(
                    'existing-photo.png',
                    ContentFile(image_buffer.getvalue()),
                    save=False,
                )
                employee.resume.save(
                    'existing-resume.pdf',
                    ContentFile(b'%PDF-1.4\n%%EOF'),
                    save=False,
                )
                employee.document.save(
                    'existing-document.pdf',
                    ContentFile(b'%PDF-1.4\n%%EOF'),
                    save=False,
                )
                employee.video.save(
                    'existing-video.mp4',
                    ContentFile(b'video data'),
                    save=False,
                )
                employee.save()
                original_files = (
                    employee.photo.name,
                    employee.resume.name,
                    employee.document.name,
                    employee.video.name,
                )
                self._select_employee_for_admin(employee)

                response = self.client.post(
                    reverse(
                        'administration:admin_edit_employee',
                        args=[employee.pk],
                    ),
                    self._employee_edit_data(employee),
                )

                self.assertRedirects(
                    response,
                    reverse('administration:admin_employee_details'),
                )
                employee.refresh_from_db()
                self.assertEqual(
                    (
                        employee.photo.name,
                        employee.resume.name,
                        employee.document.name,
                        employee.video.name,
                    ),
                    original_files,
                )

    def test_admin_edit_rejects_invalid_file_type_and_size(self):
        employee = Employee.objects.create(
            full_name='File Validation Employee',
            username='filevalidationemployee',
            email='filevalidationemployee@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        self._select_employee_for_admin(employee)
        edit_url = reverse(
            'administration:admin_edit_employee',
            args=[employee.pk],
        )

        response = self.client.post(
            edit_url,
            self._employee_edit_data(employee, account_type='ADMIN'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('account_type', response.context['form'].errors)
        self.assertEqual(
            Employee.objects.get(pk=employee.pk).account_type,
            'EMPLOYEE',
        )

        response = self.client.post(
            edit_url,
            self._employee_edit_data(
                employee,
                photo=SimpleUploadedFile(
                    'photo.txt',
                    b'not an image',
                    content_type='text/plain',
                ),
                resume=SimpleUploadedFile(
                    'not-a-resume.docx',
                    b'not a PDF',
                    content_type='application/octet-stream',
                ),
                document=SimpleUploadedFile(
                    'document.exe',
                    b'not a document',
                    content_type='application/octet-stream',
                ),
                video=SimpleUploadedFile(
                    'video.avi',
                    b'not a supported video',
                    content_type='application/octet-stream',
                ),
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('photo', response.context['form'].errors)
        self.assertIn('resume', response.context['form'].errors)
        self.assertIn('document', response.context['form'].errors)
        self.assertIn('video', response.context['form'].errors)
        self.assertFalse(Employee.objects.get(pk=employee.pk).resume)

        oversized_pdf = SimpleUploadedFile(
            'oversized-resume.pdf',
            b'%PDF-' + (b'0' * (10 * 1024 * 1024)),
            content_type='application/pdf',
        )
        response = self.client.post(
            edit_url,
            self._employee_edit_data(employee, resume=oversized_pdf),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Resume must be no larger than 10 MB.',
        )

    def test_admin_login_and_dashboard_links(self):
        response = self.client.get(
            reverse('administration:admin_login')
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="username"')

        response = self.client.post(
            reverse('administration:admin_login'),
            {
                'username': self.admin.username,
                'password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )

        response = self.client.get(
            reverse('administration:admin_dashboard')
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('administration:search_employee'),
        )
        self.assertContains(response, reverse('register'))
        self.assertContains(response, 'name="employee_id"')
        self.assertContains(response, 'name="admin_password"')
        self.assertContains(response, 'name="manager_verification"')
        self.assertContains(response, 'name="manager_password"')
        self.assertContains(response, 'class="admin-password-section"')
        self.assertContains(
            response,
            'id="manager-password-section" hidden',
        )

    def test_admin_dashboard_year_change_requires_admin_password(self):
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        response = self.client.get(
            reverse('administration:admin_dashboard'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['dashboard_year'],
            date.today().year,
        )
        self.assertContains(response, 'Change year')
        self.assertContains(response, 'id="dashboard-year-form"')
        self.assertContains(
            response,
            'id="dashboard-year-form"',
        )

        selected_year = date.today().year - 1
        response = self.client.post(
            reverse('administration:admin_dashboard'),
            {
                'year': selected_year,
                'admin_password': 'incorrect-password',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        configuration = EmployeeIdConfiguration.objects.get(pk=1)
        self.assertEqual(configuration.year, date.today().year)

        response = self.client.post(
            reverse('administration:admin_dashboard'),
            {
                'year': selected_year,
                'admin_password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        self.assertEqual(
            EmployeeIdConfiguration.objects.get(pk=1).year,
            selected_year,
        )

        response = self.client.get(
            reverse('administration:admin_dashboard'),
        )
        self.assertEqual(response.context['dashboard_year'], selected_year)
        self.assertContains(
            response,
            f'Administration Dashboard · {selected_year}',
        )

        response = self.client.post(
            reverse('administration:admin_dashboard'),
            {
                'year': 'not-a-year',
                'admin_password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        response = self.client.get(
            reverse('administration:admin_dashboard'),
        )
        self.assertEqual(
            response.context['dashboard_year'],
            selected_year,
        )
        self.assertNotContains(
            response,
            'Enter an Employee ID and your Administration password.',
        )

    def test_admin_year_change_sets_prefix_for_new_ids_only(self):
        configuration, _ = EmployeeIdConfiguration.objects.get_or_create(
            pk=1,
            defaults={'year': date.today().year},
        )
        configuration.year = 2022
        configuration.save(update_fields=['year'])
        existing_employee = Employee.objects.create(
            full_name='Existing Year Employee',
            username='existingyearadminflow',
            email='existingyearadminflow@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        self.assertEqual(existing_employee.employee_id, '22MQ1A0101')

        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()
        response = self.client.post(
            reverse('administration:admin_dashboard'),
            {
                'year': 2026,
                'admin_password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )

        new_employee = Employee.objects.create(
            full_name='New Year Employee',
            username='newyearadminflow',
            email='newyearadminflow@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567891',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        manager = Employee.objects.create(
            full_name='New Year Manager',
            username='newyearmanageradminflow',
            email='newyearmanageradminflow@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567892',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )

        existing_employee.refresh_from_db()
        self.assertEqual(existing_employee.employee_id, '22MQ1A0101')
        self.assertEqual(new_employee.employee_id, '26MQ1A0102')
        self.assertEqual(manager.employee_id, '26MQ1G0103')

    def test_admin_search_requires_own_password_for_employee_details(self):
        employee = Employee.objects.create(
            full_name='Searchable Employee',
            username='searchableemployee',
            email='searchable@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
        )
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        response = self.client.post(
            reverse('administration:search_employee'),
            {'employee_id': employee.employee_id},
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        self.assertNotIn('admin_selected_employee_id', self.client.session)

        response = self.client.post(
            reverse('administration:search_employee'),
            {
                'employee_id': employee.employee_id,
                'admin_password': 'incorrect-password',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        self.assertNotIn('admin_selected_employee_id', self.client.session)

        response = self.client.post(
            reverse('administration:search_employee'),
            {
                'employee_id': employee.employee_id,
                'admin_password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_employee_details'),
        )
        self.assertEqual(
            self.client.session['admin_selected_employee_id'],
            employee.pk,
        )

    def test_admin_search_requires_both_passwords_for_manager_details(self):
        manager = Employee.objects.create(
            full_name='Protected Manager',
            username='protectedmanager',
            email='protectedmanager@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        base_data = {
            'employee_id': manager.employee_id,
            'admin_password': 'A-unique-admin-password-482!',
        }
        cases = (
            ({**base_data}, 'Select the Manager verification checkbox'),
            (
                {**base_data, 'manager_verification': 'yes'},
                'Enter the Manager password',
            ),
            (
                {
                    **base_data,
                    'manager_verification': 'yes',
                    'manager_password': 'incorrect-password',
                },
                'Incorrect Manager password',
            ),
            (
                {
                    **base_data,
                    'admin_password': 'incorrect-password',
                    'manager_verification': 'yes',
                    'manager_password': 'A-manager-password-482!',
                },
                'Incorrect Administration password',
            ),
        )
        for data, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                response = self.client.post(
                    reverse('administration:search_employee'),
                    data,
                    follow=True,
                )
                self.assertContains(response, expected_message)
                self.assertNotIn(
                    'admin_selected_employee_id',
                    self.client.session,
                )

        response = self.client.post(
            reverse('administration:search_employee'),
            {
                **base_data,
                'manager_verification': 'yes',
                'manager_password': 'A-manager-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_employee_details'),
        )
        self.assertEqual(
            self.client.session['admin_selected_employee_id'],
            manager.pk,
        )

    def test_manager_verification_checkbox_is_rejected_for_employee(self):
        employee = Employee.objects.create(
            full_name='Regular Employee',
            username='regularemployee',
            email='regular@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
        )
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        response = self.client.post(
            reverse('administration:search_employee'),
            {
                'employee_id': employee.employee_id,
                'admin_password': 'A-unique-admin-password-482!',
                'manager_verification': 'yes',
                'manager_password': 'A-employee-password-482!',
            },
            follow=True,
        )

        self.assertContains(
            response,
            'Manager verification is only for Manager accounts.',
        )
        self.assertNotIn('admin_selected_employee_id', self.client.session)

    def test_admin_cannot_open_an_unverified_account_edit_url(self):
        employee = Employee.objects.create(
            full_name='Unverified Employee',
            username='unverifiedemployee',
            email='unverified@example.com',
            password=make_password('A-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
        )
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        response = self.client.get(
            reverse('administration:admin_edit_employee', args=[employee.pk])
        )

        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )

    def test_admin_login_requires_admin_username_and_password(self):
        employee = Employee.objects.create(
            full_name='Not An Admin',
            username='notadmin',
            email='notadmin@example.com',
            password=make_password('A-unique-employee-password-482!'),
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
            role='Employee',
        )

        for username, password in (
            (employee.username, 'A-unique-employee-password-482!'),
            (self.admin.email, 'A-unique-admin-password-482!'),
            (self.admin.employee_id, 'A-unique-admin-password-482!'),
            (self.admin.username, 'incorrect-password'),
        ):
            with self.subTest(username=username):
                response = self.client.post(
                    reverse('administration:admin_login'),
                    {'username': username, 'password': password},
                )
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(
                    'administration_admin_id',
                    self.client.session,
                )

        response = self.client.post(
            reverse('administration:admin_login'),
            {
                'username': self.admin.username,
                'password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )

    def test_admin_login_always_prompts_and_dashboard_uses_authenticated_admin(self):
        second_admin = Employee.objects.create(
            full_name='Alternate Portal Owner',
            username='secondsiteadmin',
            email='secondadmin@example.com',
            password=make_password('A-second-admin-password-482!'),
            phone='1112223333',
            address='Second admin address',
            account_type='ADMIN',
            role='ADMIN',
        )
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session['admin_selected_employee_id'] = second_admin.pk
        session.save()

        response = self.client.get(
            reverse('administration:admin_login')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Administration Login')
        self.assertContains(response, 'name="username"')
        self.assertNotIn(
            'administration_admin_id',
            self.client.session,
        )
        self.assertNotIn(
            'admin_selected_employee_id',
            self.client.session,
        )

        response = self.client.post(
            reverse('administration:admin_login'),
            {
                'username': second_admin.username,
                'password': 'A-second-admin-password-482!',
            },
        )

        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        self.assertEqual(
            self.client.session['administration_admin_id'],
            second_admin.pk,
        )
        response = self.client.get(
            reverse('administration:admin_dashboard')
        )
        self.assertContains(response, second_admin.full_name)
        self.assertNotContains(response, self.admin.full_name)

    def test_failed_admin_login_cannot_reuse_previous_admin_session(self):
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        response = self.client.post(
            reverse('administration:admin_login'),
            {
                'username': self.admin.username,
                'password': 'incorrect-password',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Incorrect username or password.')
        self.assertNotIn(
            'administration_admin_id',
            self.client.session,
        )
        self.assertRedirects(
            self.client.get(
                reverse('administration:admin_dashboard')
            ),
            reverse('administration:admin_login'),
        )

    def test_legacy_admin_role_can_sign_in_by_username_and_password(self):
        legacy_admin = Employee.objects.create(
            full_name='Legacy Admin',
            username='legacyadmin',
            email='legacyadmin@example.com',
            password=make_password('A-legacy-admin-password-482!'),
            phone='1234567890',
            address='Admin address',
            account_type='EMPLOYEE',
            role='ADMIN',
        )

        response = self.client.post(
            reverse('administration:admin_login'),
            {
                'username': legacy_admin.username,
                'password': 'A-legacy-admin-password-482!',
            },
        )

        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        legacy_admin.refresh_from_db()
        self.assertEqual(legacy_admin.account_type, 'ADMIN')
        self.assertEqual(
            self.client.get(
                reverse('administration:admin_dashboard')
            ).status_code,
            200,
        )

    def test_manager_setup_assigns_manager_id_from_101(self):
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        response = self.client.post(
            reverse('administration:admin_setup_manager'),
            {
                'full_name': 'New Setup Manager',
                'username': 'newsetupmanager',
                'email': 'newsetupmanager@example.com',
                'phone': '1234567890',
                'address': 'Manager address',
                'password': 'A-new-manager-password-482!',
                'confirm_password': 'A-new-manager-password-482!',
            },
        )

        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        manager = Employee.objects.get(username='newsetupmanager')
        self.assertEqual(
            manager.employee_id,
            f'{date.today().year % 100:02d}MQ1G0102',
        )

    def test_manager_setup_promotes_existing_employee_and_changes_id_prefix(self):
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()
        employee = Employee.objects.create(
            full_name='Employee To Promote',
            username='employeetopromote',
            email='employeetopromote@example.com',
            password='employee-password',
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
            role='Developer',
        )
        original_employee_id = employee.employee_id

        response = self.client.post(
            reverse('administration:admin_setup_manager'),
            {'employee_id': original_employee_id},
        )

        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        employee.refresh_from_db()
        self.assertEqual(employee.account_type, 'MANAGER')
        self.assertEqual(employee.role, 'MANAGER')
        self.assertEqual(
            employee.employee_id,
            original_employee_id.replace('MQ1A', 'MQ1G'),
        )

    def test_promoted_employee_keeps_sequence_and_new_manager_gets_next_id(self):
        configuration, _ = EmployeeIdConfiguration.objects.get_or_create(
            pk=1,
            defaults={'year': date.today().year},
        )
        configuration.year = 2022
        configuration.save(update_fields=['year'])
        Employee.objects.create(
            employee_id='22MQ1A0504',
            full_name='Previous Sequence Employee',
            username='previoussequenceemployee',
            email='previoussequenceemployee@example.com',
            password='employee-password',
            phone='1234567890',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        employee = Employee.objects.create(
            full_name='Promoted Sequence Employee',
            username='promotedsequenceemployee',
            email='promotedsequenceemployee@example.com',
            password='employee-password',
            phone='1234567891',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        self.assertEqual(employee.employee_id, '22MQ1A0505')

        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()
        response = self.client.post(
            reverse('administration:admin_setup_manager'),
            {'employee_id': employee.employee_id},
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )
        employee.refresh_from_db()
        self.assertEqual(employee.employee_id, '22MQ1G0505')

        manager = Employee.objects.create(
            full_name='New Manager After Promotion',
            username='newmanagerafterpromotion',
            email='newmanagerafterpromotion@example.com',
            password='manager-password',
            phone='1234567892',
            address='Manager address',
            account_type='MANAGER',
        )
        self.assertEqual(manager.employee_id, '22MQ1G0506')

    def test_manager_setup_rejects_promotion_when_manager_id_is_in_use(self):
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()
        Employee.objects.create(
            full_name='Existing Manager',
            username='existingmanager',
            email='existingmanager@example.com',
            password='manager-password',
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        employee = Employee.objects.create(
            employee_id=f'{date.today().year % 100:02d}MQ1A0102',
            full_name='Employee With Colliding ID',
            username='employeehascollidingid',
            email='employeehascollidingid@example.com',
            password='employee-password',
            phone='1234567891',
            address='Employee address',
            account_type='EMPLOYEE',
        )
        original_employee_id = employee.employee_id

        response = self.client.post(
            reverse('administration:admin_setup_manager'),
            {'employee_id': employee.employee_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'matching manager ID is already in use')
        employee.refresh_from_db()
        self.assertEqual(employee.account_type, 'EMPLOYEE')
        self.assertEqual(employee.employee_id, original_employee_id)

    def test_manager_setup_reports_unknown_employee_id(self):
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        response = self.client.post(
            reverse('administration:admin_setup_manager'),
            {'employee_id': 'not-an-employee-id'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No employee was found')

    def test_admin_can_use_normal_login_for_profile_and_admin_login(self):
        self.admin.role = 'MANAGER'
        self.admin.save(update_fields=['role'])

        response = self.client.post(
            reverse('login'),
            {
                'login_id': self.admin.username,
                'password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(
            self.client.session['home_employee_id'],
            self.admin.pk,
        )
        self.assertNotIn('administration_admin_id', self.client.session)

        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin.full_name)
        self.assertContains(response, self.admin.username)
        self.assertContains(response, self.admin.email)
        self.assertContains(response, self.admin.address)
        self.assertRedirects(
            self.client.get(reverse('manager_dashboard')),
            reverse('login'),
        )
        self.assertRedirects(
            self.client.get(reverse('hr_dashboard')),
            reverse('login'),
        )

        self.assertRedirects(
            self.client.get(reverse('administration:admin_dashboard')),
            reverse('administration:admin_login'),
        )

        response = self.client.post(
            reverse('administration:admin_login'),
            {
                'username': self.admin.username,
                'password': 'A-unique-admin-password-482!',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_dashboard'),
        )

    def test_admin_employee_details_show_separated_information(self):
        employee = Employee.objects.create(
            full_name='Admin View Employee',
            username='adminviewemployee',
            email='adminviewemployee@example.com',
            password=make_password('A-unique-password-482!'),
            phone='1234567890',
            address='Employee address',
            role='Analyst',
            current_project='Records Portal',
        )
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session['admin_selected_employee_id'] = employee.pk
        session.save()

        response = self.client.get(
            reverse('administration:admin_employee_details')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin View Employee')
        self.assertContains(response, 'Personal Details')
        self.assertContains(response, 'Professional Details')
        self.assertContains(response, 'Account Details')
        self.assertContains(response, 'Records Portal')

    def test_admin_can_edit_manager_hr_and_own_profile(self):
        manager = Employee.objects.create(
            full_name='Editable Manager',
            username='editablemanager',
            email='editablemanager@example.com',
            password=make_password('A-unique-password-482!'),
            phone='1111111111',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        hr = Employee.objects.create(
            full_name='Editable HR',
            username='editablehr',
            email='editablehr@example.com',
            password=make_password('A-unique-password-482!'),
            phone='2222222222',
            address='HR address',
            account_type='HR',
            role='HR',
        )
        session = self.client.session
        session['administration_admin_id'] = self.admin.pk
        session.save()

        for employee, new_type in ((manager, 'HR'), (hr, 'MANAGER')):
            with self.subTest(employee=employee.username):
                session = self.client.session
                session['admin_selected_employee_id'] = employee.pk
                session.save()
                response = self.client.get(
                    reverse(
                        'administration:admin_edit_employee',
                        args=[employee.pk],
                    )
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="profile-image-placeholder"')
                self.assertContains(response, 'name="photo"')
                self.assertContains(response, 'name="resume"')
                self.assertContains(response, 'name="document"')
                self.assertContains(response, 'name="video"')
                self.assertContains(
                    response,
                    'administration/css/admin_edit_employee.css',
                )
                self.assertContains(
                    response,
                    'administration/js/admin_edit_employee.js',
                )
                self.assertNotContains(response, 'View current resume')
                self.assertNotContains(response, 'Currently:')
                response = self.client.post(
                    reverse(
                        'administration:admin_edit_employee',
                        args=[employee.pk],
                    ),
                    {
                        'full_name': employee.full_name,
                        'username': employee.username,
                        'email': employee.email,
                        'phone': employee.phone,
                        'address': employee.address,
                        'account_type': new_type,
                        'salary': '100000',
                        'role': new_type,
                        'current_project': 'Admin-managed project',
                        'team_number': 'Team 2',
                    },
                )
                self.assertEqual(
                    response.status_code,
                    302,
                    response.context['form'].errors if response.context else response.content,
                )
                self.assertRedirects(
                    response,
                    reverse('administration:admin_employee_details'),
                )
                employee.refresh_from_db()
                self.assertEqual(employee.account_type, new_type)
                self.assertEqual(str(employee.salary), '100000.00')

        session = self.client.session
        session['admin_selected_employee_id'] = self.admin.pk
        session.save()
        response = self.client.get(
            reverse(
                'administration:admin_edit_employee',
                args=[self.admin.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].fields['account_type'].disabled)
        self.assertTrue(response.context['form'].fields['employee_id'].disabled)

        response = self.client.post(
            reverse(
                'administration:admin_edit_employee',
                args=[self.admin.pk],
            ),
            {
                'employee_id': self.admin.employee_id,
                'full_name': 'Updated Site Admin',
                'username': self.admin.username,
                'email': self.admin.email,
                'phone': '3333333333',
                'address': 'Updated admin address',
                'account_type': 'EMPLOYEE',
                'salary': '100000',
                'role': 'ADMIN',
                'current_project': 'Admin Console',
                'team_number': 'Leadership',
            },
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_employee_details'),
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, 'Updated Site Admin')
        self.assertEqual(self.admin.account_type, 'ADMIN')

    def test_home_always_shows_login_register_and_administration(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        for route in ('login', 'register', 'administration:admin_login'):
            with self.subTest(route=route):
                self.assertContains(response, reverse(route))

    def test_dashboard_redirects_to_login_without_admin_session(self):
        response = self.client.get(
            reverse('administration:admin_dashboard')
        )
        self.assertRedirects(
            response,
            reverse('administration:admin_login'),
        )

    def test_manager_employee_session_cannot_access_admin_dashboard(self):
        manager = Employee.objects.create(
            full_name='Dashboard Gate Manager',
            username='dashboardgatemanager',
            email='dashboardgatemanager@example.com',
            password=make_password('A-manager-password-482!'),
            phone='1234567890',
            address='Manager address',
            account_type='MANAGER',
            role='MANAGER',
        )
        session = self.client.session
        session['home_employee_id'] = manager.pk
        session.save()

        response = self.client.get(
            reverse('administration:admin_dashboard')
        )

        self.assertRedirects(
            response,
            reverse('administration:admin_login'),
        )
        self.assertNotIn(
            'administration_admin_id',
            self.client.session,
        )

    def test_every_registered_view_name_resolves(self):
        names = [
            'home',
            'login',
            'register',
            'logout',
            'profile',
            'manager_dashboard',
            'hr_dashboard',
            'employee_detail',
            'edit_employee',
            'delete_employee',
            'hr_edit_employee',
            'hr_delete_employee',
            'forgot_password',
            'administration:admin_login',
            'administration:admin_dashboard',
            'administration:search_employee',
            'administration:admin_employee_details',
            'administration:admin_edit_employee',
            'administration:admin_delete_employee',
            'administration:admin_setup_manager',
            'administration:admin_logout',
        ]
        for name in names:
            with self.subTest(name=name):
                args = [1] if name in {
                    'edit_employee',
                    'hr_edit_employee',
                    'hr_delete_employee',
                    'administration:admin_edit_employee',
                    'administration:admin_delete_employee',
                } else ['EMP001'] if name == 'delete_employee' else None
                reverse(name, args=args)


class PasswordResetFlowTests(TestCase):
    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EMAIL_HOST_USER='noreply@example.com',
        EMAIL_HOST_PASSWORD='test-password',
        DEFAULT_FROM_EMAIL='noreply@example.com',
    )
    def test_password_reset_email_otp_changes_password_and_allows_login(self):
        employee = Employee.objects.create(
            full_name='Password Reset Employee',
            username='passwordresetemployee',
            email='passwordreset@example.com',
            password=make_password('A-previous-password-482!'),
            phone='1234567890',
            address='Test address',
        )

        response = self.client.post(
            reverse('forgot_password'),
            {'action': 'send_otp', 'email': employee.email},
        )

        self.assertContains(
            response,
            'A reset code has been sent to your email.',
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [employee.email])
        otp_match = re.search(r'\b(\d{6})\b', mail.outbox[0].body)
        self.assertIsNotNone(otp_match)
        otp = otp_match.group(1)

        response = self.client.post(
            reverse('forgot_password'),
            {'action': 'verify_otp', 'otp': otp},
        )
        self.assertContains(response, 'name="confirm_password"')

        new_password = 'A-new-unique-password-583!'
        response = self.client.post(
            reverse('forgot_password'),
            {
                'action': 'reset_password',
                'password': new_password,
                'confirm_password': new_password,
            },
        )
        self.assertContains(response, 'Password changed. You can now log in.')

        employee.refresh_from_db()
        self.assertTrue(check_password(new_password, employee.password))
        response = self.client.post(
            reverse('login'),
            {'login_id': employee.username, 'password': new_password},
        )
        self.assertRedirects(response, reverse('profile'))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EMAIL_HOST_USER='noreply@example.com',
        EMAIL_HOST_PASSWORD='test-password',
        DEFAULT_FROM_EMAIL='noreply@example.com',
    )
    def test_password_reset_otp_cannot_be_used_after_expiration(self):
        employee = Employee.objects.create(
            full_name='Expired Reset Employee',
            username='expiredresetemployee',
            email='expiredreset@example.com',
            password=make_password('A-previous-password-482!'),
            phone='1234567890',
            address='Test address',
        )
        self.client.post(
            reverse('forgot_password'),
            {'action': 'send_otp', 'email': employee.email},
        )
        otp = re.search(r'\b(\d{6})\b', mail.outbox[0].body).group(1)
        self.client.post(
            reverse('forgot_password'),
            {'action': 'verify_otp', 'otp': otp},
        )

        session = self.client.session
        session['password_reset_expires'] = (
            timezone.now() - timedelta(minutes=1)
        ).isoformat()
        session.save()

        response = self.client.post(
            reverse('forgot_password'),
            {
                'action': 'reset_password',
                'password': 'A-new-unique-password-583!',
                'confirm_password': 'A-new-unique-password-583!',
            },
        )

        self.assertContains(response, 'Your reset code expired.')
        employee.refresh_from_db()
        self.assertTrue(
            check_password('A-previous-password-482!', employee.password)
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EMAIL_HOST_USER='noreply@example.com',
        EMAIL_HOST_PASSWORD='test-password',
        DEFAULT_FROM_EMAIL='noreply@example.com',
    )
    def test_password_reset_otp_locks_after_five_incorrect_attempts(self):
        employee = Employee.objects.create(
            full_name='OTP Attempts Employee',
            username='otpattemptsemployee',
            email='otpattempts@example.com',
            password=make_password('A-previous-password-482!'),
            phone='1234567890',
            address='Test address',
        )
        self.client.post(
            reverse('forgot_password'),
            {'action': 'send_otp', 'email': employee.email},
        )

        for attempt in range(5):
            response = self.client.post(
                reverse('forgot_password'),
                {'action': 'verify_otp', 'otp': f'{attempt:06d}'},
            )

        self.assertContains(response, 'Too many incorrect codes.')
        self.assertNotIn('password_reset_otp', self.client.session)

    @override_settings(EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_password_reset_reports_missing_email_configuration(self):
        employee = Employee.objects.create(
            full_name='Unconfigured Email Employee',
            username='unconfiguredemailemployee',
            email='unconfiguredemail@example.com',
            password=make_password('A-previous-password-482!'),
            phone='1234567890',
            address='Test address',
        )

        response = self.client.post(
            reverse('forgot_password'),
            {'action': 'send_otp', 'email': employee.email},
        )

        self.assertContains(response, 'Email sending is not configured.')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_HOST_USER='noreply@example.com',
        EMAIL_HOST_PASSWORD='not-a-real-app-password',
        DEFAULT_FROM_EMAIL='noreply@example.com',
    )
    @patch(
        'home.views.send_mail',
        side_effect=SMTPServerDisconnected('Connection unexpectedly closed'),
    )
    def test_password_reset_explains_when_gmail_rejects_the_login(self, _send_mail):
        employee = Employee.objects.create(
            full_name='Rejected Mail Employee',
            username='rejectedmailemployee',
            email='rejectedmail@example.com',
            password=make_password('A-previous-password-482!'),
            phone='1234567890',
            address='Test address',
        )

        response = self.client.post(
            reverse('forgot_password'),
            {'action': 'send_otp', 'email': employee.email},
        )

        self.assertContains(response, 'Gmail refused the login')
        self.assertNotIn('password_reset_otp', self.client.session)
