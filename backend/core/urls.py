"""
Root URL Configuration for core project.
Routes /api/ to junctions app and provides Swagger/OpenAPI documentation.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Admin Interface
    path("admin/", admin.site.urls),

    # Traffic Management REST APIs
    path("api/", include("junctions.urls")),

    # OpenAPI 3.0 Schema & Interactive Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
