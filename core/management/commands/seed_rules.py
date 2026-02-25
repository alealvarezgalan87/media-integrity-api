"""
Management command to seed default red flag rules from scoring_rules.yaml.
Idempotent — skips rules that already exist.
Single source of truth: scoring_rules.yaml in project root.
"""

from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

from core.models import RedFlagRule

YAML_PATH = Path(__file__).resolve().parent.parent.parent.parent / "scoring_rules.yaml"


class Command(BaseCommand):
    help = "Seed default red flag rules from scoring_rules.yaml (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=str(YAML_PATH),
            help="Path to scoring_rules.yaml (default: project root)",
        )

    def handle(self, *args, **options):
        yaml_path = Path(options["file"])
        if not yaml_path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {yaml_path}"))
            return

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        rules = data.get("rules", [])
        if not rules:
            self.stderr.write(self.style.WARNING("No rules found in YAML file."))
            return

        created_count = 0
        skipped_count = 0

        for idx, rule_data in enumerate(rules):
            _, created = RedFlagRule.objects.get_or_create(
                id=rule_data["id"],
                defaults={
                    "severity": rule_data["severity"],
                    "domain": rule_data["domain"],
                    "condition": rule_data["condition"],
                    "title": rule_data["title"],
                    "description": rule_data.get("description", ""),
                    "recommendation": rule_data.get("recommendation", ""),
                    "enabled": True,
                    "sort_order": idx * 10,
                    "is_system": True,
                    "organization": None,
                },
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} rules created, {skipped_count} already existed "
                f"(source: {yaml_path.name}, {len(rules)} rules total)."
            )
        )
