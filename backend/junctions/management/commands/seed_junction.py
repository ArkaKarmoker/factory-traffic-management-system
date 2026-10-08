"""
Database Seeding Command
Initializes Junction A, initial queues, and operator auth credentials.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.conf import settings
from junctions.models import Junction, VehicleQueueItem, AuditLog
from junctions.services import JunctionService
from traffic_engine.enums import Direction, VehicleType


class Command(BaseCommand):
    help = "Seeds database with Junction A, realistic queue vehicles, and operator token."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Factory Traffic Management System...")

        # 1. Initialize Junction A
        junction = JunctionService.get_or_create_default_junction("A")
        self.stdout.write(self.style.SUCCESS(f"Initialized {junction}"))

        # 2. Seed initial vehicle queues
        VehicleQueueItem.objects.filter(junction=junction).delete()
        initial_vehicles = [
            ("NORTH", "VH-101", VehicleType.FORKLIFT.value, 1),
            ("NORTH", "VH-102", VehicleType.TRUCK.value, 2),
            ("SOUTH", "VH-201", VehicleType.EMPLOYEE_VEHICLE.value, 1),
            ("EAST", "VH-301", VehicleType.TRUCK.value, 1),
            ("EAST", "VH-302", VehicleType.FORKLIFT.value, 2),
            ("EAST", "VH-303", VehicleType.FORKLIFT.value, 3),
        ]

        for direction, vid, vtype, seq in initial_vehicles:
            VehicleQueueItem.objects.create(
                junction=junction,
                direction=direction,
                vehicle_id=vid,
                vehicle_type=vtype,
                sequence_no=seq,
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(initial_vehicles)} initial vehicles in queues."))

        # 3. Create Default Admin User and DRF Token
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@factory.local", "is_staff": True, "is_superuser": True},
        )
        admin_user.set_password("AdminPass123!")
        admin_user.save()

        token_key = getattr(settings, "ADMIN_API_TOKEN", "factory-admin-token-2026")
        Token.objects.filter(user=admin_user).delete()
        Token.objects.create(user=admin_user, key=token_key)

        self.stdout.write(self.style.SUCCESS(f"Operator Auth Token configured: {token_key}"))
        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
