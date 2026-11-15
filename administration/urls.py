
from django.urls import path
from . import views

app_name = 'administration'

urlpatterns = [
    path('', views.admin_login, name='admin_login'),
    path(
        'dashboard/',
        views.admin_dashboard,
        name='admin_dashboard',
    ),
    path(
        'search-employee/',
        views.search_employee,
        name='search_employee',
    ),
    path(
        'employee-details/',
        views.admin_employee_details,
        name='admin_employee_details',
    ),
    path(
        'edit-employee/<int:id>/',
        views.admin_edit_employee,
        name='admin_edit_employee',
    ),
    path(
        'delete-employee/<int:id>/',
        views.admin_delete_employee,
        name='admin_delete_employee',
    ),
    path(
        'setup-manager/',
        views.admin_setup_manager,
        name='admin_setup_manager',
    ),
    path(
        'logout/',
        views.admin_logout,
        name='admin_logout',
    ),
]
