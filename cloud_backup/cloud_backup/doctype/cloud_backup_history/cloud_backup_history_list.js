// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.listview_settings["Cloud Backup History"] = {
	get_indicator(doc) {
		const map = {
			Queued: "gray",
			Processing: "blue",
			Uploading: "blue",
			Verifying: "purple",
			Completed: "green",
			Failed: "red",
			Retrying: "orange",
			Cancelled: "gray",
			Skipped: "gray",
		};
		return [__(doc.status), map[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
