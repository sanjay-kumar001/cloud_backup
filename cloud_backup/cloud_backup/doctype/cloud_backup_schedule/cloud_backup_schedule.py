# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Recurring backup-and-upload schedule."""

import frappe
from frappe.model.document import Document


class CloudBackupSchedule(Document):
	def autoname(self) -> None:
		"""Name the record after the selected schedule type (e.g. Daily)."""
		if not self.schedule_type:
			frappe.throw(frappe._("Schedule Type is required"))
		self.name = frappe.unscrub(self.schedule_type)

	def validate(self) -> None:
		"""Validate the cron expression for custom schedules."""
		if self.schedule_type == "Custom" and self.frequency:
			from croniter import croniter

			if not croniter.is_valid(self.frequency):
				frappe.throw(frappe._("Invalid cron expression: {0}").format(self.frequency))


@frappe.whitelist()
def run_now(name: str) -> dict:
	"""Run a schedule immediately (create backup + enqueue upload)."""
	frappe.has_permission("Cloud Backup Schedule", "write", doc=name, throw=True)
	from cloud_backup.tasks import run_schedule

	names = run_schedule(frappe.get_doc("Cloud Backup Schedule", name))
	return {"history": names}
