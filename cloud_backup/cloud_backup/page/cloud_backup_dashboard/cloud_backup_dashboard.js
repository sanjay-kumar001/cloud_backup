// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.pages["cloud-backup-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cloud Backup Dashboard"),
		single_column: true,
	});

	const $body = $('<div class="cb-dashboard" style="margin-top:12px;"></div>').appendTo(page.body);

	page.set_primary_action(__("Refresh"), () => load(), "refresh");
	page.add_inner_button(__("Settings"), () =>
		frappe.set_route("Form", "Cloud Backup Settings", "Cloud Backup Settings")
	);
	page.add_inner_button(__("History"), () => frappe.set_route("List", "Cloud Backup History"));

	const HEALTH_COLOR = {
		Healthy: "green",
		Attention: "red",
		Disabled: "gray",
		Unconfigured: "orange",
	};

	function load() {
		$body.html(`<div class="text-muted">${__("Loading...")}</div>`);
		Promise.all([
			frappe.xcall("cloud_backup.api.dashboard.get_summary"),
			frappe.xcall("cloud_backup.api.dashboard.get_storage_usage"),
		])
			.then(([summary, storage]) => render(summary, storage))
			.catch(() => $body.html(`<div class="text-danger">${__("Failed to load dashboard")}</div>`));
	}

	function render(summary, storage) {
		// Upload counts/trend live on the standard Cloud Backup workspace
		// (Number Cards + Dashboard Charts). This page shows the live,
		// provider-sourced data those cannot: storage quota and open failures.
		$body.empty();
		$body.append(headline(summary));
		$body.append(storage_section(storage));
		$body.append(attention_section(summary.attention || []));
	}

	function headline(s) {
		const color = HEALTH_COLOR[s.health] || "gray";
		const provider = s.default_provider
			? frappe.utils.escape_html(s.default_provider)
			: __("none");
		return $(
			`<div style="margin-bottom:16px;">` +
				`<span class="indicator-pill ${color}" style="font-size:14px;">${frappe.utils.escape_html(
					s.health
				)}</span>` +
				`<span class="text-muted" style="margin-left:10px;">${__("Provider")}: ${provider} · ` +
				`${__("Auto-upload")}: ${s.automatic_upload ? __("On") : __("Off")}</span>` +
				`</div>`
		);
	}

	function storage_section(storage) {
		const $wrap = $(
			`<div style="margin-top:8px;"><h5>${__("Storage Utilization")}</h5></div>`
		);
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

	function attention_section(rows) {
		const $wrap = $(
			`<div style="margin-top:16px;"><h5>${__("Failures Needing Attention")}</h5></div>`
		);
		if (!rows.length) {
			$wrap.append(`<div class="text-muted">${__("No failures. All clear.")}</div>`);
			return $wrap;
		}
		const body = rows
			.map(
				(r) =>
					`<tr>` +
					`<td><a href="/app/cloud-backup-history/${encodeURIComponent(
						r.name
					)}">${frappe.utils.escape_html(r.name)}</a></td>` +
					`<td>${frappe.utils.escape_html(r.backup_type || "")}</td>` +
					`<td>${frappe.utils.escape_html(r.provider || "")}</td>` +
					`<td class="text-danger">${frappe.utils.escape_html((r.error || "").slice(0, 120))}</td>` +
					`<td class="text-muted">${frappe.datetime.comment_when(r.modified)}</td>` +
					`</tr>`
			)
			.join("");
		$wrap.append(
			`<table class="table table-bordered"><thead><tr>` +
				`<th>${__("History")}</th><th>${__("Type")}</th><th>${__("Provider")}</th>` +
				`<th>${__("Error")}</th><th>${__("When")}</th></tr></thead><tbody>${body}</tbody></table>`
		);
		return $wrap;
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
