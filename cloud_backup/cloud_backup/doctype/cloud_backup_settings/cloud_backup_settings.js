// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup Settings", {
	refresh(frm) {
		frm.trigger("filter_authorized_providers");
		frm.trigger("render_status_banner");
		frm.add_custom_button(__("Upload Latest Backup"), () =>
			cloud_backup.settings.upload_latest(frm)
		).addClass("btn-primary");
		frm.add_custom_button(__("Run Cleanup Now"), () =>
			cloud_backup.settings.run_cleanup(frm)
		);
	},

	filter_authorized_providers(frm) {
		const query = () => ({ filters: { authentication_status: "Authorized" } });
		frm.set_query("default_provider", query);
		frm.set_query("fallback_provider", query);
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

cloud_backup.settings.run_cleanup = function (frm) {
	if (!frm.doc.auto_delete_remote) {
		frappe.msgprint({
			title: __("Cleanup disabled"),
			message: __("Enable 'Auto-Delete Remote Backups' first."),
			indicator: "orange",
		});
		return;
	}
	frappe.confirm(__("Delete managed remote backups outside the retention policy?"), () => {
		frappe.xcall("cloud_backup.api.backup.run_cleanup", { dry_run: 0 }).then((r) => {
			frappe.show_alert({
				message: __("Cleanup done: {0} deleted", [r.deleted || 0]),
				indicator: "green",
			});
			frm.reload_doc();
		});
	});
};

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
						message: __("Backup queued in the background ({0}). See Cloud Backup History.", [
							r.backup_type,
						]),
						indicator: "blue",
					});
				});
		},
	});
	dialog.show();
};
