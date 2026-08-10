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
