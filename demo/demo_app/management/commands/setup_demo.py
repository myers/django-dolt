"""Management command to set up the demo application with sample data."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connections

from django_dolt import dolt_add_and_commit

from demo_app.models import Category, Customer, Order, OrderItem, Product


class Command(BaseCommand):
    """Set up demo databases with sample data."""

    help = "Set up demo databases and populate with sample data"

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        self.stdout.write("Setting up demo databases...")

        # Create databases if they don't exist
        self._create_databases()

        # Create tables via migrations
        self._run_migrations()

        # Populate sample data
        self._create_inventory_data()
        self._create_orders_data()

        self.stdout.write(self.style.SUCCESS("Demo setup complete!"))
        self.stdout.write("\nYou can now:")
        self.stdout.write("  1. Run: python manage.py runserver")
        self.stdout.write("  2. Visit: http://localhost:8000/")
        self.stdout.write("  3. Admin: http://localhost:8000/admin/")
        self.stdout.write("     (Create superuser with: python manage.py createsuperuser)")

    def _create_databases(self) -> None:
        """Create the Dolt databases if they don't exist."""
        self.stdout.write("Creating Dolt databases...")

        # Connect to the Dolt server and create databases
        # We need to use a raw connection since the databases might not exist yet
        from django.conf import settings

        import pymysql

        conn = pymysql.connect(
            host=settings.DOLT_HOST,
            port=settings.DOLT_PORT,
            user=settings.DOLT_USER,
            password=settings.DOLT_PASSWORD,
        )
        cursor = conn.cursor()

        try:
            cursor.execute("CREATE DATABASE IF NOT EXISTS inventory")
            self.stdout.write("  Created/verified 'inventory' database")
        except Exception as e:
            self.stdout.write(f"  Note: {e}")

        try:
            cursor.execute("CREATE DATABASE IF NOT EXISTS orders")
            self.stdout.write("  Created/verified 'orders' database")
        except Exception as e:
            self.stdout.write(f"  Note: {e}")

        cursor.close()
        conn.close()

    def _run_migrations(self) -> None:
        """Run migrations for both Dolt databases."""
        from django.core.management import call_command

        self.stdout.write("Running migrations...")

        # Create tables directly since Dolt doesn't need Django migrations
        # for these simple models

        # Inventory tables
        with connections["inventory_db"].cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory_category (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    created_at DATETIME NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory_product (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    sku VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    category_id BIGINT NOT NULL,
                    price DECIMAL(10, 2) NOT NULL,
                    quantity_in_stock INT DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (category_id) REFERENCES inventory_category(id)
                )
            """)
        self.stdout.write("  Created inventory tables")

        # Orders tables
        with connections["orders_db"].cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders_customer (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(254) UNIQUE NOT NULL,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    phone VARCHAR(20),
                    created_at DATETIME NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders_order (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    customer_id BIGINT NOT NULL,
                    order_number VARCHAR(50) UNIQUE NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    total_amount DECIMAL(10, 2) DEFAULT 0,
                    notes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES orders_customer(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders_orderitem (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    order_id BIGINT NOT NULL,
                    product_sku VARCHAR(50) NOT NULL,
                    product_name VARCHAR(200) NOT NULL,
                    quantity INT DEFAULT 1,
                    unit_price DECIMAL(10, 2) NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders_order(id)
                )
            """)
        self.stdout.write("  Created orders tables")

    def _create_inventory_data(self) -> None:
        """Create sample inventory data."""
        self.stdout.write("Creating inventory data...")

        # Check if data already exists
        if Category.objects.using("inventory_db").exists():
            self.stdout.write("  Inventory data already exists, skipping...")
            return

        # Create categories
        electronics = Category.objects.using("inventory_db").create(
            name="Electronics",
            description="Electronic devices and accessories",
        )
        clothing = Category.objects.using("inventory_db").create(
            name="Clothing",
            description="Apparel and fashion items",
        )
        books = Category.objects.using("inventory_db").create(
            name="Books",
            description="Books and publications",
        )

        # Create products
        products_data = [
            ("ELEC-001", "Wireless Mouse", electronics, Decimal("29.99"), 150),
            ("ELEC-002", "USB-C Hub", electronics, Decimal("49.99"), 75),
            ("ELEC-003", "Mechanical Keyboard", electronics, Decimal("89.99"), 50),
            ("CLTH-001", "Cotton T-Shirt", clothing, Decimal("19.99"), 200),
            ("CLTH-002", "Denim Jeans", clothing, Decimal("59.99"), 100),
            ("CLTH-003", "Hoodie", clothing, Decimal("39.99"), 80),
            ("BOOK-001", "Python Programming", books, Decimal("44.99"), 30),
            ("BOOK-002", "Database Design", books, Decimal("39.99"), 25),
            ("BOOK-003", "Web Development", books, Decimal("49.99"), 40),
        ]

        for sku, name, category, price, qty in products_data:
            Product.objects.using("inventory_db").create(
                sku=sku,
                name=name,
                category=category,
                price=price,
                quantity_in_stock=qty,
            )

        self.stdout.write(f"  Created {len(products_data)} products in 3 categories")

        # Commit the initial data
        try:
            dolt_add_and_commit(
                message="Initial inventory data",
                author="Demo Setup <demo@example.com>",
                using="inventory_db",
            )
            self.stdout.write("  Committed inventory data to Dolt")
        except Exception as e:
            self.stdout.write(f"  Note: Could not commit - {e}")

    def _create_orders_data(self) -> None:
        """Create sample orders data."""
        self.stdout.write("Creating orders data...")

        # Check if data already exists
        if Customer.objects.using("orders_db").exists():
            self.stdout.write("  Orders data already exists, skipping...")
            return

        # Create customers
        customers_data = [
            ("alice@example.com", "Alice", "Johnson", "555-0101"),
            ("bob@example.com", "Bob", "Smith", "555-0102"),
            ("carol@example.com", "Carol", "Williams", "555-0103"),
        ]

        customers = []
        for email, first, last, phone in customers_data:
            customer = Customer.objects.using("orders_db").create(
                email=email,
                first_name=first,
                last_name=last,
                phone=phone,
            )
            customers.append(customer)

        # Create orders
        orders_data = [
            (customers[0], "ORD-2024-001", "delivered", [
                ("ELEC-001", "Wireless Mouse", 2, Decimal("29.99")),
                ("BOOK-001", "Python Programming", 1, Decimal("44.99")),
            ]),
            (customers[1], "ORD-2024-002", "shipped", [
                ("CLTH-001", "Cotton T-Shirt", 3, Decimal("19.99")),
                ("CLTH-002", "Denim Jeans", 1, Decimal("59.99")),
            ]),
            (customers[2], "ORD-2024-003", "processing", [
                ("ELEC-003", "Mechanical Keyboard", 1, Decimal("89.99")),
            ]),
            (customers[0], "ORD-2024-004", "pending", [
                ("ELEC-002", "USB-C Hub", 1, Decimal("49.99")),
                ("BOOK-002", "Database Design", 1, Decimal("39.99")),
            ]),
        ]

        for customer, order_num, status, items in orders_data:
            total = sum(qty * price for _, _, qty, price in items)
            order = Order.objects.using("orders_db").create(
                customer=customer,
                order_number=order_num,
                status=status,
                total_amount=total,
            )
            for sku, name, qty, price in items:
                OrderItem.objects.using("orders_db").create(
                    order=order,
                    product_sku=sku,
                    product_name=name,
                    quantity=qty,
                    unit_price=price,
                )

        self.stdout.write(f"  Created {len(orders_data)} orders for {len(customers)} customers")

        # Commit the initial data
        try:
            dolt_add_and_commit(
                message="Initial orders data",
                author="Demo Setup <demo@example.com>",
                using="orders_db",
            )
            self.stdout.write("  Committed orders data to Dolt")
        except Exception as e:
            self.stdout.write(f"  Note: Could not commit - {e}")
