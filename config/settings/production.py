import os

from .base import *  # noqa: F403

DEBUG = False

_raw_hosts = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]
ALLOWED_HOSTS = _raw_hosts[:]
for h in _raw_hosts:
    if not h.startswith('.') and not h.startswith('*') and '.' in h:
        ALLOWED_HOSTS.append(f'.{h}')

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'sslmode': 'require',
        },
    }
}

# Security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

_csrf_origins = []
for h in _raw_hosts:
    _csrf_origins.append(f'https://{h}')
    if not h.startswith('*.') and not h.startswith('.') and '.' in h:
        _csrf_origins.append(f'https://*.{h}')
CSRF_TRUSTED_ORIGINS = _csrf_origins

CORS_ALLOWED_ORIGIN_REGEXES = [
    rf'https://[\w-]+\.{h.replace(".", r"\.")}' for h in _raw_hosts
    if not h.startswith('*') and '.' in h
]

CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
