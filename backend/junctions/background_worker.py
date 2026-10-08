"""
Non-blocking Background Transition Worker
Advances state machine timers in a lightweight background daemon thread without blocking HTTP request threads.
"""
import threading
import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_worker_thread = None
_stop_event = threading.Event()


def _run_worker_loop():
    from django.db import connection
    from junctions.models import Junction
    from junctions.services import JunctionService

    logger.info("Traffic background transition worker started.")
    while not _stop_event.is_set():
        try:
            junction_ids = list(Junction.objects.values_list("junction_id", flat=True))
            for j_id in junction_ids:
                JunctionService.step_transition_tick(j_id)
        except Exception as e:
            # Prevent thread death on transient db lock
            logger.debug(f"Worker tick notice: {e}")
        finally:
            connection.close()
        _stop_event.wait(1.0)


def start_background_worker():
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _stop_event.clear()
        _worker_thread = threading.Thread(target=_run_worker_loop, daemon=True, name="TrafficTransitionWorker")
        _worker_thread.start()


def stop_background_worker():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        _stop_event.set()
        _worker_thread.join(timeout=2.0)
        _worker_thread = None
