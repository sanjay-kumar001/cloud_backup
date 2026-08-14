# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""bench cloud-backup command group."""

import click
import frappe
from frappe.commands import get_site

from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
	get_cloud_backup_settings,
)


@click.group("cloud-backup", invoke_without_command=True)
@click.option("--with-files", is_flag=True, default=False, help="Include file backups")
@click.pass_context
def cloud_backup(ctx, with_files):
	"""Create a backup and upload it to the configured provider."""
	if ctx.invoked_subcommand is None:
		_dispatch(ctx, lambda: _upload(with_files))


@cloud_backup.command("test")
@click.pass_context
def test_connection(ctx):
	"""Test connectivity to the configured provider."""
	_dispatch(ctx, _test)


@cloud_backup.command("list")
@click.option("--limit", default=10, help="Number of rows")
@click.pass_context
def list_history(ctx, limit):
	"""List recent backup upload history."""
	_dispatch(ctx, lambda: _list(limit))


@cloud_backup.command("cleanup")
@click.pass_context
def cleanup(ctx):
	"""Run retention cleanup now."""
	_dispatch(ctx, _cleanup)


@cloud_backup.command("status")
@click.pass_context
def status(ctx):
	"""Show last-upload status and health."""
	_dispatch(ctx, _status)


commands = [cloud_backup]


def _dispatch(ctx, action) -> None:
	"""Run an action inside a site context; exit non-zero on failure (FR-55)."""
	frappe.init(site=get_site(ctx.obj))
	frappe.connect()
	code = 1
	try:
		code = action() or 0
	except Exception as exc:
		click.secho(str(exc), fg="red", err=True)
	finally:
		frappe.destroy()
	if code:
		raise SystemExit(code)


def _upload(with_files: bool) -> int:
	from frappe.utils.backups import new_backup

	from cloud_backup.services import backup_service

	provider = backup_service.resolve_provider()
	if not provider:
		click.secho("No authorized provider with a destination (default or fallback).", fg="red", err=True)
		return 1
	odb = new_backup(ignore_files=not with_files)
	artifacts = {"database"} | ({"public", "private"} if with_files else set())
	results = backup_service.upload_artifacts_sync(
		provider,
		artifacts,
		lambda a: getattr(odb, backup_service.ARTIFACT_PATH_ATTR[a], None),
		trigger="cli",
	)
	if not results:
		click.secho("No backup artifacts to upload.", fg="yellow")
		return 1
	for name, ok in results:
		click.secho(f"{'OK  ' if ok else 'FAIL'} {name}", fg="green" if ok else "red")
	return 0 if all(ok for _, ok in results) else 1


def _test() -> int:
	from cloud_backup.services import backup_service, provider_service

	provider = backup_service.resolve_provider()
	if not provider:
		click.secho("No authorized provider (default or fallback).", fg="red", err=True)
		return 1
	result = provider_service.get_provider(provider).test_connection()
	click.secho(result.get("message", ""), fg="green" if result.get("ok") else "red")
	return 0 if result.get("ok") else 1


def _list(limit: int) -> int:
	rows = frappe.get_all(
		"Cloud Backup History",
		fields=["name", "backup_type", "status", "file_size", "completed_at"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	if not rows:
		click.echo("No history.")
		return 0
	for r in rows:
		click.echo(
			f"{r.name}  {r.backup_type or '-':8}  {r.status or '-':10}  {r.file_size or 0:>12}  {r.completed_at or ''}"
		)
	return 0


def _cleanup() -> int:
	from cloud_backup.services import retention_service

	result = retention_service.run_cleanup()
	if result.get("skipped"):
		click.secho("Cleanup skipped (auto_delete_remote is off).", fg="yellow")
		return 0
	click.secho(f"Deleted {result['deleted']} of {result['candidates']} candidate(s).", fg="green")
	return 0


def _status() -> int:
	settings = get_cloud_backup_settings()
	total = frappe.db.count("Cloud Backup History")
	failed = frappe.db.count("Cloud Backup History", {"status": "Failed"})
	click.echo(f"Provider:    {settings.default_provider or '-'}")
	click.echo(f"Enabled:     {bool(settings.enabled)}   Auto-upload: {bool(settings.automatic_upload)}")
	click.echo(f"Last upload: {settings.last_upload_status or '-'} @ {settings.last_upload_timestamp or '-'}")
	click.echo(f"History:     {total} total, {failed} failed")
	return 1 if settings.last_upload_status == "Failed" else 0
