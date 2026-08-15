# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Operational event log for Cloud Backup."""

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CloudBackupLog(Document):
	def before_insert(self) -> None:
		"""Stamp the event time when not supplied."""
		if not self.timestamp:
			self.timestamp = now_datetime()

	@staticmethod
	def clear_old_logs(days: int = 90) -> None:
		"""LogType hook: let native Log Settings purge rows older than `days`."""
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Cloud Backup Log")
		frappe.db.delete(table, filters=(table.timestamp < (Now() - Interval(days=days))))
