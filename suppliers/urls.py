from django.urls import path

from suppliers.views import SupplierSyncView

urlpatterns = [path("sync/supplier/", SupplierSyncView.as_view())]
