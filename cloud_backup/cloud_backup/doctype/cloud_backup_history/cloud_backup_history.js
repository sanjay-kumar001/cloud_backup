// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup History", {
	refresh(frm) {
		if (["Failed", "Cancelled"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Retry Upload"), () => {
				frappe
					.xcall("cloud_backup.api.backup.retry_upload", { history: frm.doc.name })
					.then(() => {
						frappe.show_alert({ message: __("Upload re-queued"), indicator: "blue" });
						frm.reload_doc();
					});
			}).addClass("btn-primary");
		}
	},
});
