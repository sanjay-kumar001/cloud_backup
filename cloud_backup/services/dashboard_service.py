# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Per-provider storage utilization for the storage chart and quota alerts."""

from __future__ import annotations

import frappe

from cloud_backup.services import provider_service
from cloud_backup.utils.constants import QUOTA_WARN_THRESHOLD
from cloud_backup.utils.exceptions import CloudBackupError


def get_overview() -> dict:
	"""Return health status + per-provider storage for the Health page."""
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
		"storage": get_storage_usage(),
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
		except Exception as exc:  # provider without quota, transport, etc.
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


def _authorized_providers() -> list[str]:
	"""Enabled, authorized providers (quota is only meaningful once connected)."""
	return frappe.get_all(
		"Cloud Backup Provider",
		filters={"enabled": 1, "authentication_status": "Authorized"},
		pluck="name",
	)
