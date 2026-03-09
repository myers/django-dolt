"""Admin configuration for demo models."""

from django.contrib import admin

from .models import Category, Customer, Order, OrderItem, Product


# =============================================================================
# Inventory Admin (inventory_db)
# =============================================================================


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin for product categories."""

    list_display = ["name", "description", "created_at"]
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin for products."""

    list_display = ["sku", "name", "category", "price", "quantity_in_stock"]
    list_filter = ["category"]
    search_fields = ["sku", "name"]


# =============================================================================
# Orders Admin (orders_db)
# =============================================================================


class OrderItemInline(admin.TabularInline):  # type: ignore[type-arg]
    """Inline for order items."""

    model = OrderItem
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin for customers."""

    list_display = ["email", "first_name", "last_name", "created_at"]
    search_fields = ["email", "first_name", "last_name"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin for orders."""

    list_display = ["order_number", "customer", "status", "total_amount", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["order_number", "customer__email"]
    inlines = [OrderItemInline]
