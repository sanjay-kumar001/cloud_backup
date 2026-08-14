# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Whitelisted restore endpoint: download a cloud backup for Frappe restore."""

from __future__ import annotations

import frappe

from cloud_backup.services import restore_service
from cloud_backup.utils.exceptions import CloudBackupError


@frappe.whitelist()
def download_from_cloud(history: str) -> dict:
	"""Download a managed remote backup to private/backups (System Manager only)."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(frappe._("Only System Manager can restore backups"), frappe.PermissionError)
	frappe.has_permission("Cloud Backup History", "read", doc=history, throw=True)
	try:
		return restore_service.download_backup(history)
	except CloudBackupError as exc:
		frappe.throw(exc.message or str(exc), title=frappe._("Cloud Backup Restore"))
