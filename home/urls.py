from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path(
        'departments/<slug:department_slug>/',
        views.department_detail,
        name='department_detail',
    ),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('hr/', views.hr_dashboard, name='hr_dashboard'),
    path('employee-details/', views.employee_detail, name='employee_detail'),
    path('employee/<int:id>/edit/', views.edit_employee, name='edit_employee'),
    path(
        'employee/<str:employee_id>/delete/',
        views.delete_employee,
        name='delete_employee',
    ),
    path(
        'hr/employee/<int:id>/edit/',
        views.hr_edit_employee,
        name='hr_edit_employee',
    ),
    path(
        'hr/employee/<int:id>/delete/',
        views.hr_delete_employee,
        name='hr_delete_employee',
    ),
    path(
        'forgot-password/',
        views.forgot_password,
        name='forgot_password',
    ),
]
