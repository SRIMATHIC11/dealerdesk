from django.urls import path

from catalogue.views import InventoryView, ProductsView, ProductView

urlpatterns = [
    path("products/", ProductsView.as_view()),
    path("products/<str:sku>/", ProductView.as_view()),
    path("inventory/<str:sku>/", InventoryView.as_view()),
]
