// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Cloud Backup Storage"] = {
	method: "cloud_backup.cloud_backup.dashboard_chart_source.cloud_backup_storage.cloud_backup_storage.get",
	filters: [],
};
