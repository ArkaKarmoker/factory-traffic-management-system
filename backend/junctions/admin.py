"""
Django Admin Configuration for Factory Traffic Management System
Registers Junctions, Priority Queues, Idempotency Events, Controller Commands, and Audit Trail.
"""
from django.contrib import admin
from junctions.models import (
    Junction,
    VehicleQueueItem,
    ProcessedEvent,
    ControllerCommand,
    AuditLog,
)


@admin.register(Junction)
class JunctionAdmin(admin.ModelAdmin):
    list_display = (
        "junction_id",
        "name",
        "mode",
        "current_phase",
        "transition_step",
        "controller_status",
        "emergency_active",
        "updated_at",
    )
    list_filter = ("mode", "current_phase", "controller_status", "emergency_active")
    search_fields = ("junction_id", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(VehicleQueueItem)
class VehicleQueueItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "junction",
        "direction",
        "vehicle_id",
        "vehicle_type",
        "sequence_no",
        "arrived_at",
    )
    list_filter = ("junction", "direction", "vehicle_type")
    search_fields = ("vehicle_id", "junction__junction_id")
    ordering = ("-arrived_at",)


@admin.register(ProcessedEvent)
class ProcessedEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_id",
        "junction_id",
        "direction",
        "event_type",
        "vehicle_id",
        "sequence_no",
        "processed_at",
    )
    list_filter = ("junction_id", "event_type", "direction")
    search_fields = ("event_id", "vehicle_id")
    ordering = ("-processed_at",)


@admin.register(ControllerCommand)
class ControllerCommandAdmin(admin.ModelAdmin):
    list_display = (
        "command_id",
        "junction",
        "direction",
        "requested_state",
        "actual_state",
        "status",
        "dispatched_at",
        "acked_at",
    )
    list_filter = ("status", "requested_state", "direction")
    search_fields = ("command_id", "junction__junction_id")
    ordering = ("-dispatched_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "timestamp",
        "junction_id",
        "event_type",
        "direction",
        "previous_state",
        "new_state",
        "command_id",
    )
    list_filter = ("junction_id", "event_type", "direction")
    search_fields = ("event_type", "command_id")
    ordering = ("-timestamp",)
    readonly_fields = ("timestamp",)
