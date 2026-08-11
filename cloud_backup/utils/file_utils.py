# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Pure filesystem helpers (no Frappe DB access)."""

from __future__ import annotations

import os
import re
from datetime import datetime


def file_extension(path: str) -> str:
	"""Return the compound extension (e.g. '.sql.gz', '.tar')."""
	name = os.path.basename(path)
	_stem, dot, rest = name.partition(".")
	return f".{rest}" if dot else ""


def slugify_site(site: str) -> str:
	"""Return a filesystem/cloud-safe token for a site name."""
	return re.sub(r"[^A-Za-z0-9]+", "_", site).strip("_")


def build_remote_filename(
	site: str, label: str, local_path: str, timestamp: datetime | None = None
) -> str:
	"""Build '{site}_{label}_{YYYYMMDD_HHMMSS}{ext}' from the local file."""
	stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
	return f"{slugify_site(site)}_{label}_{stamp}{file_extension(local_path)}"
