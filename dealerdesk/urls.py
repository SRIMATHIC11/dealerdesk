from django.urls import include, path

urlpatterns = [
    path("api/", include("core.urls")),
    path("api/", include("catalogue.urls")),
    path("api/", include("dealers.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("assistant.urls")),
    path("api/", include("forecasting.urls")),
    path("api/", include("suppliers.urls")),
    path("", include("portal.urls")),
]
handler404 = "core.errors.not_found"
handler500 = "core.errors.server_error"
