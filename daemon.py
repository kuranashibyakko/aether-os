import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage_steward import (
    auto_organize_directory,
    find_duplicate_files,
    safe_delete_file,
)


def daemon_tick(
    watch_dir: str,
    trash_dir: str = ".aether_trash",
    log_file: str = ".aether_daemon.jsonl",
) -> dict[str, Any]:
    """Executes a single atomic sweep of `watch_dir`:
    1. Detects and trashes exact SHA-256 duplicates.
    2. Organizes remaining top-level loose files into category folders.
    3. Logs an audit entry to `log_file` ONLY if actions were taken.
    """
    root = Path(watch_dir)

    if not root.exists():
        return {
            "trashed": [],
            "organized": {},
            "action_taken": False,
        }

    trashed_files: list[str] = []

    # Step 1: Detect and trash duplicates
    dups = find_duplicate_files(watch_dir)

    for d in dups:
        safe_delete_file(d, trash_dir=trash_dir)
        trashed_files.append(Path(d).name)

    # Step 2: Organize remaining files
    organized = auto_organize_directory(watch_dir)

    action_taken = bool(trashed_files or organized)

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "watch_dir": str(root.resolve()),
        "trashed": trashed_files,
        "organized": organized,
        "action_taken": action_taken,
    }

    # Step 3: Append telemetry log when actions occurred
    if action_taken:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    return event


def run_daemon(
    watch_dir: str = "sandbox_dir",
    trash_dir: str = ".aether_trash",
    poll_interval: float = 2.0,
    max_ticks: int | None = None,
) -> list[dict[str, Any]]:
    """Runs the background folder-watcher loop until `max_ticks` or KeyboardInterrupt."""
    print(
        f"👁️  [Aether-OS Daemon] Watching '{watch_dir}' "
        f"(interval={poll_interval}s)..."
    )

    ticks = 0
    action_events: list[dict[str, Any]] = []

    try:
        while max_ticks is None or ticks < max_ticks:
            event = daemon_tick(watch_dir, trash_dir=trash_dir)

            if event["action_taken"]:
                print(
                    f"⚡ [Daemon Sweep #{ticks + 1}] "
                    f"Trashed={event['trashed']} | "
                    f"Organized={event['organized']}"
                )
                action_events.append(event)

            ticks += 1

            if max_ticks is None or ticks < max_ticks:
                time.sleep(poll_interval)

    except KeyboardInterrupt:
        print("\n🛑 [Aether-OS Daemon] Gracefully stopped by user.")

    return action_events


if __name__ == "__main__":
    import shutil

    sandbox = Path("sandbox_dir")

    if sandbox.exists():
        shutil.rmtree(sandbox)

    sandbox.mkdir(exist_ok=True)

    # Simulate a user dropping messy files & duplicates into the watched folder
    (sandbox / "invoice_jan.pdf").write_text(
        "PDF_BYTES_101",
        encoding="utf-8",
    )

    (sandbox / "invoice_jan_copy.pdf").write_text(
        "PDF_BYTES_101",
        encoding="utf-8",
    )

    (sandbox / "dataset.csv").write_text(
        "id,val\n1,99",
        encoding="utf-8",
    )

    # Run 2 ticks in demo mode so it sweeps the dropped files and exits cleanly
    events = run_daemon(
        watch_dir="sandbox_dir",
        poll_interval=0.5,
        max_ticks=2,
    )

    print(f"\n✅ Daemon completed {len(events)} active sweep(s).")