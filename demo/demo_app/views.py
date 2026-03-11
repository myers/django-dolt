"""Views for the demo application."""

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

import django_dolt
from django_dolt import dolt_add_and_commit, dolt_log, dolt_status

from .models import Category, Customer, Order, Product


def index(request: HttpRequest) -> HttpResponse:
    """Home page showing overview of both databases."""
    # Get Dolt database info
    dolt_databases = django_dolt.get_dolt_databases()

    # Get counts from each database
    inventory_stats = {
        "categories": Category.objects.using("inventory_db").count(),
        "products": Product.objects.using("inventory_db").count(),
    }

    orders_stats = {
        "customers": Customer.objects.using("orders_db").count(),
        "orders": Order.objects.using("orders_db").count(),
    }

    context = {
        "dolt_databases": dolt_databases,
        "inventory_stats": inventory_stats,
        "orders_stats": orders_stats,
    }
    return render(request, "demo_app/index.html", context)


def inventory_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard for inventory database."""
    products = Product.objects.using("inventory_db").select_related("category").all()
    categories = Category.objects.using("inventory_db").all()

    # Get Dolt status and recent commits
    try:
        status = dolt_status(using="inventory_db")
        commits = dolt_log(limit=10, using="inventory_db")
    except Exception:
        status = []
        commits = []

    context = {
        "products": products,
        "categories": categories,
        "dolt_status": status,
        "dolt_commits": commits,
        "db_alias": "inventory_db",
    }
    return render(request, "demo_app/inventory.html", context)


def orders_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard for orders database."""
    orders = (
        Order.objects.using("orders_db")
        .select_related("customer")
        .prefetch_related("items")
        .all()
    )
    customers = Customer.objects.using("orders_db").all()

    # Get Dolt status and recent commits
    try:
        status = dolt_status(using="orders_db")
        commits = dolt_log(limit=10, using="orders_db")
    except Exception:
        status = []
        commits = []

    context = {
        "orders": orders,
        "customers": customers,
        "dolt_status": status,
        "dolt_commits": commits,
        "db_alias": "orders_db",
    }
    return render(request, "demo_app/orders.html", context)


def dolt_commit(request: HttpRequest, db_alias: str) -> HttpResponse:
    """Commit changes to a Dolt database."""
    if request.method != "POST":
        return HttpResponseRedirect(reverse("index"))

    message = request.POST.get("message", "Manual commit from demo app")

    user = request.user
    if user.is_authenticated:
        author = f"{user.get_full_name() or user.username} <{user.email or user.username + '@localhost'}>"
    else:
        author = "Demo App <demo@example.com>"
    try:
        commit_hash = dolt_add_and_commit(
            message=message,
            author=author,
            using=db_alias,
        )
        if commit_hash:
            messages.success(request, f"Committed to {db_alias}: {commit_hash[:8]}")
        else:
            messages.info(request, f"No changes to commit in {db_alias}")
    except Exception as e:
        messages.error(request, f"Commit failed: {e}")

    # Redirect to 'next' param if provided, otherwise back to dashboard
    next_url = request.POST.get("next")
    if next_url:
        return HttpResponseRedirect(next_url)
    if db_alias == "inventory_db":
        return HttpResponseRedirect(reverse("inventory"))
    elif db_alias == "orders_db":
        return HttpResponseRedirect(reverse("orders"))
    return HttpResponseRedirect(reverse("index"))
