"""Service layer: wraps the internetarchive library for the GUI."""

from archivary.services.ia_service import (
    DEFAULT_RETRIES,
    DownloadOptions,
    DownloadSpec,
    IAService,
    UploadFile,
    UploadOptions,
    collect_upload_files,
    friendly_url_to_identifier,
    human_eta,
    human_size,
    human_speed,
    md5_file,
)
from archivary.services.spreadsheet import (
    export_results,
    parse_metadata_rows,
    parse_upload_rows,
    read_table,
    write_template,
)

__all__ = [
    "IAService",
    "UploadFile",
    "UploadOptions",
    "DownloadSpec",
    "DownloadOptions",
    "collect_upload_files",
    "md5_file",
    "friendly_url_to_identifier",
    "human_size",
    "human_speed",
    "human_eta",
    "DEFAULT_RETRIES",
    "read_table",
    "parse_upload_rows",
    "parse_metadata_rows",
    "export_results",
    "write_template",
]
