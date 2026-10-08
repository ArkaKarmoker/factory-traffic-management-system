import os
import sys
from django.apps import AppConfig


class JunctionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "junctions"

    def ready(self):
        # Do not start background worker during database management commands or tests
        skip_commands = {"migrate", "makemigrations", "test", "pytest", "collectstatic", "shell"}
        if any(cmd in sys.argv for cmd in skip_commands):
            return

        if "runserver" in sys.argv:
            if os.environ.get("RUN_MAIN") == "true" or "--noreload" in sys.argv:
                from junctions.background_worker import start_background_worker
                start_background_worker()
        else:
            from junctions.background_worker import start_background_worker
            start_background_worker()
