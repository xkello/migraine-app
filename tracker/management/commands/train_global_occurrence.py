"""Management command wrapper for global ML training routines."""

from django.core.management.base import BaseCommand, CommandError

from tracker.ml.train_global import train_global_occurrence, train_global_severity


class Command(BaseCommand):
	help = "Train the generalized (global) ML model(s)."

	def add_arguments(self, parser):
		"""Register optional command flags."""
		parser.add_argument(
			"--with-severity",
			action="store_true",
			help="Also train global severity model after occurrence training.",
		)

	def handle(self, *args, **options):
		"""Run occurrence training and optional severity training."""
		self.stdout.write("Starting global occurrence training...")
		occurrence_result = train_global_occurrence()
		if not occurrence_result.get("ok"):
			raise CommandError(
				f"Global occurrence training failed: {occurrence_result.get('reason', 'unknown error')}"
			)

		self.stdout.write(self.style.SUCCESS(f"Occurrence training OK: {occurrence_result}"))

		if options.get("with_severity"):
			self.stdout.write("Starting global severity training...")
			severity_result = train_global_severity()
			if not severity_result.get("ok"):
				raise CommandError(
					f"Global severity training failed: {severity_result.get('reason', 'unknown error')}"
				)
			self.stdout.write(self.style.SUCCESS(f"Severity training OK: {severity_result}"))


