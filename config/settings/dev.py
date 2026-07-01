from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

LOGGING['handlers']['console']['formatter'] = 'verbose'  # noqa: F405
LOGGING['root']['level'] = 'DEBUG'  # noqa: F405
for _logger in ('django', 'accounts', 'organizations', 'doctors', 'visits', 'dashboard', 'reports'):
    LOGGING['loggers'][_logger]['level'] = 'DEBUG'  # noqa: F405
del _logger
