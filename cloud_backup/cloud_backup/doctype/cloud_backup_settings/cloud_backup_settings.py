# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Singleton settings for Cloud Backup."""

import frappe
from frappe.model.document import Document


class CloudBackupSettings(Document):
	def validate(self) -> None:
		"""Normalize retention inputs against the selected policy."""
		self.validate_retention()

	def validate_retention(self) -> None:
		"""Guard non-negative retention values per selected type."""
		if self.retention_count and self.retention_count < 0:
			frappe.throw(frappe._("Backups to Keep cannot be negative"))
		if self.retention_days and self.retention_days < 0:
			frappe.throw(frappe._("Retention Days cannot be negative"))
