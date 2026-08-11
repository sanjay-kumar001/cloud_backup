# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Whitelisted backup endpoint: enqueue upload of the latest backup."""

from __future__ import annotations

import os

import frappe

from cloud_backup.services import backup_service, retention_service
from cloud_backup.utils.constants import UPLOAD_QUEUE, UPLOAD_TIMEOUT, DocType


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


@frappe.whitelist()
def retry_upload(history: str) -> dict:
	"""Re-enqueue a failed/cancelled upload for the given History row."""
	frappe.has_permission(DocType.HISTORY, "write", doc=history, throw=True)
	doc = frappe.get_doc(DocType.HISTORY, history)
	if doc.status not in ("Failed", "Cancelled"):
		frappe.throw(frappe._("Only failed or cancelled uploads can be retried"))
	if not doc.local_file or not os.path.exists(doc.local_file):
		frappe.throw(frappe._("The local backup file no longer exists"))
	doc.db_set("status", "Queued", commit=False)
	doc.db_set("error", None, commit=False)
	frappe.db.commit()
	frappe.enqueue(
		"cloud_backup.jobs.upload_backup.run",
		queue=UPLOAD_QUEUE,
		timeout=UPLOAD_TIMEOUT,
		history=doc.name,
		trigger="retry",
	)
	return {"history": doc.name}


@frappe.whitelist()
def run_cleanup(dry_run: int | str = 0) -> dict:
	"""Run the retention cleanup now (dry_run=1 to preview candidate count)."""
	frappe.has_permission(DocType.SETTINGS, "write", throw=True)
	return retention_service.run_cleanup(dry_run=bool(int(dry_run)))


def _default_backup_type(settings) -> str:
	"""Derive the backup type from the Settings upload-type toggles."""
	if settings.upload_full or (settings.upload_database and settings.upload_files):
		return "full"
	if settings.upload_files:
		return "files"
	return "database"
