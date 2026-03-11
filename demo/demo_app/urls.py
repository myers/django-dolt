"""URL configuration for demo app."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("inventory/", views.inventory_dashboard, name="inventory"),
    path("orders/", views.orders_dashboard, name="orders"),
    path("dolt/commit/<str:db_alias>/", views.dolt_commit, name="dolt_commit"),
    path("inventory/product/<int:pk>/", views.product_detail, name="product_detail"),
    path("inventory/product/<int:pk>/comment/", views.add_product_comment, name="add_product_comment"),
]
