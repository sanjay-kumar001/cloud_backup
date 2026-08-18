// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cloud Backup Provider", {
	refresh(frm) {
		frm.trigger("render_actions");
		frm.trigger("bind_authorize_link");
		frm.trigger("render_redirect_note");
		if (frm.is_new()) {
			frm.dashboard.clear_headline();
			return;
		}
		frm.trigger("set_status_indicator");
		frm.trigger("flash_authorization_result");
	},

	render_redirect_note(frm) {
		const field = frm.get_field("oauth2_redirect_note");
		if (!field || !["onedrive", "dropbox"].includes(frm.doc.provider_type)) {
			return;
		}
		const uri = `${window.location.origin}/api/method/cloud_backup.services.oauth2_service.callback`;
		field.$wrapper.html(
			`<p class="text-muted">${__("Register this exact redirect URI in the provider's app console:")}</p>` +
				`<pre style="white-space:pre-wrap;">${frappe.utils.escape_html(uri)}</pre>`
		);
	},

	bind_authorize_link(frm) {
		const field = frm.get_field("gdrive_credentials_note");
		if (!field) {
			return;
		}
		field.$wrapper.find(".cb-authorize-link").off("click").on("click", (e) => {
			e.preventDefault();
			if (frm.is_new()) {
				frappe.msgprint(__("Save the provider first, then Authorize."));
				return;
			}
			cloud_backup.provider.authorize(frm);
		});
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
		const can_browse =
			(frm.doc.storage_kind === "folder" && authorized) ||
			(frm.doc.storage_kind === "object" && frm.doc.bucket);
		if (can_browse) {
			const label =
				frm.doc.storage_kind === "object"
					? __("Select Destination Prefix")
					: __("Select Destination Folder");
			frm.add_custom_button(label, () => cloud_backup.provider.open_folder_browser(frm));
		}
	},

	flash_authorization_result(frm) {
		// Only after an OAuth callback on a saved provider.
		if (frm.is_new() || frappe.utils.get_url_arg("cb_authorized") === null) {
			return;
		}
		frm.trigger("clear_authorization_args");
		if (frm.doc.authentication_status === "Authorized") {
			frappe.show_alert({ message: __("Provider authorized"), indicator: "green" });
			return;
		}
		// GDrive uses core Google Settings; others use creds here.
		if (
			frm.doc.provider_type !== "google_drive" &&
			!(frm.doc.client_id && frm.doc.client_secret)
		) {
			return;
		}
		const reason = frappe.utils.get_url_arg("cb_reason");
		frappe.msgprint({
			title: __("Authorization failed"),
			indicator: "red",
			message: reason
				? frappe.utils.escape_html(decodeURIComponent(reason))
				: __("Check the credentials, the registered redirect URI, and Cloud Backup Log."),
		});
	},

	clear_authorization_args() {
		const url = new URL(window.location.href);
		url.searchParams.delete("cb_authorized");
		url.searchParams.delete("cb_reason");
		history.replaceState(null, "", url.toString());
	},

	set_status_indicator(frm) {
		if (frm.is_new()) {
			return;
		}
		const map = {
			"Not Configured": "gray",
			Authorized: "green",
			Expired: "orange",
			Failed: "red",
		};
		const status = frm.doc.authentication_status;
		frm.dashboard.clear_headline();
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

cloud_backup.provider.inject_browser_styles = function () {
	if (document.getElementById("cb-folder-browser-styles")) {
		return;
	}
	const css = `
	.cb-fb { display:flex; flex-direction:column; gap:12px; }
	.cb-fb-bar { display:flex; align-items:center; justify-content:space-between; gap:8px; }
	.cb-fb-crumbs { display:flex; flex-wrap:wrap; align-items:center; gap:2px; font-size:var(--text-md); min-height:24px; }
	.cb-fb-crumb { color:var(--text-muted); cursor:pointer; padding:2px 6px; border-radius:var(--border-radius); white-space:nowrap; }
	.cb-fb-crumb:hover { background:var(--bg-light-gray); color:var(--text-color); }
	.cb-fb-crumb.active { color:var(--text-color); font-weight:600; cursor:default; }
	.cb-fb-crumb.active:hover { background:none; }
	.cb-fb-sep { color:var(--text-light); }
	.cb-fb-list { border:1px solid var(--border-color); border-radius:var(--border-radius-md); overflow:hidden auto; max-height:320px; min-height:220px; background:var(--card-bg); }
	.cb-fb-row { display:flex; align-items:center; gap:10px; padding:9px 12px; cursor:pointer; border-bottom:1px solid var(--border-color); transition:background .1s; }
	.cb-fb-row:last-child { border-bottom:none; }
	.cb-fb-row:hover { background:var(--bg-light-gray); }
	.cb-fb-row .cb-fb-ficon { color:var(--yellow-500, #eab308); font-size:16px; width:18px; text-align:center; }
	.cb-fb-row .cb-fb-name { flex:1; color:var(--text-color); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
	.cb-fb-row .cb-fb-open { color:var(--text-light); opacity:0; transition:opacity .1s; }
	.cb-fb-row:hover .cb-fb-open { opacity:1; }
	.cb-fb-state { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; height:220px; color:var(--text-muted); text-align:center; }
	.cb-fb-state .cb-fb-bigicon { font-size:28px; opacity:.5; }
	.cb-fb-selected { display:flex; align-items:center; gap:8px; padding:8px 12px; background:var(--bg-light-gray); border-radius:var(--border-radius-md); font-size:var(--text-sm); }
	.cb-fb-selected .cb-fb-sel-label { color:var(--text-muted); }
	.cb-fb-selected .cb-fb-sel-path { color:var(--text-color); font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
	`;
	const style = document.createElement("style");
	style.id = "cb-folder-browser-styles";
	style.textContent = css;
	document.head.appendChild(style);
};

cloud_backup.provider.open_folder_browser = function (frm) {
	cloud_backup.provider.inject_browser_styles();
	const provider = frm.doc.name;
	const objectKind = frm.doc.storage_kind === "object";
	const rootLabel = objectKind ? __("Bucket Root") : __("My Drive");
	let path = [{ id: frm.doc.root_folder || "root", name: rootLabel }];

	const dialog = new frappe.ui.Dialog({
		title: objectKind ? __("Select Destination Prefix") : __("Select Destination Folder"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "browser" }],
		primary_action_label: __("Use This Folder"),
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
	const esc = frappe.utils.escape_html;

	function crumbs_html() {
		return path
			.map((p, i) => {
				const active = i === path.length - 1 ? " active" : "";
				const sep = i > 0 ? `<span class="cb-fb-sep"><i class="fa fa-angle-right"></i></span>` : "";
				return `${sep}<span class="cb-fb-crumb${active}" data-idx="${i}">${esc(p.name)}</span>`;
			})
			.join("");
	}

	function shell(inner) {
		$body.html(
			`<div class="cb-fb">` +
				`<div class="cb-fb-bar">` +
					`<div class="cb-fb-crumbs">${crumbs_html()}</div>` +
					`<button class="btn btn-xs btn-default cb-fb-new"><i class="fa fa-plus"></i> ${__(
						"New Folder"
					)}</button>` +
				`</div>` +
				`<div class="cb-fb-list">${inner}</div>` +
				`<div class="cb-fb-selected">` +
					`<span class="cb-fb-sel-label">${__("Selected")}:</span>` +
					`<span class="cb-fb-sel-path">${esc(path.map((p) => p.name).join(" / "))}</span>` +
				`</div>` +
			`</div>`
		);
		$body.find(".cb-fb-crumb:not(.active)").on("click", function () {
			path = path.slice(0, cint($(this).data("idx")) + 1);
			load();
		});
		$body.find(".cb-fb-new").on("click", () => new_folder());
	}

	function render(folders) {
		if (!folders.length) {
			shell(
				`<div class="cb-fb-state">` +
					`<div class="cb-fb-bigicon"><i class="fa fa-folder-open-o"></i></div>` +
					`<div>${__("This folder is empty")}</div>` +
				`</div>`
			);
			return;
		}
		const rows = folders
			.map(
				(f) =>
					`<div class="cb-fb-row" data-id="${esc(f.id)}" data-name="${esc(f.name)}">` +
						`<span class="cb-fb-ficon"><i class="fa fa-folder"></i></span>` +
						`<span class="cb-fb-name">${esc(f.name)}</span>` +
						`<span class="cb-fb-open"><i class="fa fa-angle-right"></i></span>` +
					`</div>`
			)
			.join("");
		shell(rows);
		$body.find(".cb-fb-row").on("click", function () {
			path.push({ id: $(this).data("id"), name: $(this).data("name") });
			load();
		});
	}

	function load() {
		shell(
			`<div class="cb-fb-state">` +
				`<div class="cb-fb-bigicon"><i class="fa fa-spinner fa-spin"></i></div>` +
				`<div>${__("Loading folders...")}</div>` +
			`</div>`
		);
		frappe
			.xcall("cloud_backup.api.provider.list_folders", { provider, parent_id: current().id })
			.then(render)
			.catch(() =>
				shell(
					`<div class="cb-fb-state text-danger">` +
						`<div class="cb-fb-bigicon"><i class="fa fa-exclamation-triangle"></i></div>` +
						`<div>${__("Could not load folders")}</div>` +
					`</div>`
				)
			);
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
