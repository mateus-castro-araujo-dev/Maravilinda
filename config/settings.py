import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("SECRET_KEY não definida no .env. O servidor não pode iniciar em produção sem ela.")
    SECRET_KEY = 'django-insecure-temporaria-apenas-para-dev'

_allowed = os.environ.get('ALLOWED_HOSTS', 'lojamaravilinda.com.br,www.lojamaravilinda.com.br,localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
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

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.globals',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_USER_MODEL = 'core.User'

AUTHENTICATION_BACKENDS = [
    'core.auth_backends.EmailBackend',
]

if os.environ.get('DATABASE_URL'):
    import urllib.parse
    _url = urllib.parse.urlparse(os.environ['DATABASE_URL'])
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _url.path.lstrip('/'),
            'USER': _url.username,
            'PASSWORD': _url.password,
            'HOST': _url.hostname,
            'PORT': _url.port or 5432,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = False

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG   # HTTPS only em produção
CSRF_COOKIE_SECURE = not DEBUG      # HTTPS only em produção
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MAX_UPLOAD_SIZE = 16 * 1024 * 1024

# Loja config
WHATSAPP_NUMBER = '5586994156794'
CORREIOS_CEP_ORIGEM = '64218440'
MELHOR_ENVIO_TOKEN = os.environ.get('MELHOR_ENVIO_TOKEN', 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiOTU5OTZiOTBiMzhlYWIyMjNmMjliZTM0N2Q5YTNmMmFjNjBhYWI2YTZmZDYyZTFjNWYxYWFiNDdjZjg5OGY2NmVlZDAwMGRhMzBmNTBkYzUiLCJpYXQiOjE3Nzg4OTk0ODcuMzMzMDMyLCJuYmYiOjE3Nzg4OTk0ODcuMzMzMDM0LCJleHAiOjE4MTA0MzU0ODcuMzIzNDUxLCJzdWIiOiJhMWNhMzkwMy03NWY3LTRiNGEtOWI2Ny1iMTE3NTVkN2YxNmYiLCJzY29wZXMiOlsic2hpcHBpbmctY2FsY3VsYXRlIl19.QraPu0JSpmTSr0khHP7nr7Dn12ynzmWeU1XInnrqOk9YA-6xQybZt4Y0psNWjgSsWRx4W86uls-6wK8b9g09_8MyltGFPSkYdN-IBOWl8KZP7NG3kjXL2yMC1mWaekSFnNZenPsDQzZ7pLiPbMCaXEdyEVZIRixAJuj4UJKJa3J5TTfuBZB0CswkgUX8zacu7Sr296vouuDypfAoYWNEzmUZepF3jZan0hoBpBo1zMf3SfoWrnfpJwh0B9EGWSWv6yIV-GIAUNTEE63Wxhl7N4usUbnBDaErLw9mUq1GJ6PzTPVkFvlShbsVKmrDF5vL1IA0SCEwYl0g0p_YJ2kRqlQXOZNxlvuZ94d-iYhvXFNLKvLhoGV2m6LW9vqUR4-t_rVskh3XXgU-d5xJ1y4cc0KEgXjUGupOKyyfQTo3ABmT-KfWGp0Xy425IsjTBKhoxoNjiOY4HniwIh8Dcqh4Q82oFM6banhXFLj5EWEEeGaiBHdrMARW7XAuzrJm9_1NAmTT0YC37jlaVQX5nQV86h-SRQAOfl20mO__g7yfqD9f_8TOosHnwEExbqQccQbCJ0fGBRX-fHYZrey7bho5rQSz0t9QXEaMznx5yKXaw1-LjqCgtZVhmXmSYq2fHwAXs9l8FasvyrfGfaODoqUbkWrnw8im2D-TeP05X0WY84Y')
MELHOR_ENVIO_SANDBOX = os.environ.get('MELHOR_ENVIO_SANDBOX', 'false').lower() == 'true'
INSTAGRAM_USER = 'maravilinda_s.o'
FACEBOOK_USER = 'maravilinda.no'
PIX_KEY = os.environ.get('PIX_KEY', 'Lojamaravilindastore@gmail.com')
PIX_NAME = 'Maravilinda Moda'
PIX_CITY = 'Parnaiba'

# ── Mercado Pago ─────────────────────────────────────────────────────────────
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')
MERCADOPAGO_PUBLIC_KEY = os.environ.get('MERCADOPAGO_PUBLIC_KEY', '')
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get('MERCADOPAGO_WEBHOOK_SECRET', '')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')

# ── Email (reset de senha) ───────────────────────────────────────────────────
# Em dev, links de reset aparecem no terminal. Em produção, configure SMTP via env.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Maravilinda <nao-responda@maravilinda.com.br>')
