// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup Provider", {
	refresh(frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("render_actions");
		frm.trigger("flash_authorization_result");
	},

	provider_type(frm) {
		frm.trigger("apply_storage_kind");
	},

	apply_storage_kind(frm) {
		if (!frm.doc.provider_type) {
			frm.set_value("storage_kind", "");
			return;
		}
		frappe
			.xcall(
				"cloud_backup.cloud_backup.doctype.cloud_backup_provider.cloud_backup_provider.get_provider_storage_kind"
			)
			.then((map) => {
				frm.set_value("storage_kind", map[frm.doc.provider_type] || "");
			});
	},

	render_actions(frm) {
		if (frm.is_new() || !frm.doc.provider_type) {
			return;
		}
		const authorized = frm.doc.authentication_status === "Authorized";
		if (frm.doc.storage_kind === "folder") {
			frm.add_custom_button(authorized ? __("Re-authorize") : __("Authorize"), () =>
				cloud_backup.provider.authorize(frm)
			);
		}
		if (authorized || frm.doc.storage_kind === "object") {
			frm.add_custom_button(__("Test Connection"), () =>
				cloud_backup.provider.test_connection(frm)
			);
		}
		if (frm.doc.storage_kind === "folder" && authorized) {
			frm.add_custom_button(__("Select Destination Folder"), () =>
				cloud_backup.provider.open_folder_browser(frm)
			);
		}
	},

	flash_authorization_result(frm) {
		// The shared Google callback appends cb_authorized=1 whenever Google
		// returned no error, even if the token exchange failed — so trust the
		// persisted authentication_status, not the URL param.
		if (frappe.utils.get_url_arg("cb_authorized") === null) {
			return;
		}
		const ok = frm.doc.authentication_status === "Authorized";
		frappe.show_alert({
			message: ok
				? __("Google Drive authorized")
				: __("Authorization failed — check Google Settings client secret and the Error Log"),
			indicator: ok ? "green" : "red",
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

frappe.provide("cloud_backup.provider");

cloud_backup.provider.authorize = function (frm) {
	frappe
		.xcall("cloud_backup.api.provider.authorize", { provider: frm.doc.name })
		.then((r) => {
			if (r && r.url) {
				window.location.href = r.url;
			}
		});
};

cloud_backup.provider.test_connection = function (frm) {
	frappe
		.xcall("cloud_backup.api.provider.test_connection", { provider: frm.doc.name })
		.then((r) => {
			frappe.msgprint({
				title: r.ok ? __("Success") : __("Failed"),
				message: frappe.utils.escape_html(r.message || ""),
				indicator: r.ok ? "green" : "red",
			});
		});
};

cloud_backup.provider.open_folder_browser = function (frm) {
	const provider = frm.doc.name;
	let path = [{ id: frm.doc.root_folder || "root", name: __("Root") }];

	const dialog = new frappe.ui.Dialog({
		title: __("Select Destination Folder"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "browser" }],
		primary_action_label: __("Use Current Folder"),
		primary_action() {
			const current = path[path.length - 1];
			frm.set_value("destination_folder", current.id);
			frm.set_value("folder_name_display", path.map((p) => p.name).join(" / "));
			dialog.hide();
			frm.save();
		},
	});

	const $body = dialog.fields_dict.browser.$wrapper;
	const current = () => path[path.length - 1];

	function render(folders) {
		const crumbs = path
			.map(
				(p, i) =>
					`<a href="#" class="cb-crumb" data-idx="${i}">${frappe.utils.escape_html(
						p.name
					)}</a>`
			)
			.join(" / ");
		const rows = folders.length
			? folders
					.map(
						(f) =>
							`<div class="cb-folder-row list-row" data-id="${frappe.utils.escape_html(
								f.id
							)}" data-name="${frappe.utils.escape_html(
								f.name
							)}" style="cursor:pointer;padding:6px 4px;"><i class="fa fa-folder-o"></i> ${frappe.utils.escape_html(
								f.name
							)}</div>`
					)
					.join("")
			: `<div class="text-muted" style="padding:6px 4px;">${__("No subfolders")}</div>`;
		$body.html(
			`<div class="cb-crumbs text-muted" style="margin-bottom:8px;">${crumbs}</div>` +
				`<div style="margin-bottom:8px;"><button class="btn btn-xs btn-default cb-new-folder">${__(
					"New Folder"
				)}</button></div>` +
				`<div class="cb-folder-list">${rows}</div>`
		);
		$body.find(".cb-folder-row").on("click", function () {
			path.push({ id: $(this).data("id"), name: $(this).data("name") });
			load();
		});
		$body.find(".cb-crumb").on("click", function (e) {
			e.preventDefault();
			path = path.slice(0, cint($(this).data("idx")) + 1);
			load();
		});
		$body.find(".cb-new-folder").on("click", () => new_folder());
	}

	function load() {
		$body.html(`<div class="text-muted">${__("Loading...")}</div>`);
		frappe
			.xcall("cloud_backup.api.provider.list_folders", {
				provider,
				parent_id: current().id,
			})
			.then(render)
			.catch(() => $body.html(`<div class="text-danger">${__("Failed to list folders")}</div>`));
	}

	function new_folder() {
		frappe.prompt(
			{ label: __("Folder Name"), fieldname: "name", fieldtype: "Data", reqd: 1 },
			(values) => {
				frappe
					.xcall("cloud_backup.api.provider.create_folder", {
						provider,
						name: values.name,
						parent_id: current().id,
					})
					.then(() => load());
			},
			__("New Folder"),
			__("Create")
		);
	}

	dialog.show();
	load();
};
