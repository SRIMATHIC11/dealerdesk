from django.db import models


class Dealer(models.Model):
    dealer_code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    gstin = models.CharField(max_length=40, blank=True)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(credit_limit__gte=0), name="dealer_credit_nonnegative"
            )
        ]
