// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt

frappe.pages["cloud-backup-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cloud Backup Dashboard"),
		single_column: true,
	});

	const $body = $(
		'<div class="cb-dash" style="margin-top:12px;padding:0 15px;"></div>'
	).appendTo(page.body);
	page.set_primary_action(__("Refresh"), () => load(), "refresh");
	page.add_inner_button(__("Backup Now"), () => backup_now());
	page.add_inner_button(__("History"), () => frappe.set_route("List", "Cloud Backup History"));
	page.add_inner_button(__("Settings"), () =>
		frappe.set_route("Form", "Cloud Backup Settings", "Cloud Backup Settings")
	);

	const HEALTH_COLOR = {
		Healthy: "green",
		Attention: "red",
		Disabled: "gray",
		Unconfigured: "orange",
	};
	const STATUS_COLOR = {
		Completed: "green",
		Failed: "red",
		Uploading: "blue",
		Processing: "blue",
		Verifying: "blue",
		Queued: "orange",
		Retrying: "orange",
		Cancelled: "gray",
		Skipped: "gray",
	};

	function load() {
		$body.html(`<div class="text-muted">${__("Loading...")}</div>`);
		frappe
			.xcall("cloud_backup.api.dashboard.get_overview")
			.then((d) => {
				render(d);
				load_storage();
			})
			.catch(() => $body.html(`<div class="text-danger">${__("Failed to load")}</div>`));
	}

	function load_storage() {
		const $col = $body.find(".cb-storage-col");
		const $target = $col.find(".cb-storage-body");
		$target.html(`<div class="text-muted">${__("Loading...")}</div>`);
		frappe
			.xcall("cloud_backup.api.dashboard.get_storage")
			.then((storage) => render_storage($target, storage || []))
			.catch(() =>
				$target.html(`<div class="text-danger">${__("Failed to load storage")}</div>`)
			);
	}

	function backup_now() {
		frappe
			.xcall("cloud_backup.api.backup.upload_latest")
			.then(() => {
				frappe.show_alert({ message: __("Backup queued"), indicator: "green" });
				setTimeout(load, 1500);
			})
			.catch(() => frappe.show_alert({ message: __("Failed to queue backup"), indicator: "red" }));
	}

	function render(d) {
		$body.empty();
		$body.append(headline(d));
		$body.append(summary_row(d.summary || {}));
		const $cols = $('<div class="row"></div>').appendTo($body);
		$cols.append(storage_section());
		$cols.append(trend_section(d.trend || {}));
		$body.append(recent_section(d.recent || []));
	}

	const TILE_BG = {
		total: "rgba(88,116,214,0.10)",
		completed: "rgba(40,167,69,0.10)",
		failed: "rgba(224,54,54,0.10)",
	};

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

	function summary_row(s) {
		const days = s.days || 7;
		const window = __("Last {0} days", [days]);
		const $row = $('<div class="row" style="margin-bottom:16px;"></div>');
		$row.append(stat_tile(__("Total Uploads"), window, s.total || 0, "", TILE_BG.total));
		$row.append(stat_tile(__("Completed"), window, s.completed || 0, "text-success", TILE_BG.completed));
		$row.append(
			stat_tile(__("Failed"), window, s.failed || 0, s.failed ? "text-danger" : "", TILE_BG.failed)
		);
		return $row;
	}

	function stat_tile(label, window, value, cls, bg) {
		return $(
			`<div class="col-sm-4"><div class="cb-tile" style="border:1px solid var(--border-color);` +
				`border-radius:8px;padding:14px 16px;background:${bg};">` +
				`<div style="display:flex;justify-content:space-between;align-items:baseline;">` +
				`<span class="text-muted" style="font-size:12px;">${label}</span>` +
				`<span class="text-muted" style="font-size:11px;">${window}</span></div>` +
				`<div class="${cls}" style="font-size:26px;font-weight:600;">${value}</div></div></div>`
		);
	}

	function storage_section() {
		return $(
			`<div class="col-md-6 cb-storage-col"><h5>${__("Storage")}</h5>` +
				`<div class="cb-storage-body"></div></div>`
		);
	}

	function render_storage($target, storage) {
		$target.empty();
		if (!storage.length) {
			$target.html(`<div class="text-muted">${__("No authorized provider with quota.")}</div>`);
			return;
		}
		const $grid = $(
			'<div style="display:flex;flex-wrap:wrap;gap:10px;"></div>'
		).appendTo($target);
		storage.forEach((e) => $grid.append(storage_card(e)));
	}

	function provider_logo(e) {
		if (!e.logo) return "";
		return (
			`<img src="${e.logo}" alt="" style="width:22px;height:22px;object-fit:contain;` +
			`margin-right:8px;border-radius:4px;">`
		);
	}

	const STORE_CARD =
		"border:1px solid var(--border-color);border-radius:8px;padding:12px 14px;flex:1 1 0;min-width:180px;";

	function storage_card(e) {
		const name = frappe.utils.escape_html(e.provider);
		if (!e.ok) {
			return $(
				`<div class="cb-store" style="${STORE_CARD}display:flex;align-items:center;">` +
					`${provider_logo(e)}<div><b>${name}</b> ` +
					`<span class="text-muted">${frappe.utils.escape_html(
						e.message || __("unavailable")
					)}</span></div></div>`
			);
		}
		const header =
			`<div style="display:flex;justify-content:space-between;align-items:center;">` +
			`<span style="display:flex;align-items:center;">${provider_logo(e)}<b>${name}</b></span>`;
		// Object stores (S3) report bytes used but no account quota (percent null).
		if (e.percent === null || e.percent === undefined) {
			return $(
				`<div class="cb-store" style="${STORE_CARD}">${header}</div>` +
					`<div class="text-muted" style="font-size:12px;margin:6px 0 0;">` +
					`${fmt_bytes(e.used)} ${__("used")} · ${__("no quota limit")}</div></div>`
			);
		}
		const pct = Math.min(100, Math.round(e.percent * 100));
		const bar = e.warn ? "progress-bar-danger" : "progress-bar-success";
		return $(
			`<div class="cb-store" style="${STORE_CARD}">` +
				`${header}${e.warn ? `<span class="indicator-pill red">${__("Near limit")}</span>` : ""}</div>` +
				`<div class="text-muted" style="font-size:12px;margin:6px 0;">${pct}% · ` +
				`${fmt_bytes(e.used)} / ${e.total ? fmt_bytes(e.total) : "∞"}</div>` +
				`<div class="progress" style="height:10px;">` +
				`<div class="progress-bar ${bar}" role="progressbar" style="width:${pct}%;"></div>` +
				`</div></div>`
		);
	}

	function trend_section(trend) {
		const days = (trend.labels || []).length || 7;
		const $col = $(
			`<div class="col-md-6"><h5>${__("Upload Trend")} ` +
				`<span class="text-muted" style="font-size:12px;font-weight:400;">` +
				`${__("Last {0} days", [days])}</span></h5></div>`
		);
		if (!trend.labels || !trend.labels.length) {
			$col.append(`<div class="text-muted">${__("No data.")}</div>`);
			return $col;
		}
		const $chart = $('<div class="cb-chart"></div>').appendTo($col);
		frappe.require("charts.bundle.js", () => {
			new frappe.Chart($chart.get(0), {
				data: {
					labels: trend.labels.map((d) => frappe.datetime.str_to_user(d)),
					datasets: [
						{ name: __("Completed"), values: trend.completed },
						{ name: __("Failed"), values: trend.failed },
					],
				},
				type: "line",
				height: 220,
				colors: ["#28a745", "#e03636"],
				lineOptions: { hideDots: 0, regionFill: 1 },
			});
		});
		return $col;
	}

	function recent_section(recent) {
		const $wrap = $(`<div style="margin-top:8px;"><h5>${__("Recent Uploads")}</h5></div>`);
		if (!recent.length) {
			$wrap.append(`<div class="text-muted">${__("No uploads yet.")}</div>`);
			return $wrap;
		}
		const head =
			`<thead><tr><th>${__("File")}</th><th>${__("Provider")}</th>` +
			`<th>${__("Type")}</th><th>${__("Size")}</th><th>${__("Status")}</th>` +
			`<th>${__("When")}</th></tr></thead>`;
		const rows = recent
			.map((r) => {
				const color = STATUS_COLOR[r.status] || "gray";
				const file = frappe.utils.escape_html(r.remote_file || r.name);
				const when = r.completed_at || r.creation;
				return (
					`<tr><td><a href="/app/cloud-backup-history/${encodeURIComponent(r.name)}">${file}</a></td>` +
					`<td>${frappe.utils.escape_html(r.provider || "")}</td>` +
					`<td>${frappe.utils.escape_html(r.backup_type || "")}</td>` +
					`<td>${r.file_size ? fmt_bytes(r.file_size) : "—"}</td>` +
					`<td><span class="indicator-pill ${color}">${frappe.utils.escape_html(r.status)}</span></td>` +
					`<td class="text-muted">${when ? frappe.datetime.comment_when(when) : "—"}</td></tr>`
				);
			})
			.join("");
		$wrap.append(
			`<div class="table-responsive"><table class="table table-hover">${head}<tbody>${rows}</tbody></table></div>`
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
