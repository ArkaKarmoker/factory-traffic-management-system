"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()

# Ensure database tables exist, default Junction A is seeded, and static files are collected on cloud boot
try:
    from django.core.management import call_command
    call_command("migrate", interactive=False)
    call_command("seed_junction")
    call_command("collectstatic", interactive=False)
except Exception as e:
    import logging
    logging.getLogger("core.wsgi").warning(f"WSGI startup notice: {e}")


