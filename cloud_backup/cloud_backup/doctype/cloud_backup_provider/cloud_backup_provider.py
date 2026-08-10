# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Cloud storage provider configuration and credentials."""

import frappe
from frappe.model.document import Document

from cloud_backup.utils.constants import (
	FOLDER_PROVIDERS,
	OBJECT_PROVIDERS,
	PROVIDER_STORAGE_KIND,
	storage_kind_for,
)


class CloudBackupProvider(Document):
	def validate(self) -> None:
		"""Set initial auth status and validate provider-specific config."""
		if self.is_new() and not self.authentication_status:
			self.authentication_status = "Not Configured"
		self.storage_kind = storage_kind_for(self.provider_type)
		self.validate_provider_config()

	def validate_provider_config(self) -> None:
		"""Require bucket for object storage; clear S3 fields for folders."""
		if self.provider_type in OBJECT_PROVIDERS:
			if self.enabled and not self.bucket:
				frappe.throw(frappe._("Bucket is required for {0}").format(self.provider_type))
		elif self.provider_type in FOLDER_PROVIDERS:
			self.bucket = None
			self.region = None


@frappe.whitelist()
def get_provider_storage_kind() -> dict[str, str]:
	"""Return the provider_type -> storage_kind map for form section toggling."""
	frappe.has_permission("Cloud Backup Provider", "read", throw=True)
	return dict(PROVIDER_STORAGE_KIND)
