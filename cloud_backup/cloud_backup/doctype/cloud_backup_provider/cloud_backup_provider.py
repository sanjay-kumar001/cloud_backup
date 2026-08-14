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
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		access_token: DF.Password | None
		authentication_status: DF.Literal["Not Configured", "Authorized", "Expired", "Failed"]
		bucket: DF.Data | None
		client_id: DF.Password | None
		client_secret: DF.Password | None
		destination_folder: DF.Data | None
		enabled: DF.Check
		folder_name_display: DF.Data | None
		provider_type: DF.Literal["google_drive", "dropbox", "onedrive", "amazon_s3"]
		refresh_token: DF.Password | None
		region: DF.Data | None
		root_folder: DF.Data | None
		storage_kind: DF.Data | None
		token_expiry: DF.Datetime | None
	# end: auto-generated types

	def autoname(self) -> None:
		"""Name the record after the selected provider type (e.g. Google Drive)."""
		if not self.provider_type:
			frappe.throw(frappe._("Provider Type is required"))
		self.name = frappe.unscrub(self.provider_type)

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
