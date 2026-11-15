
"""
Django settings for emp_management project.
"""

from pathlib import Path
import os
import secrets

from django.core.exceptions import ImproperlyConfigured


# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path):
    """Load local defaults without overriding values set by the process."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key.lower().startswith('export '):
            key = key[7:].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _mail_setting(name):
    return os.environ.get(name, '').strip().strip('"').strip("'").replace(' ', '')


_load_env_file(BASE_DIR / '.env')


# Security settings
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').strip().lower() in {
    '1',
    'true',
    'yes',
    'on',
}
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            'Set DJANGO_SECRET_KEY when DEBUG is disabled.'
        )
    SECRET_KEY = secrets.token_urlsafe(50)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
    if host.strip()
]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']
elif not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'Set DJANGO_ALLOWED_HOSTS when DEBUG is disabled.'
    )


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'home',
    'administration',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'emp_management.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'emp_management.wsgi.application'


# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


# Static files

STATIC_URL = 'static/'


# Gmail SMTP Email Configuration

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'

EMAIL_PORT = 587

EMAIL_USE_TLS = True

# Gmail only accepts a 16-character App Password here, not the normal account password.
# Put them in the environment or in a project .env file:
# DJANGO_GMAIL_ADDRESS=you@gmail.com
# DJANGO_GMAIL_APP_PASSWORD=abcdefghijklmnop
EMAIL_HOST_USER = _mail_setting('DJANGO_GMAIL_ADDRESS')

EMAIL_HOST_PASSWORD = _mail_setting('DJANGO_GMAIL_APP_PASSWORD')

DEFAULT_FROM_EMAIL = os.environ.get(
    'DJANGO_DEFAULT_FROM_EMAIL',
    EMAIL_HOST_USER,
)

EMAIL_TIMEOUT = 10


# Media files

MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'
