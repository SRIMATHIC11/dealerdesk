from django.db import models


class Product(models.Model):
    sku = models.CharField(max_length=80, primary_key=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True, db_index=True)
    brand = models.CharField(max_length=120, blank=True)
    vehicle_fitment = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["sku"]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="product_positive_price")
        ]

    def __str__(self):
        return self.sku


class Inventory(models.Model):
    product = models.OneToOneField(
        Product, primary_key=True, on_delete=models.CASCADE, related_name="inventory"
    )
    quantity = models.PositiveIntegerField(default=0)
    last_reason = models.CharField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="inventory_nonnegative"
            )
        ]
