"""Views for the demo application."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

import django_dolt
from django_dolt import dolt_add_and_commit, dolt_log, dolt_status
from django_dolt.decorators import dolt_autocommit, get_author_from_request

from .models import Category, Customer, Order, Product, ProductComment


def index(request: HttpRequest) -> HttpResponse:
    """Home page showing overview of both databases."""
    # Get Dolt database info
    dolt_databases = django_dolt.get_dolt_databases()

    # Get counts from each database
    inventory_stats = {
        "categories": Category.objects.using("inventory").count(),
        "products": Product.objects.using("inventory").count(),
    }

    orders_stats = {
        "customers": Customer.objects.using("orders").count(),
        "orders": Order.objects.using("orders").count(),
    }

    context = {
        "dolt_databases": dolt_databases,
        "inventory_stats": inventory_stats,
        "orders_stats": orders_stats,
    }
    return render(request, "demo_app/index.html", context)


def inventory_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard for inventory database."""
    products = Product.objects.using("inventory").select_related("category").all()
    categories = Category.objects.using("inventory").all()

    # Get Dolt status and recent commits
    try:
        status = dolt_status(using="inventory")
        commits = dolt_log(limit=10, using="inventory")
    except Exception:
        status = []
        commits = []

    context = {
        "products": products,
        "categories": categories,
        "dolt_status": status,
        "dolt_commits": commits,
        "db_alias": "inventory",
    }
    return render(request, "demo_app/inventory.html", context)


def orders_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard for orders database."""
    orders = (
        Order.objects.using("orders")
        .select_related("customer")
        .prefetch_related("items")
        .all()
    )
    customers = Customer.objects.using("orders").all()

    # Get Dolt status and recent commits
    try:
        status = dolt_status(using="orders")
        commits = dolt_log(limit=10, using="orders")
    except Exception:
        status = []
        commits = []

    context = {
        "orders": orders,
        "customers": customers,
        "dolt_status": status,
        "dolt_commits": commits,
        "db_alias": "orders",
    }
    return render(request, "demo_app/orders.html", context)


def dolt_commit(request: HttpRequest, db_alias: str) -> HttpResponse:
    """Commit changes to a Dolt database."""
    if request.method != "POST":
        return HttpResponseRedirect(reverse("index"))

    message = request.POST.get("message", "Manual commit from demo app")
    author = get_author_from_request(request)

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
    if db_alias == "inventory":
        return HttpResponseRedirect(reverse("inventory"))
    elif db_alias == "orders":
        return HttpResponseRedirect(reverse("orders"))
    return HttpResponseRedirect(reverse("index"))


def product_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Product detail page showing comments."""
    product = get_object_or_404(Product.objects.using("inventory"), pk=pk)
    comments = ProductComment.objects.using("inventory").filter(product=product)
    context = {
        "product": product,
        "comments": comments,
    }
    return render(request, "demo_app/product_detail.html", context)


@login_required
@dolt_autocommit(
    using="inventory",
    message=lambda r: f"Add comment on product (by {r.user.username})",
)
def add_product_comment(request: HttpRequest, pk: int) -> HttpResponse:
    """Add a comment to a product — auto-committed by @dolt_autocommit."""
    product = get_object_or_404(Product.objects.using("inventory"), pk=pk)
    if request.method != "POST":
        return HttpResponseRedirect(reverse("product_detail", args=[pk]))

    body = request.POST.get("body", "").strip()
    if not body:
        messages.error(request, "Comment cannot be empty.")
        return HttpResponseRedirect(reverse("product_detail", args=[pk]))

    ProductComment.objects.using("inventory").create(
        product=product,
        author=request.user.get_full_name() or request.user.username,
        body=body,
    )
    messages.success(request, "Comment added and auto-committed to Dolt.")
    return HttpResponseRedirect(reverse("product_detail", args=[pk]))
