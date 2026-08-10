// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup Provider", {
	refresh(frm) {
		frm.trigger("set_status_indicator");
	},

	provider_type(frm) {
		frm.trigger("apply_storage_kind");
	},

	apply_storage_kind(frm) {
		if (!frm.doc.provider_type) {
			frm.set_value("storage_kind", "");
			return;
		}
		frappe.xcall(
			"cloud_backup.cloud_backup.doctype.cloud_backup_provider.cloud_backup_provider.get_provider_storage_kind"
		).then((map) => {
			frm.set_value("storage_kind", map[frm.doc.provider_type] || "");
		});
	},

	set_status_indicator(frm) {
		const map = {
			"Not Configured": "gray",
			Authorized: "green",
			Expired: "orange",
			Failed: "red",
		};
		const status = frm.doc.authentication_status;
		if (status) {
			frm.dashboard.set_headline(
				`<span class="indicator ${map[status] || "gray"}">${frappe.utils.escape_html(
					status
				)}</span>`
			);
		}
	},
});
