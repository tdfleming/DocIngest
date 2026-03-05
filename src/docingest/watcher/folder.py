"""Folder watcher service.

Monitors /data/inbox/{tenant_id}/ directories for new files.
Submits them to the ingestion API and moves to processed/ or failed/.
"""

import asyncio
import shutil
from pathlib import Path

import httpx
import structlog

from docingest.config import settings

log = structlog.get_logger()

SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".docx"}


async def _submit_file(
    http_client: httpx.AsyncClient, file_path: Path, tenant_id: str, api_key: str
) -> bool:
    """Submit a file to the ingestion API."""
    api_url = f"http://ingestion-api:{settings.api_port}/v1/documents"

    try:
        with open(file_path, "rb") as f:
            response = await http_client.post(
                api_url,
                files={"file": (file_path.name, f)},
                headers={"X-API-Key": api_key},
            )
        response.raise_for_status()
        result = response.json()
        log.info("file submitted", file=file_path.name, tenant=tenant_id, result=result)
        return True
    except Exception as e:
        log.error("file submission failed", file=file_path.name, error=str(e))
        return False


def _move_file(file_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(file_path), str(dest_dir / file_path.name))


async def _process_tenant_folder(
    http_client: httpx.AsyncClient, tenant_dir: Path, tenant_id: str, api_key: str
) -> None:
    """Process all new files in a tenant's inbox folder."""
    processed_dir = tenant_dir / "processed"
    failed_dir = tenant_dir / "failed"

    for file_path in tenant_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        success = await _submit_file(http_client, file_path, tenant_id, api_key)
        if success:
            _move_file(file_path, processed_dir)
        else:
            _move_file(file_path, failed_dir)
            # Write error sidecar
            error_file = failed_dir / f"{file_path.name}.error"
            error_file.write_text("Submission to ingestion API failed")


async def watch_loop(tenant_keys: dict[str, str]) -> None:
    """Main watch loop. tenant_keys maps tenant_id -> api_key.

    Polls the watch folder for each tenant at the configured interval.
    """
    watch_root = Path(settings.watch_folder)
    interval = settings.watch_poll_interval

    log.info("folder watcher started", watch_root=str(watch_root), interval=interval)

    async with httpx.AsyncClient(timeout=120) as http_client:
        while True:
            for tenant_id, api_key in tenant_keys.items():
                tenant_dir = watch_root / tenant_id
                if not tenant_dir.exists():
                    tenant_dir.mkdir(parents=True, exist_ok=True)
                    continue

                try:
                    await _process_tenant_folder(
                        http_client, tenant_dir, tenant_id, api_key
                    )
                except Exception as e:
                    log.error("watch error", tenant=tenant_id, error=str(e))

            await asyncio.sleep(interval)


def main() -> None:
    """Entry point for the folder watcher service.

    In production, tenant_keys would be loaded from MongoDB or environment.
    """
    import json
    import os

    # Load tenant keys from WATCHER_TENANT_KEYS env var (JSON: {"tenant_id": "api_key"})
    raw = os.environ.get("WATCHER_TENANT_KEYS", "{}")
    tenant_keys = json.loads(raw)

    if not tenant_keys:
        log.warning("no tenant keys configured, watcher idle")

    asyncio.run(watch_loop(tenant_keys))


if __name__ == "__main__":
    main()
