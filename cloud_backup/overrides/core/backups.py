# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Wrap frappe.utils.backups.new_backup to auto-upload after every backup."""

from __future__ import annotations

import frappe
from frappe.utils import backups as _backups

from cloud_backup.overrides.patch_manager import _safe_log, record_original

TARGET = "frappe.utils.backups.new_backup"
SENTINEL = "_cloud_backup_new_backup_patched"


def apply_patches() -> None:
	"""Idempotently wrap new_backup; call original first, return it unchanged."""
	if getattr(_backups, SENTINEL, False):
		return
	if not hasattr(_backups, "new_backup"):
		_safe_log(f"Cloud Backup: {TARGET} missing; patch skipped (layout drift)")
		return

	original = _backups.new_backup
	record_original(TARGET, original)

	def patched_new_backup(*args, **kwargs):
		odb = original(*args, **kwargs)
		try:
			from cloud_backup.services import backup_service

			backup_service.enqueue_after_backup(odb, trigger="auto")
		except Exception:
			_safe_log("Cloud Backup: auto-upload after backup failed to enqueue")
		return odb

	_backups.new_backup = patched_new_backup
	setattr(_backups, SENTINEL, True)


def revert() -> None:
	"""Restore the original new_backup and clear the sentinel (rollback)."""
	from cloud_backup.overrides.patch_manager import _ORIGINALS

	original = _ORIGINALS.get(TARGET)
	if original is not None:
		_backups.new_backup = original
	if hasattr(_backups, SENTINEL):
		delattr(_backups, SENTINEL)
