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
		const can_restore =
			frm.doc.status === "Completed" &&
			frm.doc.remote_file &&
			!frm.doc.remote_deleted &&
			frappe.user.has_role("System Manager");
		if (can_restore) {
			frm.add_custom_button(__("Download from Cloud"), () =>
				cloud_backup_history_download(frm)
			);
		}
	},
});

function cloud_backup_history_download(frm) {
	frappe.confirm(
		__("Download this backup from the cloud into the site's private/backups folder?"),
		() => {
			frappe
				.xcall("cloud_backup.api.restore.download_from_cloud", { history: frm.doc.name })
				.then((r) => {
					frappe.msgprint({
						title: __("Downloaded"),
						indicator: "green",
						message: __("Saved to {0}. Restore with: {1}", [
							`<code>${frappe.utils.escape_html(r.local_path)}</code>`,
							`<code>bench --site ${frappe.utils.escape_html(
								frappe.boot.sitename || "SITE"
							)} restore ${frappe.utils.escape_html(r.local_path)}</code>`,
						]),
					});
				});
		}
	);
}
