# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Settings-gated cloud retention: delete only Cloud Backup-managed remote files."""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from cloud_backup.services import backup_service, log_service, provider_service
from cloud_backup.utils.constants import DocType
from cloud_backup.utils.exceptions import CloudBackupError

SOURCE = "retention_service"


def run_cleanup(dry_run: bool = False) -> dict:
	"""Apply the retention policy to managed remote files. Idempotent (NFR-14)."""
	settings = frappe.get_single(DocType.SETTINGS)
	result = {"deleted": 0, "candidates": 0, "dry_run": dry_run, "skipped": False}
	if not settings.auto_delete_remote:
		result["skipped"] = True
		return result

	for provider in _managed_providers():
		rows = _managed_rows(provider)
		to_delete = _select_for_deletion(rows, settings)
		result["candidates"] += len(to_delete)
		if not to_delete or not backup_service.is_provider_ready(provider):
			continue
		if dry_run:
			continue
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
				DocType.HISTORY, row["name"], {"remote_deleted": 1, "deleted_at": now_datetime()}
			)
			frappe.db.commit()
			result["deleted"] += 1

	_write_last_cleanup(result)
	log_service.write_log(
		"cleanup_run",
		f"Deleted {result['deleted']} of {result['candidates']} candidate(s)",
		source=SOURCE,
	)
	return result


def _managed_providers() -> list[str]:
	"""Providers that own at least one live managed remote file."""
	return frappe.get_all(
		DocType.HISTORY,
		filters={"status": "Completed", "remote_deleted": 0, "remote_file": ["is", "set"]},
		distinct=True,
		pluck="provider",
	)


def _managed_rows(provider: str) -> list[dict]:
	"""Live managed uploads for a provider, newest first."""
	return frappe.get_all(
		DocType.HISTORY,
		filters={
			"provider": provider,
			"status": "Completed",
			"remote_deleted": 0,
			"remote_file": ["is", "set"],
		},
		fields=["name", "remote_file", "completed_at"],
		order_by="completed_at desc",
	)


def _select_for_deletion(rows: list[dict], settings) -> list[dict]:
	"""Rows outside the configured count/age policy (only managed rows enter here)."""
	if settings.retention_type == "Count":
		keep = int(settings.retention_count or 0)
		return rows[keep:] if keep > 0 else []
	if settings.retention_type == "Age":
		days = int(settings.retention_days or 0)
		if days <= 0:
			return []
		cutoff = add_to_date(now_datetime(), days=-days)
		return [r for r in rows if r["completed_at"] and get_datetime(r["completed_at"]) < cutoff]
	return []


def _write_last_cleanup(result: dict) -> None:
	frappe.db.set_value(
		DocType.SETTINGS,
		DocType.SETTINGS,
		{
			"last_cleanup_timestamp": now_datetime(),
			"last_cleanup_status": "Success",
		},
	)
	frappe.db.commit()
