// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup Settings", {
	refresh(frm) {
		frm.trigger("render_status_banner");
		frm.add_custom_button(__("Upload Latest Backup"), () =>
			cloud_backup.settings.upload_latest(frm)
		).addClass("btn-primary");
	},

	render_status_banner(frm) {
		if (!frm.doc.last_upload_status) {
			return;
		}
		const ok = frm.doc.last_upload_status === "Success";
		const color = ok ? "green" : "red";
		const when = frm.doc.last_upload_timestamp
			? frappe.datetime.str_to_user(frm.doc.last_upload_timestamp)
			: "";
		frm.dashboard.clear_headline();
		frm.dashboard.set_headline(
			`<span class="indicator ${color}">Last upload: ${frappe.utils.escape_html(
				frm.doc.last_upload_status
			)} ${frappe.utils.escape_html(when)}</span>`
		);
	},
});

frappe.provide("cloud_backup.settings");

cloud_backup.settings.upload_latest = function (frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Upload Latest Backup"),
		fields: [
			{
				fieldname: "backup_type",
				fieldtype: "Select",
				label: __("Backup Type"),
				options: ["From Settings", "database", "files", "full"].join("\n"),
				default: "From Settings",
			},
		],
		primary_action_label: __("Upload"),
		primary_action(values) {
			dialog.hide();
			const backup_type =
				values.backup_type === "From Settings" ? null : values.backup_type;
			frappe
				.xcall("cloud_backup.api.backup.upload_latest", { backup_type })
				.then((r) => {
					frappe.show_alert({
						message: __("Queued {0} upload(s): {1}", [
							r.history.length,
							r.history.join(", "),
						]),
						indicator: "blue",
					});
				});
		},
	});
	dialog.show();
};
