# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Notify administrators of important Cloud Backup events."""

from __future__ import annotations

import frappe

from cloud_backup.cloud_backup.doctype.cloud_backup_settings.cloud_backup_settings import (
	get_cloud_backup_settings,
)


def notify(subject: str, message: str, force: bool = False) -> None:
	"""In-app + email to System Managers when notifications are enabled. Never raises."""
	try:
		settings = get_cloud_backup_settings()
		if not settings.notifications_enabled and not force:
			return
		recipients = _recipients()
		if not recipients:
			return
		for user in recipients:
			_in_app(user, subject, message)
		frappe.sendmail(recipients=recipients, subject=subject, message=message)
	except Exception:
		frappe.log_error(title="Cloud Backup Notification", message=subject)


def _recipients() -> list[str]:
	"""Enabled System Manager users that have an email address."""
	users = frappe.get_all(
		"Has Role",
		filters={"role": "System Manager", "parenttype": "User"},
		pluck="parent",
	)
	out = []
	for user in set(users):
		if user in ("Administrator", "Guest"):
			continue
		if frappe.db.get_value("User", user, "enabled"):
			out.append(user)
	return out


def _in_app(user: str, subject: str, message: str) -> None:
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"for_user": user,
			"type": "Alert",
			"subject": subject,
			"email_content": message,
			"document_type": "Cloud Backup Settings",
			"document_name": "Cloud Backup Settings",
		}
	).insert(ignore_permissions=True)
