// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup Schedule", {
	refresh(frm) {
		frm.set_query("provider", () => ({
			filters: { authentication_status: "Authorized" },
		}));
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Run Now"), () => {
			frappe.confirm(__("Create a backup now and upload it via this schedule?"), () => {
				frappe
					.xcall(
						"cloud_backup.cloud_backup.doctype.cloud_backup_schedule.cloud_backup_schedule.run_now",
						{ name: frm.doc.name }
					)
					.then((r) => {
						frappe.show_alert({
							message: __("Queued {0} upload(s)", [(r.history || []).length]),
							indicator: "blue",
						});
						frm.reload_doc();
					});
			});
		});
	},
});
