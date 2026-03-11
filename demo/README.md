# Django-Dolt Demo Application

This demo application showcases Django-Dolt's multi-database support with two separate Dolt databases:

- **Inventory Database** (`inventory`) - Tracks products and categories
- **Orders Database** (`orders`) - Tracks customers and orders

Each database has its own version history, and you can commit changes independently.

## Prerequisites

- Python 3.12+
- Docker (for running Dolt server)
- MySQL client libraries (for mysqlclient package)

On macOS:
```bash
brew install mysql-client pkg-config
export PKG_CONFIG_PATH="/opt/homebrew/opt/mysql-client/lib/pkgconfig"
```

## Quick Start

1. **Start the Dolt server:**
   ```bash
   docker-compose up -d
   ```

2. **Install dependencies:**
   ```bash
   cd demo
   uv pip install -e "..[demo]"
   ```

3. **Set up the demo databases:**
   ```bash
   python manage.py setup_demo
   ```

4. **Create a superuser for admin access:**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

6. **Open in browser:**
   - Demo app: http://localhost:8000/
   - Admin panel: http://localhost:8000/admin/

## Features Demonstrated

### Multi-Database Support

The demo uses two Dolt databases configured in `demo/settings.py`:

```python
DATABASES = {
    "default": {...},  # SQLite for Django internals
    "inventory": {...},  # Dolt database for inventory
    "orders": {...},  # Dolt database for orders
}
```

### Database Routing

Models are routed to their respective databases using `demo/routers.py`:

- `Category` and `Product` models → `inventory`
- `Customer`, `Order`, and `OrderItem` models → `orders`

### Dolt Version Control

Each database page shows:
- Current uncommitted changes (Dolt status)
- Recent commit history
- Commit form to save changes with a message

### Admin Integration

Django admin automatically shows Branch, Commit, and Remote models for each detected Dolt database, organized in separate sections.

## Project Structure

```
demo/
├── manage.py
├── demo/
│   ├── settings.py      # Django settings with multiple Dolt databases
│   ├── routers.py       # Database routing for models
│   └── urls.py
├── demo_app/
│   ├── models.py        # Inventory and Orders models
│   ├── admin.py         # Multi-database admin configuration
│   ├── views.py         # Dashboard views with Dolt integration
│   └── management/
│       └── commands/
│           └── setup_demo.py  # Initial data setup command
└── templates/
    └── demo_app/
        ├── index.html       # Home dashboard
        ├── inventory.html   # Inventory dashboard
        └── orders.html      # Orders dashboard
```

## Making Changes

1. Add/edit data via the admin panel or views
2. View uncommitted changes on the respective dashboard
3. Enter a commit message and click "Commit"
4. Changes are versioned in the Dolt database

## Stopping the Demo

```bash
docker-compose down
```

To also remove the data volumes:
```bash
docker-compose down -v
```
