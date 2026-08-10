// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup Settings", {
	refresh(frm) {
		frm.trigger("render_status_banner");
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
