# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Aggregate Cloud Backup health, counts and storage utilization for the dashboard."""

from __future__ import annotations

import frappe
from frappe.query_builder.functions import Count

from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
	get_cloud_backup_settings,
)
from cloud_backup.services import provider_service
from cloud_backup.utils.constants import QUOTA_WARN_THRESHOLD
from cloud_backup.utils.exceptions import CloudBackupError

_ATTENTION_LIMIT = 10


def get_summary() -> dict:
	"""Return health headline, status counts, last backup and recent failures."""
	settings = get_cloud_backup_settings()
	counts = _status_counts()
	failed = counts.get("Failed", 0)
	completed = counts.get("Completed", 0)
	return {
		"enabled": bool(settings.enabled),
		"automatic_upload": bool(settings.automatic_upload),
		"default_provider": settings.default_provider,
		"fallback_provider": settings.fallback_provider,
		"last_upload_status": settings.last_upload_status,
		"last_upload_timestamp": settings.last_upload_timestamp,
		"last_cleanup_status": settings.last_cleanup_status,
		"last_cleanup_timestamp": settings.last_cleanup_timestamp,
		"health": _health(settings, failed),
		"counts": {"total": sum(counts.values()), "completed": completed, "failed": failed},
		"last_backup": _last_backup(),
		"attention": _failures_needing_attention(),
	}


def get_storage_usage() -> list[dict]:
	"""Return per-provider storage utilization with a threshold-breach flag."""
	out: list[dict] = []
	for provider in _authorized_providers():
		entry = {"provider": provider, "ok": False, "message": "", "percent": None}
		try:
			usage = provider_service.get_provider(provider).get_storage_usage()
			entry.update(_utilization(usage))
			entry["ok"] = True
		except CloudBackupError as exc:
			entry["message"] = exc.message or str(exc)
		except Exception as exc:  # provider not implementing quota, transport, etc.
			entry["message"] = str(exc)
		out.append(entry)
	return out


def _utilization(usage: dict) -> dict:
	"""Derive used/total/percent/warn from a provider usage dict."""
	used = int(usage.get("used") or 0)
	total = usage.get("total")
	percent = round(used / total, 4) if total else None
	return {
		"used": used,
		"total": total,
		"available": usage.get("available"),
		"percent": percent,
		"warn": bool(percent is not None and percent >= QUOTA_WARN_THRESHOLD),
	}


def _health(settings, failed: int) -> str:
	"""One-word health signal for the headline indicator."""
	if not settings.enabled:
		return "Disabled"
	if settings.last_upload_status == "Failed":
		return "Attention"
	if not settings.default_provider:
		return "Unconfigured"
	return "Healthy"


def _status_counts() -> dict[str, int]:
	"""History row counts grouped by status."""
	h = frappe.qb.DocType("Cloud Backup History")
	rows = (
		frappe.qb.from_(h).select(h.status, Count(h.name).as_("n")).groupby(h.status)
	).run(as_dict=True)
	return {r["status"]: r["n"] for r in rows}


def _last_backup() -> dict | None:
	"""Most recent completed upload, for the 'last backup' card."""
	rows = frappe.get_all(
		"Cloud Backup History",
		filters={"status": "Completed"},
		fields=["name", "site", "backup_type", "provider", "file_size", "completed_at"],
		order_by="completed_at desc",
		limit=1,
	)
	return rows[0] if rows else None


def _failures_needing_attention() -> list[dict]:
	"""Recent failed uploads that have not since been re-uploaded and deleted."""
	return frappe.get_all(
		"Cloud Backup History",
		filters={"status": "Failed"},
		fields=["name", "site", "backup_type", "provider", "error", "modified"],
		order_by="modified desc",
		limit=_ATTENTION_LIMIT,
	)


def _authorized_providers() -> list[str]:
	"""Enabled, authorized providers (quota is only meaningful once connected)."""
	return frappe.get_all(
		"Cloud Backup Provider",
		filters={"enabled": 1, "authentication_status": "Authorized"},
		pluck="name",
	)
