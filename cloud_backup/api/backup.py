# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Whitelisted backup endpoint: enqueue upload of the latest backup."""

from __future__ import annotations

import frappe

from cloud_backup.services import backup_service
from cloud_backup.utils.constants import DocType


@frappe.whitelist()
def upload_latest(backup_type: str | None = None) -> dict:
	"""Validate config and enqueue upload of the latest backup; return History names."""
	frappe.has_permission(DocType.SETTINGS, "write", throw=True)
	settings = frappe.get_single(DocType.SETTINGS)
	provider = settings.default_provider
	if not provider:
		frappe.throw(frappe._("Set a Default Provider in Cloud Backup Settings"))

	config = frappe.db.get_value(
		DocType.PROVIDER,
		provider,
		["authentication_status", "destination_folder", "root_folder"],
		as_dict=True,
	)
	if config.authentication_status != "Authorized":
		frappe.throw(frappe._("Default provider is not authorized"))
	if not (config.destination_folder or config.root_folder):
		frappe.throw(frappe._("Select a destination folder on the provider first"))

	names = backup_service.enqueue_upload(
		provider, backup_type or _default_backup_type(settings), trigger="manual"
	)
	return {"history": names}


def _default_backup_type(settings) -> str:
	"""Derive the backup type from the Settings upload-type toggles."""
	if settings.upload_full or (settings.upload_database and settings.upload_files):
		return "full"
	if settings.upload_files:
		return "files"
	return "database"
