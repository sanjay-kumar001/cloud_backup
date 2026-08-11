# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Scheduler entrypoints: auto-upload fallback and due schedules."""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from cloud_backup.overrides.patch_manager import is_disabled
from cloud_backup.services import backup_service
from cloud_backup.utils.constants import DocType


def auto_upload_fallback() -> None:
	"""Sustain auto-upload when the new_backup patch is kill-switched off."""
	if not is_disabled():
		return
	backup_service.auto_enqueue_latest(trigger="fallback")


def run_due_schedules() -> None:
	"""Run every enabled schedule whose cadence is due."""
	now = now_datetime()
	for name in frappe.get_all(DocType.SCHEDULE, filters={"enabled": 1}, pluck="name"):
		try:
			schedule = frappe.get_doc(DocType.SCHEDULE, name)
			if is_due(schedule, now):
				run_schedule(schedule)
		except Exception:
			frappe.log_error(title="Cloud Backup Schedule", message=f"Schedule {name} failed")


def run_schedule(schedule) -> list[str]:
	"""Create a backup and enqueue its upload for this schedule's provider."""
	from frappe.utils.backups import new_backup

	settings = frappe.get_single(DocType.SETTINGS)
	wants_files = bool({"public", "private"} & backup_service.selected_artifacts(settings))
	odb = new_backup(ignore_files=not wants_files)
	names = backup_service.enqueue_for_schedule(schedule, odb)
	schedule.db_set("last_run", now_datetime())
	frappe.db.commit()
	return names


def is_due(schedule, now: datetime) -> bool:
	"""Return whether a schedule is due relative to its last run."""
	if not schedule.last_run:
		return True
	last = get_datetime(schedule.last_run)
	if schedule.schedule_type == "Daily":
		return last <= add_to_date(now, days=-1)
	if schedule.schedule_type == "Weekly":
		return last <= add_to_date(now, days=-7)
	if schedule.schedule_type == "Custom" and schedule.frequency:
		from croniter import croniter

		return croniter(schedule.frequency, last).get_next(datetime) <= now
	return False
