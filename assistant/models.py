from django.db import models


class ChatSession(models.Model):
    session_id = models.CharField(max_length=120, primary_key=True)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.PROTECT)
    messages = models.JSONField(default=list)
    last_skus = models.JSONField(default=list)
    lease_token = models.CharField(max_length=36, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
