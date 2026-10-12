from django.urls import path

from forecasting.views import ForecastView, ReorderView

urlpatterns = [
    path("forecast/<str:sku>/", ForecastView.as_view()),
    path("reorder-suggestions/", ReorderView.as_view()),
]
