"""
URL Routing for Junctions and Traffic Endpoints
Strictly matches Section 10 Minimum Backend APIs.
"""
from django.urls import path
from junctions.views import (
    HealthCheckView,
    JunctionListCreateView,
    JunctionDetailView,
    JunctionStatusView,
    JunctionCommandView,
    JunctionHistoryView,
    JunctionQueuesView,
    JunctionTickView,
    JunctionResetView,
    SensorEventIngestionView,
    ControllerEventIngestionView,
)

urlpatterns = [
    # Health probe for UptimeRobot / Cloud Keep-Alive (/api/health)
    path("health", HealthCheckView.as_view(), name="health-check"),

    # 10.1 Junctions
    path("junctions", JunctionListCreateView.as_view(), name="junction-list-create"),
    path("junctions/<str:id>", JunctionDetailView.as_view(), name="junction-detail"),
    
    # 10.3 Junction Status
    path("junctions/<str:id>/status", JunctionStatusView.as_view(), name="junction-status"),
    
    # 10.4 Manual / Control Commands
    path("junctions/<str:id>/commands", JunctionCommandView.as_view(), name="junction-commands"),
    
    # 10.6 History
    path("junctions/<str:id>/history", JunctionHistoryView.as_view(), name="junction-history"),
    
    # Queue details & Evaluator convenience helpers
    path("junctions/<str:id>/queues", JunctionQueuesView.as_view(), name="junction-queues"),
    path("junctions/<str:id>/tick", JunctionTickView.as_view(), name="junction-tick"),
    path("junctions/<str:id>/reset", JunctionResetView.as_view(), name="junction-reset"),

    # 10.2 Sensor Events
    path("sensor-events", SensorEventIngestionView.as_view(), name="sensor-events"),

    # 10.5 Controller Events / Acknowledgements
    path("controller-events", ControllerEventIngestionView.as_view(), name="controller-events"),
]
