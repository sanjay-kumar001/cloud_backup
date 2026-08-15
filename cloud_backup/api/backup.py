# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Whitelisted backup endpoint: enqueue upload of the latest backup."""

from __future__ import annotations

import os

import frappe

from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
	get_cloud_backup_settings,
)
from cloud_backup.services import backup_service, retention_service
from cloud_backup.utils.constants import UPLOAD_QUEUE, UPLOAD_TIMEOUT


@frappe.whitelist()
def upload_latest(backup_type: str | None = None) -> dict:
	"""Validate config and hand backup generation + upload to a background job."""
	frappe.has_permission("Cloud Backup Settings", "write", throw=True)
	settings = get_cloud_backup_settings()
	provider = backup_service.resolve_provider(settings)
	if not provider:
		frappe.throw(
			frappe._("No authorized provider with a destination is configured (default or fallback)")
		)

	# Generating a backup can be slow on large sites, so run it in a worker
	# (not inline in the web request).
	bt = backup_type or _default_backup_type(settings)
	frappe.enqueue(
		"cloud_backup.services.backup_service.enqueue_upload",
		queue=UPLOAD_QUEUE,
		timeout=UPLOAD_TIMEOUT,
		provider=provider,
		backup_type=bt,
		trigger="manual",
	)
	return {"queued": True, "backup_type": bt}


@frappe.whitelist()
def retry_upload(history: str) -> dict:
	"""Re-enqueue a failed/cancelled upload for the given History row."""
	frappe.has_permission("Cloud Backup History", "write", doc=history, throw=True)
	doc = frappe.get_doc("Cloud Backup History", history)
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
	frappe.has_permission("Cloud Backup Settings", "write", throw=True)
	return retention_service.run_cleanup(dry_run=bool(int(dry_run)))


def _default_backup_type(settings) -> str:
	"""Derive the backup type from the Settings upload-type toggles."""
	if settings.upload_full or (settings.upload_database and settings.upload_files):
		return "full"
	if settings.upload_files:
		return "files"
	return "database"
