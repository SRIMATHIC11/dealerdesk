from django.urls import path

from dealers.views import DealersView, DealerView

urlpatterns = [
    path("dealers/", DealersView.as_view()),
    path("dealers/<int:pk>/", DealerView.as_view()),
]
