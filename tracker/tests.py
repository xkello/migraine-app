"""Test coverage for missed-log group synchronization management command."""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from tracker.models import DailyLog, UserProfile


class MissedLogGroupCommandTests(TestCase):
    """Validate group membership and counter updates for missed-day workflow."""

    def setUp(self):
        """Create one active user/profile fixture used by all test cases."""
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="alice", password="password123"
        )
        self.profile = UserProfile.objects.create(user=self.user)
        self.group_name = "missed_daily_log"

    def test_adds_user_and_increments_counter_when_missed(self):
        """User without yesterday log is added to group and counter increments."""
        call_command("sync_missed_log_group", run_date="2026-03-25")

        self.profile.refresh_from_db()
        group = Group.objects.get(name=self.group_name)

        self.assertEqual(self.profile.missed_days_count, 1)
        self.assertEqual(self.profile.missed_days_last_incremented_on, date(2026, 3, 25))
        self.assertTrue(group.user_set.filter(id=self.user.id).exists())

    def test_same_day_rerun_is_idempotent(self):
        """Running sync twice for same date must not increment counter twice."""
        call_command("sync_missed_log_group", run_date="2026-03-25")
        call_command("sync_missed_log_group", run_date="2026-03-25")

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.missed_days_count, 1)

    def test_user_with_yesterday_log_removed_and_counter_reset(self):
        """User who logged yesterday is removed from group and counter resets."""
        group, _ = Group.objects.get_or_create(name=self.group_name)
        group.user_set.add(self.user)

        self.profile.missed_days_count = 3
        self.profile.missed_days_last_incremented_on = date(2026, 3, 24)
        self.profile.save(update_fields=["missed_days_count", "missed_days_last_incremented_on"])

        DailyLog.objects.create(
            user=self.user,
            date=date(2026, 3, 24),
            sleep_hours=8,
            physical_activity_minutes=30,
            stress_level=2,
            caffeine_mg=100,
        )

        call_command("sync_missed_log_group", run_date="2026-03-25")

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.missed_days_count, 0)
        self.assertIsNone(self.profile.missed_days_last_incremented_on)
        self.assertFalse(group.user_set.filter(id=self.user.id).exists())
