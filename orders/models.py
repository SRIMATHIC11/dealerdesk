from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        CONFIRMED = "CONFIRMED"
        DISPATCHED = "DISPATCHED"
        DELIVERED = "DELIVERED"
        CANCELLED = "CANCELLED"

    order_number = models.CharField(max_length=40, unique=True)
    dealer = models.ForeignKey("dealers.Dealer", on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["dealer", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["DRAFT", "CONFIRMED", "DISPATCHED", "DELIVERED", "CANCELLED"]
                ),
                name="order_valid_status",
            )
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalogue.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    name_snapshot = models.CharField(max_length=255)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="order_unique_product"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="order_item_positive_quantity"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gt=0), name="order_item_positive_price"
            ),
        ]


class DailySequence(models.Model):
    day = models.DateField(primary_key=True)
    value = models.PositiveIntegerField(default=0)


class OrderRequest(models.Model):
    key = models.CharField(max_length=255, primary_key=True)
    payload_hash = models.CharField(max_length=64)
    order = models.OneToOneField(
        Order, on_delete=models.PROTECT, null=True, related_name="idempotency_request"
    )
