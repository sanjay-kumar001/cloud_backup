# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Per-provider storage utilization for the storage chart and quota alerts."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate

from cloud_backup.services import provider_service
from cloud_backup.utils.constants import QUOTA_WARN_THRESHOLD
from cloud_backup.utils.exceptions import CloudBackupError

RECENT_LIMIT = 7
TREND_DAYS = 7
SUMMARY_DAYS = 7


def get_overview() -> dict:
	"""Return health, summary counts, storage, recent uploads and trend."""
	from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
		get_cloud_backup_settings,
	)

	settings = get_cloud_backup_settings()
	if not settings.enabled:
		health = "Disabled"
	elif settings.last_upload_status == "Failed":
		health = "Attention"
	elif not settings.default_provider:
		health = "Unconfigured"
	else:
		health = "Healthy"
	return {
		"health": health,
		"provider": settings.default_provider,
		"automatic_upload": bool(settings.automatic_upload),
		"summary": get_summary(),
		"storage": get_storage_usage(),
		"recent": get_recent_uploads(),
		"trend": get_upload_trend(),
	}


def get_summary() -> dict:
	"""Return total/completed/failed upload counts for the last 7 days."""
	since = add_days(getdate(), -(SUMMARY_DAYS - 1))
	base = {"creation": [">=", since]}
	return {
		"days": SUMMARY_DAYS,
		"total": frappe.db.count("Cloud Backup History", base),
		"completed": frappe.db.count("Cloud Backup History", {**base, "status": "Completed"}),
		"failed": frappe.db.count("Cloud Backup History", {**base, "status": "Failed"}),
	}


def get_recent_uploads() -> list[dict]:
	"""Return the most recent upload history rows for the table."""
	return frappe.get_all(
		"Cloud Backup History",
		fields=[
			"name",
			"provider",
			"backup_type",
			"status",
			"file_size",
			"remote_file",
			"completed_at",
			"creation",
		],
		order_by="creation desc",
		limit=RECENT_LIMIT,
	)


def get_upload_trend() -> dict:
	"""Return completed/failed counts per day over the trend window."""
	start = add_days(getdate(), -(TREND_DAYS - 1))
	rows = frappe.get_all(
		"Cloud Backup History",
		filters={"creation": [">=", start], "status": ["in", ["Completed", "Failed"]]},
		fields=["creation", "status"],
	)
	labels = [str(add_days(start, i)) for i in range(TREND_DAYS)]
	completed = {d: 0 for d in labels}
	failed = {d: 0 for d in labels}
	for r in rows:
		key = str(getdate(r.creation))
		if key not in completed:
			continue
		if r.status == "Completed":
			completed[key] += 1
		else:
			failed[key] += 1
	return {
		"labels": labels,
		"completed": [completed[d] for d in labels],
		"failed": [failed[d] for d in labels],
	}


def get_storage_usage() -> list[dict]:
	"""Return per-provider storage utilization with a threshold-breach flag."""
	out: list[dict] = []
	for prov in _authorized_providers():
		entry = {
			"provider": prov.name,
			"provider_type": prov.provider_type,
			"logo": prov.logo or _logo(prov.provider_type),
			"ok": False,
			"message": "",
			"percent": None,
		}
		try:
			usage = provider_service.get_provider(prov.name).get_storage_usage()
			entry.update(_utilization(usage))
			entry["ok"] = True
		except CloudBackupError as exc:
			entry["message"] = exc.message or str(exc)
		except Exception as exc:  # provider without quota, transport, etc.
			entry["message"] = str(exc)
		out.append(entry)
	return out


PROVIDER_LOGOS = {
	"google_drive": "google_drive.png",
	"dropbox": "dropbox.png",
	"onedrive": "onedrive.jpg",
	"amazon_s3": "amazon_s3.jpg",
}


def _logo(provider_type: str | None) -> str | None:
	"""Return the asset URL for a provider type's logo, if shipped."""
	fname = PROVIDER_LOGOS.get(provider_type or "")
	return f"/assets/cloud_backup/images/{fname}" if fname else None


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


def _authorized_providers() -> list[dict]:
	"""Enabled, authorized providers (quota is only meaningful once connected)."""
	return frappe.get_all(
		"Cloud Backup Provider",
		filters={"enabled": 1, "authentication_status": "Authorized"},
		fields=["name", "provider_type", "logo"],
	)
