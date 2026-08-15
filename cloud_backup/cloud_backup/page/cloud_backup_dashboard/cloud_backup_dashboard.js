// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.pages["cloud-backup-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cloud Backup Health"),
		single_column: true,
	});

	const $body = $('<div class="cb-health" style="margin-top:12px;"></div>').appendTo(page.body);
	page.set_primary_action(__("Refresh"), () => load(), "refresh");
	page.add_inner_button(__("Overview"), () =>
		frappe.set_route("dashboard-view", "Cloud Backup Overview")
	);
	page.add_inner_button(__("Settings"), () =>
		frappe.set_route("Form", "Cloud Backup Settings", "Cloud Backup Settings")
	);

	const HEALTH_COLOR = { Healthy: "green", Attention: "red", Disabled: "gray", Unconfigured: "orange" };

	function load() {
		$body.html(`<div class="text-muted">${__("Loading...")}</div>`);
		frappe
			.xcall("cloud_backup.api.dashboard.get_overview")
			.then(render)
			.catch(() => $body.html(`<div class="text-danger">${__("Failed to load")}</div>`));
	}

	function render(d) {
		$body.empty();
		$body.append(headline(d));
		$body.append(storage_section(d.storage || []));
	}

	function headline(d) {
		const color = HEALTH_COLOR[d.health] || "gray";
		const provider = d.provider ? frappe.utils.escape_html(d.provider) : __("none");
		return $(
			`<div style="margin-bottom:16px;">` +
				`<span class="indicator-pill ${color}" style="font-size:14px;">${frappe.utils.escape_html(
					d.health
				)}</span>` +
				`<span class="text-muted" style="margin-left:10px;">${__("Provider")}: ${provider} · ` +
				`${__("Auto-upload")}: ${d.automatic_upload ? __("On") : __("Off")}</span></div>`
		);
	}

	function storage_section(storage) {
		const $wrap = $(`<div><h5>${__("Storage Utilization")}</h5></div>`);
		if (!storage.length) {
			$wrap.append(`<div class="text-muted">${__("No authorized provider with quota.")}</div>`);
			return $wrap;
		}
		storage.forEach((e) => $wrap.append(storage_bar(e)));
		return $wrap;
	}

	function storage_bar(e) {
		const name = frappe.utils.escape_html(e.provider);
		if (!e.ok || e.percent === null || e.percent === undefined) {
			return $(
				`<div style="margin-bottom:10px;"><b>${name}</b> ` +
					`<span class="text-muted">${frappe.utils.escape_html(
						e.message || __("quota unavailable")
					)}</span></div>`
			);
		}
		const pct = Math.min(100, Math.round(e.percent * 100));
		const bar = e.warn ? "progress-bar-danger" : "progress-bar-success";
		return $(
			`<div style="margin-bottom:12px;">` +
				`<div><b>${name}</b> <span class="text-muted">${pct}% · ` +
				`${fmt_bytes(e.used)} / ${e.total ? fmt_bytes(e.total) : "∞"}</span>` +
				`${e.warn ? ` <span class="indicator-pill red">${__("Near limit")}</span>` : ""}</div>` +
				`<div class="progress" style="height:10px;margin-top:4px;">` +
				`<div class="progress-bar ${bar}" role="progressbar" style="width:${pct}%;"></div>` +
				`</div></div>`
		);
	}

	function fmt_bytes(n) {
		if (!n) return "0 B";
		const units = ["B", "KB", "MB", "GB", "TB"];
		let i = 0;
		let v = n;
		while (v >= 1024 && i < units.length - 1) {
			v /= 1024;
			i++;
		}
		return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
	}

	load();
};
