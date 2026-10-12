from django.urls import path

from portal.views import forecast_download, index

urlpatterns = [path("", index), path("forecast.csv", forecast_download)]
