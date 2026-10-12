import csv
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from catalogue.models import Inventory, Product
from dealers.models import Dealer


class Command(BaseCommand):
    help = "Load the files in data/ into the database. Must be safe to run more than once."

    @transaction.atomic
    def handle(self, *args, **options):
        products_created = dealers_created = 0
        with (settings.DATA_DIR / "catalogue.csv").open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                stock = int(row.pop("stock"))
                row["price"] = Decimal(row["price"])
                sku = row.pop("sku")
                product, created = Product.objects.get_or_create(sku=sku, defaults=row)
                products_created += created
                # An existing product's price and live stock must never be reset by seeding.
                Inventory.objects.get_or_create(
                    product=product, defaults={"quantity": stock if created else 0}
                )
        with (settings.DATA_DIR / "dealers.csv").open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                code = row.pop("dealer_code")
                row["credit_limit"] = Decimal(row["credit_limit"])
                _, created = Dealer.objects.get_or_create(dealer_code=code, defaults=row)
                dealers_created += created
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {products_created} products and {dealers_created} dealers created; existing records preserved."
            )
        )
