"""Small-catalogue weighted lexical retrieval; no embeddings/downloads/extensions.

Rank metadata only. Supplier descriptions are excluded from prompts and scoring.
Stock/prices are fetched anew on every call, so synchronization needs no index refresh.
"""

import math
import re
from collections import Counter

from catalogue.models import Product
from core.money import money

STOPWORDS = {
    "a",
    "an",
    "the",
    "for",
    "of",
    "to",
    "in",
    "on",
    "and",
    "or",
    "please",
    "i",
    "my",
    "me",
    "have",
    "do",
    "you",
    "need",
    "want",
    "show",
    "find",
    "available",
    "parts",
    "part",
    "with",
    "some",
    "is",
    "there",
    "any",
}
ALIASES = {
    "pads": "pad",
    "brakes": "brake",
    "filters": "filter",
    "mirrors": "mirror",
    "plugs": "plug",
    "chains": "chain",
    "oils": "oil",
    "batteries": "battery",
    "tyres": "tyre",
    "tires": "tyre",
    "sprockets": "sprocket",
    "indicators": "indicator",
    "bulbs": "bulb",
    "clutches": "clutch",
    "grips": "grip",
}


def tokens(text):
    return [
        ALIASES.get(t, t) for t in re.findall(r"[a-z0-9]+", text.casefold()) if t not in STOPWORDS
    ]


def product_facts(product):
    return {
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "vehicle_fitment": product.vehicle_fitment,
        "price": money(product.price),
        "stock": product.inventory.quantity,
    }


def search_parts(query, vehicle="", limit=6):
    products = list(Product.objects.select_related("inventory").all())
    terms = set(tokens(query))
    vehicle_terms = set(tokens(vehicle))
    documents = {
        p.sku: Counter(
            tokens(f"{p.sku} {p.name} {p.name} {p.brand} {p.category} {p.vehicle_fitment}")
        )
        for p in products
    }
    frequencies = Counter(t for terms_in_doc in documents.values() for t in terms_in_doc)
    avg_len = sum(sum(t.values()) for t in documents.values()) / max(1, len(products))
    ranked = []
    for p in products:
        fit = set(tokens(p.vehicle_fitment))
        if vehicle_terms and not vehicle_terms.issubset(fit):
            continue
        doc = documents[p.sku]
        exact = p.sku.casefold() in query.casefold()
        if terms and not terms.intersection(doc) and not exact:
            continue
        # Explicit vehicle displacement numbers must match, even in an unstructured query.
        numeric = {t for t in terms if t.isdigit() and len(t) <= 3}
        if numeric and not numeric.issubset(set(doc)):
            continue
        score = 100 if exact else 0
        length = sum(doc.values())
        for term in terms:
            tf = doc.get(term, 0)
            idf = math.log(
                1 + (len(products) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
            )
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / max(avg_len, 1)))
        ranked.append((score, p.inventory.quantity > 0, p.sku, p))
    ranked.sort(key=lambda r: (-r[0], -r[1], r[2]))
    if ranked and terms:
        # Prefer complete part phrases: a brake pad query must not offer a tank
        # pad or brake lever when products matching both brake and pad exist.
        coverage = {r[2]: len(terms.intersection(documents[r[2]])) for r in ranked}
        best_coverage = max(coverage.values())
        ranked = [r for r in ranked if r[0] >= 100 or coverage[r[2]] == best_coverage]
        # Avoid returning weak matches from a different part family below the best result.
        floor = ranked[0][0] * 0.35
        ranked = [r for r in ranked if r[0] >= floor]
    return {
        "products": [product_facts(p) for _, _, _, p in ranked[:limit]],
        "matched_count": len(ranked),
    }


def check_stock(skus):
    products = {p.sku: p for p in Product.objects.select_related("inventory").filter(sku__in=skus)}
    return {
        "products": [
            product_facts(products[sku]) for sku in dict.fromkeys(skus) if sku in products
        ],
        "missing_skus": [sku for sku in skus if sku not in products],
    }
