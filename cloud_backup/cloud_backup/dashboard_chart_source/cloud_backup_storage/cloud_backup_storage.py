# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Dashboard chart source: per-provider storage utilization (%)."""

import frappe
from frappe.utils.dashboard import cache_source


@frappe.whitelist()
@cache_source
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	"""Return {labels, datasets} of storage-used % per authorized provider."""
	from cloud_backup.services import dashboard_service

	labels, values = [], []
	for entry in dashboard_service.get_storage_usage():
		if not entry.get("ok") or entry.get("percent") is None:
			continue
		labels.append(entry["provider"])
		values.append(round(entry["percent"] * 100, 1))
	return {"labels": labels, "datasets": [{"name": frappe._("Storage Used %"), "values": values}]}
