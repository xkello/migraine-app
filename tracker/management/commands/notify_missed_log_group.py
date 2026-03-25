from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Placeholder notification command for users in the missed log group. "
        "Currently prints recipients only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--group-name",
            default="missed_daily_log",
            help="Group containing users to notify (default: missed_daily_log).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Optional max number of users to process.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print recipients without performing any send action.",
        )

    def handle(self, *args, **options):
        group_name = options["group_name"]
        limit = options.get("limit")
        dry_run = options.get("dry_run", False)

        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist as exc:
            raise CommandError(
                f"Group '{group_name}' does not exist. Run sync_missed_log_group first."
            ) from exc

        users_qs = group.user_set.filter(is_active=True).order_by("id")
        if limit:
            users_qs = users_qs[:limit]

        users = list(users_qs)
        if not users:
            self.stdout.write(self.style.WARNING("No active users to notify."))
            return

        self.stdout.write(
            f"Preparing placeholder notifications for {len(users)} users from '{group_name}'."
        )

        # Placeholder only: print recipients until email provider/config is ready.
        for user in users:
            email = user.email or "<no-email>"
            self.stdout.write(f"- user={user.username} email={email}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete. No messages were sent."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Placeholder run complete. No emails sent by design; integrate provider later."
                )
            )


