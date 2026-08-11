# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Scheduled/manual entrypoint for cloud retention cleanup."""

from __future__ import annotations

from cloud_backup.services import retention_service


def run(dry_run: bool = False) -> dict:
	"""Run the Settings-gated retention cleanup."""
	return retention_service.run_cleanup(dry_run=bool(dry_run))
