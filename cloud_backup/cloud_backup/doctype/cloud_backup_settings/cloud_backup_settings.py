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


def get_cloud_backup_settings() -> "CloudBackupSettings":
	"""Return the cached Cloud Backup Settings singleton."""
	return frappe.get_cached_doc("Cloud Backup Settings")


def get_selected_artifacts(settings=None) -> set[str]:
	"""Artifact keys to upload, from the Settings upload-type toggles."""
	settings = settings or get_cloud_backup_settings()
	keys: set[str] = set()
	if settings.upload_full:
		keys.update(("database", "public", "private"))
	if settings.upload_database:
		keys.add("database")
	if settings.upload_files:
		keys.update(("public", "private"))
	return keys
