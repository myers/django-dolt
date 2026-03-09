"""URL configuration for demo app."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("inventory/", views.inventory_dashboard, name="inventory"),
    path("orders/", views.orders_dashboard, name="orders"),
    path("dolt/commit/<str:db_alias>/", views.dolt_commit, name="dolt_commit"),
]
