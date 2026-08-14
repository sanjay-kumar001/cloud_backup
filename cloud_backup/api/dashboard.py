# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Whitelisted dashboard endpoints: health summary, storage, filter options."""

from __future__ import annotations

import frappe

from cloud_backup.services import dashboard_service


@frappe.whitelist()
def get_summary() -> dict:
	"""Return health headline, status counts, last backup and failures."""
	frappe.has_permission("Cloud Backup Settings", "read", throw=True)
	return dashboard_service.get_summary()


@frappe.whitelist()
def get_storage_usage() -> list[dict]:
	"""Return per-provider storage utilization with threshold flags."""
	frappe.has_permission("Cloud Backup Provider", "read", throw=True)
	return dashboard_service.get_storage_usage()


@frappe.whitelist()
def filter_options() -> dict:
	"""Return master-sourced filter values for the dashboard (SKILL.md §9)."""
	frappe.has_permission("Cloud Backup History", "read", throw=True)
	return {
		"providers": frappe.get_all("Cloud Backup Provider", pluck="name"),
	}
