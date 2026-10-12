from decimal import Decimal

from catalogue.models import Inventory, Product
from dealers.models import Dealer


def product(sku="BRK-TEST", price="10.03", stock=5, **extra):
    values = {
        "name": "Brake Pad Set - Bajaj Pulsar 150",
        "brand": "Endurance",
        "category": "Brakes",
        "vehicle_fitment": "Bajaj Pulsar 150",
        "price": Decimal(price),
    }
    values.update(extra)
    result = Product.objects.create(sku=sku, **values)
    Inventory.objects.create(product=result, quantity=stock)
    return result


def dealer(code="DLR-TEST"):
    return Dealer.objects.create(dealer_code=code, name="Test Dealer")
