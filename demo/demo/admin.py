"""Custom admin site for the django-dolt demo using DoltAdminSite."""

from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from django_dolt.admin import DoltAdminSite, register_dolt_admin
from django_dolt.dolt_databases import get_dolt_databases

# Create a DoltAdminSite which provides:
# - Per-database sidebar grouping (Inventory (Dolt), Orders (Dolt))
# - Status and diff views for each database
dolt_admin_site = DoltAdminSite(name="admin")

# Register Django's built-in auth models
dolt_admin_site.register(User, UserAdmin)
dolt_admin_site.register(Group, GroupAdmin)

# Register Dolt admin views (branches, commits, remotes) for each database
for db_alias in get_dolt_databases():
    register_dolt_admin(db_alias, site=dolt_admin_site)
