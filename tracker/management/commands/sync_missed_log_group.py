from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tracker.models import DailyLog, UserProfile


class Command(BaseCommand):
    help = (
        "Sync users who missed logging into a Django group and update their missed-day counter."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--group-name",
            default="missed_daily_log",
            help="Group that stores users who missed logging (default: missed_daily_log).",
        )
        parser.add_argument(
            "--run-date",
            help="Date to evaluate in YYYY-MM-DD format (default: local today).",
        )

    def handle(self, *args, **options):
        run_date = self._parse_run_date(options.get("run_date"))
        target_date = run_date - timedelta(days=1)
        group_name = options["group_name"]

        group, _ = Group.objects.get_or_create(name=group_name)

        user_model = get_user_model()
        users = list(user_model.objects.filter(is_active=True).only("id"))
        if not users:
            self.stdout.write(self.style.WARNING("No active users found."))
            return

        user_ids = [u.id for u in users]

        existing_profiles = {
            p.user_id: p
            for p in UserProfile.objects.filter(user_id__in=user_ids)
        }
        missing_profile_ids = [uid for uid in user_ids if uid not in existing_profiles]
        if missing_profile_ids:
            UserProfile.objects.bulk_create([UserProfile(user_id=uid) for uid in missing_profile_ids])
            existing_profiles = {
                p.user_id: p
                for p in UserProfile.objects.filter(user_id__in=user_ids)
            }

        logged_ids = set(
            DailyLog.objects.filter(user_id__in=user_ids, date=target_date).values_list(
                "user_id", flat=True
            )
        )
        in_group_ids = set(group.user_set.filter(id__in=user_ids).values_list("id", flat=True))

        add_to_group_ids = []
        remove_from_group_ids = []
        profiles_to_update = []

        incremented = 0
        reset = 0

        for uid in user_ids:
            profile = existing_profiles[uid]
            missed_yesterday = uid not in logged_ids

            if missed_yesterday:
                if uid not in in_group_ids:
                    add_to_group_ids.append(uid)

                if profile.missed_days_last_incremented_on != run_date:
                    profile.missed_days_count += 1
                    profile.missed_days_last_incremented_on = run_date
                    profiles_to_update.append(profile)
                    incremented += 1
            else:
                if uid in in_group_ids:
                    remove_from_group_ids.append(uid)

                if profile.missed_days_count != 0 or profile.missed_days_last_incremented_on is not None:
                    profile.missed_days_count = 0
                    profile.missed_days_last_incremented_on = None
                    profiles_to_update.append(profile)
                    reset += 1

        if add_to_group_ids:
            group.user_set.add(*add_to_group_ids)
        if remove_from_group_ids:
            group.user_set.remove(*remove_from_group_ids)
        if profiles_to_update:
            UserProfile.objects.bulk_update(
                profiles_to_update,
                ["missed_days_count", "missed_days_last_incremented_on"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Synced missed log group '%s' for target_date=%s: added=%s removed=%s "
                "incremented=%s reset=%s"
                % (
                    group_name,
                    target_date.isoformat(),
                    len(add_to_group_ids),
                    len(remove_from_group_ids),
                    incremented,
                    reset,
                )
            )
        )

    def _parse_run_date(self, run_date_raw: str | None) -> date:
        if not run_date_raw:
            return timezone.localdate()

        try:
            return date.fromisoformat(run_date_raw)
        except ValueError as exc:
            raise CommandError("--run-date must be in YYYY-MM-DD format") from exc

