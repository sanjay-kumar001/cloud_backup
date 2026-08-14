# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Shared test helpers (providers are named by type, so one per type)."""

import frappe


def make_provider(provider_type: str = "onedrive", **kwargs):
	"""Create an authorized provider of a type, replacing any existing one."""
	name = frappe.unscrub(provider_type)
	if frappe.db.exists("Cloud Backup Provider", name):
		frappe.delete_doc("Cloud Backup Provider", name, force=True, ignore_permissions=True)
	values = {"authentication_status": "Authorized", "destination_folder": "TestFolder"}
	values.update(kwargs)
	return frappe.get_doc(
		{"doctype": "Cloud Backup Provider", "provider_type": provider_type, **values}
	).insert(ignore_permissions=True)


def make_schedule(schedule_type: str = "Daily", **kwargs):
	"""Create a schedule of a type, replacing any existing one."""
	if frappe.db.exists("Cloud Backup Schedule", schedule_type):
		frappe.delete_doc("Cloud Backup Schedule", schedule_type, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{"doctype": "Cloud Backup Schedule", "schedule_type": schedule_type, **kwargs}
	).insert(ignore_permissions=True)
