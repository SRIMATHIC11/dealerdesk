"""Opt-in real provider check; credentials are never printed."""

import uuid

from django.core.management.base import BaseCommand, CommandError

from assistant.orchestration import chat
from assistant.provider import configuration
from dealers.models import Dealer


class Command(BaseCommand):
    help = "Check the configured live LLM with catalogue search; optionally create one draft."

    def add_arguments(self, parser):
        parser.add_argument("--create-draft", action="store_true")

    def handle(self, *args, **options):
        from core.errors import APIError

        try:
            provider, model, _ = configuration()
            dealer = Dealer.objects.order_by("id").first()
            if not dealer:
                raise CommandError("Run seed_data first.")
            session = f"integration-{uuid.uuid4().hex}"
            self.stdout.write(
                f"Checking provider={provider}, model={model}. Credentials are hidden."
            )
            greeting = chat(session, dealer.pk, "Hello, what can you help me with?")
            if not greeting["reply"] or greeting["actions"]:
                raise CommandError(
                    "The model did not return a valid greeting without side effects."
                )
            self.stdout.write("Greeting passed.")
            result = chat(
                session,
                dealer.pk,
                "Find brake pads for a Bajaj Pulsar 150 and check their current stock.",
            )
            if not result["tool_calls"] or not result["cited_skus"]:
                raise CommandError("The model did not return a grounded tool result.")
            self.stdout.write(result["reply"])
            self.stdout.write("Tools: " + ", ".join(t["name"] for t in result["tool_calls"]))
            if options["create_draft"]:
                sku = result["cited_skus"][0]
                result = chat(session, dealer.pk, f"Create a draft order for 1 unit of {sku}.")
                if not result["actions"]:
                    raise CommandError("The model did not create the requested draft.")
                self.stdout.write(result["reply"])
            self.stdout.write(self.style.SUCCESS("Live assistant integration passed."))
        except APIError as exc:
            raise CommandError(exc.message) from None
