"""Demo models for showcasing multi-database Dolt support.

This module defines models for two separate Dolt databases:
- Inventory models (inventory_db): Products and categories
- Order models (orders_db): Customers and orders
"""

from django.db import models


# =============================================================================
# Inventory Models (stored in inventory_db Dolt database)
# =============================================================================


class Category(models.Model):
    """Product category."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_category"
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """Product in inventory."""

    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_in_stock = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_product"

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"


# =============================================================================
# Order Models (stored in orders_db Dolt database)
# =============================================================================


class Customer(models.Model):
    """Customer who places orders."""

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders_customer"

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} <{self.email}>"


class Order(models.Model):
    """Customer order."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    order_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders_order"

    def __str__(self) -> str:
        return f"Order {self.order_number} - {self.customer.email}"


class OrderItem(models.Model):
    """Line item in an order."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    # Store product SKU as reference (cross-database, can't use ForeignKey)
    product_sku = models.CharField(max_length=50)
    product_name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "orders_orderitem"

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product_name}"

    @property
    def subtotal(self) -> float:
        """Calculate subtotal for this line item."""
        return float(self.quantity * self.unit_price)
