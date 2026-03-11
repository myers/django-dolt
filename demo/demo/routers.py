"""Database routers for the demo application.

Routes models to their appropriate Dolt databases based on db_table prefix.
"""

from typing import Any


class DemoRouter:
    """Route demo models to their respective Dolt databases."""

    def _get_db_for_model(self, model: type) -> str | None:
        """Determine database based on db_table prefix."""
        db_table = model._meta.db_table
        if db_table.startswith("inventory_"):
            return "inventory"
        if db_table.startswith("orders_"):
            return "orders"
        return None

    def db_for_read(self, model: type, **hints: Any) -> str | None:
        """Route read operations to the appropriate database."""
        return self._get_db_for_model(model)

    def db_for_write(self, model: type, **hints: Any) -> str | None:
        """Route write operations to the appropriate database."""
        return self._get_db_for_model(model)

    def allow_relation(
        self, obj1: Any, obj2: Any, **hints: Any
    ) -> bool | None:
        """Allow relations within the same database."""
        db1 = self._get_db_for_model(type(obj1))
        db2 = self._get_db_for_model(type(obj2))
        if db1 and db2:
            return db1 == db2
        return None

    def allow_migrate(
        self, db: str, app_label: str, model_name: str | None = None, **hints: Any
    ) -> bool | None:
        """Control which models can be migrated to which database."""
        if app_label == "demo_app" and model_name:
            # Route demo_app models to their Dolt database based on db_table prefix
            from django.apps import apps

            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                return None
            target_db = self._get_db_for_model(model)
            if target_db:
                return db == target_db
            return None
        # Default apps go to default database only
        if db == "default":
            return app_label != "demo_app"
        return None
