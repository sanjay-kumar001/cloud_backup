# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Settings-gated cloud retention: delete only Cloud Backup-managed remote files."""

from __future__ import annotations

import re

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
	get_cloud_backup_settings,
)
from cloud_backup.services import backup_service, log_service, provider_service
from cloud_backup.utils.exceptions import CloudBackupError

SOURCE = "retention_service"


def run_cleanup(dry_run: bool = False, provider: str | None = None) -> dict:
	"""Apply retention to managed remote files. Idempotent (NFR-14).

	provider=None runs every managed provider (daily/manual pass) and also
	purges old, already-deleted History rows. A provider name runs just that
	target (the after-upload pass) — only its set can have changed.
	"""
	settings = get_cloud_backup_settings()
	result = {"deleted": 0, "candidates": 0, "dry_run": dry_run, "skipped": False, "history_purged": 0}
	if settings.auto_delete_remote:
		targets = [provider] if provider else _managed_providers()
		for target in targets:
			_cleanup_provider(target, settings, result, dry_run)
	else:
		result["skipped"] = True

	# Age-based History housekeeping is global; only run it on the full pass.
	if provider is None:
		result["history_purged"] = _purge_history(settings, dry_run)

	_write_last_cleanup(result)
	log_service.write_log(
		"cleanup_run",
		f"Deleted {result['deleted']} of {result['candidates']} candidate(s); "
		f"purged {result['history_purged']} history row(s)",
		source=SOURCE,
	)
	return result


def _cleanup_provider(provider: str, settings, result: dict, dry_run: bool) -> None:
	"""Delete this provider's managed remote files outside the retention policy."""
	rows = _managed_rows(provider)
	to_delete = _select_for_deletion(rows, settings)
	result["candidates"] += len(to_delete)
	if not to_delete or not backup_service.is_provider_ready(provider) or dry_run:
		return
	instance = provider_service.get_provider(provider)
	for row in to_delete:
		try:
			instance.delete_file(row["remote_file"])
		except CloudBackupError as exc:
			log_service.write_log(
				"cleanup_error", str(exc), level="ERROR", source=SOURCE, details={"history": row["name"]}
			)
			continue
		frappe.db.set_value(
			"Cloud Backup History", row["name"], {"remote_deleted": 1, "deleted_at": now_datetime()}
		)
		frappe.db.commit()
		result["deleted"] += 1


def _purge_history(settings, dry_run: bool) -> int:
	"""Delete History rows whose remote file is already gone, older than N days."""
	days = int(getattr(settings, "history_retention_days", 0) or 0)
	if days <= 0:
		return 0
	cutoff = add_to_date(now_datetime(), days=-days)
	names = frappe.get_all(
		"Cloud Backup History",
		filters={"remote_deleted": 1, "deleted_at": ["<", cutoff]},
		pluck="name",
	)
	if dry_run:
		return len(names)
	for name in names:
		frappe.delete_doc("Cloud Backup History", name, ignore_permissions=True, force=True, delete_permanently=True)
	if names:
		frappe.db.commit()
	return len(names)


def _managed_providers() -> list[str]:
	"""Providers that own at least one live managed remote file."""
	return frappe.get_all(
		"Cloud Backup History",
		filters={"status": "Completed", "remote_deleted": 0, "remote_file": ["is", "set"]},
		distinct=True,
		pluck="provider",
	)


def _managed_rows(provider: str) -> list[dict]:
	"""Live managed uploads for a provider, newest first."""
	return frappe.get_all(
		"Cloud Backup History",
		filters={
			"provider": provider,
			"status": "Completed",
			"remote_deleted": 0,
			"remote_file": ["is", "set"],
		},
		fields=["name", "remote_file", "completed_at"],
		order_by="completed_at desc",
	)


_ARTIFACT_RE = re.compile(r"_(database|files|private-files)_\d{8}_\d{6}")


def _artifact_group(remote_file: str | None) -> str:
	"""Artifact kind (database/files/private-files) from the remote filename."""
	match = _ARTIFACT_RE.search(remote_file or "")
	return match.group(1) if match else "other"


def _select_for_deletion(rows: list[dict], settings) -> list[dict]:
	"""Rows outside the configured count/age policy (only managed rows enter here)."""
	if settings.retention_type == "Count":
		keep = int(settings.retention_count or 0)
		if keep <= 0:
			return []
		# Count applies per artifact kind, not across mixed types.
		groups: dict[str, list[dict]] = {}
		for row in rows:
			groups.setdefault(_artifact_group(row["remote_file"]), []).append(row)
		to_delete: list[dict] = []
		for group_rows in groups.values():
			to_delete.extend(group_rows[keep:])
		return to_delete
	if settings.retention_type == "Age":
		days = int(settings.retention_days or 0)
		if days <= 0:
			return []
		cutoff = add_to_date(now_datetime(), days=-days)
		return [r for r in rows if r["completed_at"] and get_datetime(r["completed_at"]) < cutoff]
	return []


def _write_last_cleanup(result: dict) -> None:
	frappe.db.set_value(
		"Cloud Backup Settings",
		"Cloud Backup Settings",
		{
			"last_cleanup_timestamp": now_datetime(),
			"last_cleanup_status": "Success",
		},
	)
	frappe.db.commit()
