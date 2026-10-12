from django.conf import settings
from django.http import FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def index(request):
    return render(request, "portal/index.html")


@require_GET
def forecast_download(request):
    return FileResponse(
        (settings.BASE_DIR / "ml/forecast.csv").open("rb"),
        as_attachment=True,
        filename="forecast.csv",
        content_type="text/csv",
    )
