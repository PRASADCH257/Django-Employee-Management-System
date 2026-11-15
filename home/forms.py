
from django import forms
from django.core.exceptions import ValidationError
from home.models import Employee


def _validate_upload(upload, label, extensions, max_size):
    if upload is None:
        return

    extension = upload.name.rsplit('.', 1)[-1].lower()
    if '.' not in upload.name or extension not in extensions:
        allowed_types = ', '.join(f'.{item}' for item in extensions)
        raise ValidationError(
            f'{label} must use one of these file types: {allowed_types}.'
        )

    if upload.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        raise ValidationError(
            f'{label} must be no larger than {max_size_mb} MB.'
        )


def _validate_non_privileged_role(role):
    if (role or '').strip().upper() in {'ADMIN', 'MANAGER', 'HR'}:
        raise ValidationError(
            'Reserved account roles can only be assigned by an administrator.'
        )
    return role


class EmployeeRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Employee
        fields = [
            'full_name',
            'username',
            'email',
            'phone',
            'address',
            'photo',
            'resume',
        ]

    def clean_username(self):
        username = self.cleaned_data['username']
        if Employee.objects.filter(username__iexact=username).exists():
            raise ValidationError('This username is already registered.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if Employee.objects.filter(email__iexact=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data


class AdminEmployeeEditForm(forms.ModelForm):

    class Meta:
        model = Employee

        fields = [
            'employee_id',
            'full_name',
            'username',
            'email',
            'phone',
            'address',
            'photo',
            'resume',
            'document',
            'video',
            'account_type',
            'salary',
            'role',
            'department',
            'current_project',
            'team_number',
        ]

        widgets = {
            'employee_id': forms.TextInput(attrs={
                'class': 'form-control',
            }),

            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter full name'
            }),

            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter username'
            }),

            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email'
            }),

            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),

            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter address'
            }),

            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.webp'
            }),

            'resume': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf'
            }),

            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx'
            }),

            'video': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.mp4,.mov,.webm'
            }),

            'account_type': forms.Select(attrs={
                'class': 'form-control'
            }),

            'salary': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '0',
                'placeholder': 'e.g. 100000'
            }),

            'role': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter employee position'
            }),

            'department': forms.Select(attrs={
                'class': 'form-control'
            }),

            'current_project': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter current project'
            }),

            'team_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter team number'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['account_type'].choices = [
            ('EMPLOYEE', 'Employee'),
            ('HR', 'HR'),
            ('MANAGER', 'Manager'),
        ]
        if self.instance.account_type == 'ADMIN':
            self.fields['account_type'].choices.append(('ADMIN', 'Admin'))

        self.fields['photo'].help_text = (
            'JPEG, PNG, or WebP. Maximum size: 5 MB.'
        )
        self.fields['resume'].help_text = 'PDF only. Maximum size: 10 MB.'
        self.fields['document'].help_text = (
            'PDF, DOC, or DOCX. Maximum size: 10 MB.'
        )
        self.fields['video'].help_text = (
            'MP4, MOV, or WebM. Maximum size: 50 MB.'
        )

    def clean_photo(self):
        uploaded_file = self.files.get('photo')
        _validate_upload(
            uploaded_file,
            'Profile photo',
            ('jpg', 'jpeg', 'png', 'webp'),
            5 * 1024 * 1024,
        )
        return self.cleaned_data['photo']

    def clean_resume(self):
        uploaded_file = self.files.get('resume')
        _validate_upload(
            uploaded_file,
            'Resume',
            ('pdf',),
            10 * 1024 * 1024,
        )
        if uploaded_file:
            position = uploaded_file.tell()
            header = uploaded_file.read(1024)
            uploaded_file.seek(position)
            if b'%PDF-' not in header:
                raise ValidationError('Resume must be a valid PDF file.')
        return self.cleaned_data['resume']

    def clean_document(self):
        _validate_upload(
            self.files.get('document'),
            'Document',
            ('pdf', 'doc', 'docx'),
            10 * 1024 * 1024,
        )
        return self.cleaned_data['document']

    def clean_video(self):
        _validate_upload(
            self.files.get('video'),
            'Video',
            ('mp4', 'mov', 'webm'),
            50 * 1024 * 1024,
        )
        return self.cleaned_data['video']

    def clean_employee_id(self):
        employee_id = self.cleaned_data['employee_id']

        existing = Employee.objects.filter(
            employee_id__iexact=employee_id
        ).exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError(
                'This Employee ID is already used.'
            )

        return employee_id

    def clean_username(self):
        username = self.cleaned_data['username']

        existing = Employee.objects.filter(
            username__iexact=username
        ).exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError(
                'This username is already used.'
            )

        return username

    def clean_email(self):
        email = self.cleaned_data['email']

        existing = Employee.objects.filter(
            email__iexact=email
        ).exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError(
                'This email is already used.'
            )

        return email


class ManagerEmployeeEditForm(AdminEmployeeEditForm):
    """Fields managers can update without changing the employee ID."""

    class Meta(AdminEmployeeEditForm.Meta):
        fields = AdminEmployeeEditForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee_id'].disabled = True
        self.fields['account_type'].choices = [
            ('EMPLOYEE', 'Employee'),
            ('HR', 'HR'),
        ]
        if self.instance.account_type not in {'EMPLOYEE', 'HR'}:
            self.fields['account_type'].choices.append(
                (
                    self.instance.account_type,
                    self.instance.get_account_type_display(),
                )
            )

    def clean_role(self):
        return _validate_non_privileged_role(self.cleaned_data.get('role'))


class EmployeeProfessionalEditForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'salary',
            'role',
            'department',
            'current_project',
            'team_number',
        ]
        widgets = {
            'salary': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'role': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'current_project': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'team_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_role(self):
        return _validate_non_privileged_role(self.cleaned_data.get('role'))
