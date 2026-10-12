from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request):
    """GET /api/health/ — the grader polls this until your app is ready."""
    return Response({"status": "ok"})
