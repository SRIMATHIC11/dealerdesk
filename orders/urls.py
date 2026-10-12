from django.urls import path

from orders.views import OrderActionView, OrdersView, OrderView

urlpatterns = [
    path("orders/", OrdersView.as_view()),
    path("orders/<str:number>/", OrderView.as_view()),
    path("orders/<str:number>/<str:action>/", OrderActionView.as_view()),
]
