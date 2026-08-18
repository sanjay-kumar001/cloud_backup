# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Settings-gated cloud retention: delete only Cloud Backup-managed remote files."""

from __future__ import annotations

import re
from datetime import datetime

import frappe
from frappe.utils import add_to_date, now_datetime

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
	"""Reconcile this provider's destination folder against the retention policy.

	Lists the remote folder, keeps only files this app named, and deletes the
	ones outside the policy — including orphans whose History row was lost.
	"""
	if not backup_service.is_provider_ready(provider):
		return
	try:
		instance = provider_service.get_provider(provider)
		remote = instance.list_files(_destination(provider))
	except CloudBackupError as exc:
		log_service.write_log(
			"cleanup_error", str(exc), level="ERROR", source=SOURCE, details={"provider": provider}
		)
		return
	managed = [m for m in (_classify(f) for f in remote) if m]
	to_delete = _select_for_deletion(managed, settings)
	result["candidates"] += len(to_delete)
	if not to_delete or dry_run:
		return
	tracked = _history_by_remote_id(provider)
	for item in to_delete:
		try:
			instance.delete_file(item["id"])
		except CloudBackupError as exc:
			log_service.write_log(
				"cleanup_error", str(exc), level="ERROR", source=SOURCE, details={"remote_file": item["id"]}
			)
			continue
		history = tracked.get(item["id"])
		if history:
			frappe.db.set_value(
				"Cloud Backup History", history, {"remote_deleted": 1, "deleted_at": now_datetime()}
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
		frappe.delete_doc(
			"Cloud Backup History", name, ignore_permissions=True, force=True, delete_permanently=True
		)
	if names:
		frappe.db.commit()
	return len(names)


def _managed_providers() -> list[str]:
	"""Providers to reconcile: any that ever uploaded, plus the active targets."""
	providers = set(
		frappe.get_all(
			"Cloud Backup History", filters={"remote_file": ["is", "set"]}, distinct=True, pluck="provider"
		)
	)
	settings = get_cloud_backup_settings()
	providers.update(p for p in (settings.default_provider, settings.fallback_provider) if p)
	return [p for p in providers if p]


def _destination(provider: str) -> str | None:
	"""Return the folder this provider uploads into (destination or root)."""
	config = frappe.db.get_value(
		"Cloud Backup Provider", provider, ["destination_folder", "root_folder"], as_dict=True
	)
	return config and (config.destination_folder or config.root_folder)


def _history_by_remote_id(provider: str) -> dict[str, str]:
	"""Map live remote-file id -> History name for this provider."""
	rows = frappe.get_all(
		"Cloud Backup History",
		filters={"provider": provider, "remote_file": ["is", "set"], "remote_deleted": 0},
		fields=["name", "remote_file"],
	)
	return {r.remote_file: r.name for r in rows}


# Remote names built by build_remote_filename: {site}_{label}_{YYYYMMDD_HHMMSS}{ext}
_ARTIFACT_RE = re.compile(r"_(database|files|private-files)_(\d{8}_\d{6})\.(?:sql\.gz|tar)(?:\.gpg)?$")


def _classify(remote_file: dict) -> dict | None:
	"""Return {id, label, stamp} for an app-named remote file, else None."""
	match = _ARTIFACT_RE.search(remote_file.get("name") or "")
	if not match:
		return None
	return {"id": remote_file["id"], "label": match.group(1), "stamp": match.group(2)}


def _select_for_deletion(managed: list[dict], settings) -> list[dict]:
	"""App-named remote files outside the configured count/age policy."""
	if settings.retention_type == "Count":
		keep = int(settings.retention_count or 0)
		if keep <= 0:
			return []
		# Count applies per artifact kind, not across mixed types.
		groups: dict[str, list[dict]] = {}
		for item in managed:
			groups.setdefault(item["label"], []).append(item)
		to_delete: list[dict] = []
		for group in groups.values():
			group.sort(key=lambda i: i["stamp"], reverse=True)
			to_delete.extend(group[keep:])
		return to_delete
	if settings.retention_type == "Age":
		days = int(settings.retention_days or 0)
		if days <= 0:
			return []
		cutoff = add_to_date(now_datetime(), days=-days)
		return [i for i in managed if _parse_stamp(i["stamp"]) and _parse_stamp(i["stamp"]) < cutoff]
	return []


def _parse_stamp(stamp: str):
	"""Parse a YYYYMMDD_HHMMSS backup stamp; None when malformed."""
	try:
		return datetime.strptime(stamp, "%Y%m%d_%H%M%S")
	except ValueError:
		return None


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
