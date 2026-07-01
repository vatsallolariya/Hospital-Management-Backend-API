from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

LOG_DIR = BASE_DIR / 'logs'  # noqa: F405
LOG_DIR.mkdir(exist_ok=True)

LOGGING['handlers']['file'] = {  # noqa: F405
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': LOG_DIR / 'django.log',
    'maxBytes': 10 * 1024 * 1024,  # 10 MB
    'backupCount': 5,
    'formatter': 'verbose',
}

LOGGING['root']['handlers'].append('file')  # noqa: F405
for _logger in LOGGING['loggers'].values():  # noqa: F405
    _logger['handlers'].append('file')
del _logger
