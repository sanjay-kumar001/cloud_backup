# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Whitelisted endpoint for the Cloud Backup Health page."""

from __future__ import annotations

import frappe

from cloud_backup.services import dashboard_service


@frappe.whitelist()
def get_overview() -> dict:
	"""Return health status + per-provider storage utilization."""
	frappe.has_permission("Cloud Backup Settings", "read", throw=True)
	return dashboard_service.get_overview()
