# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""OneDrive (Microsoft Graph) REST endpoint constants; auth via MSAL."""

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_DRIVE = f"{GRAPH_BASE}/me/drive"

# 320 KiB multiple, required by Graph upload-session chunking.
GRAPH_CHUNK_SIZE = 5 * 320 * 1024
