# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Governed applier for core runtime patches (kill-switch + idempotent)."""

from __future__ import annotations

from importlib import import_module

import frappe

KILL_SWITCH = "disable_runtime_patches"

_ORIGINALS: dict[str, object] = {}
_APPLIED = False


def is_disabled() -> bool:
	"""Return the kill-switch state; safe before frappe.conf is available."""
	try:
		return bool(frappe.conf.get(KILL_SWITCH))
	except Exception:
		return False


def record_original(dotted: str, original: object) -> None:
	"""Retain the pre-patch callable for rollback/inspection."""
	_ORIGINALS.setdefault(dotted, original)


def apply_all_patches(*args, **kwargs) -> None:
	"""Apply every registered patch once; skipped entirely by the kill-switch."""
	global _APPLIED
	if _APPLIED or is_disabled():
		return
	from cloud_backup.overrides.patch_registry import PATCH_REGISTRY

	for dotted in PATCH_REGISTRY:
		module_path, func_name = dotted.rsplit(".", 1)
		try:
			getattr(import_module(module_path), func_name)()
		except Exception:
			_safe_log(f"Cloud Backup: failed to apply patch {dotted}")
	_APPLIED = True


def patch_status() -> dict:
	"""Ops probe: kill-switch state, recorded originals, target + sentinel."""
	from frappe.utils import backups

	return {
		"disabled": is_disabled(),
		"originals": list(_ORIGINALS.keys()),
		"target_exists": hasattr(backups, "new_backup"),
		"sentinel": getattr(backups, "_cloud_backup_new_backup_patched", False),
	}


def _safe_log(message: str) -> None:
	"""Log without ever raising (import-time contexts may lack a DB)."""
	try:
		frappe.log_error(title="Cloud Backup Patch", message=message)
	except Exception:
		pass
