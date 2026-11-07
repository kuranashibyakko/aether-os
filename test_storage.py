import shutil
from pathlib import Path
from storage_steward import (
    scan_directory_summary,
    find_duplicate_files,
    safe_delete_file,
    auto_organize_directory,
)

def test_storage_lifecycle(tmp_path: Path):
    f1 = tmp_path / "doc1.txt"
    f2 = tmp_path / "doc1_copy.txt"
    f3 = tmp_path / "script.py"
    trash = tmp_path / ".trash"

    f1.write_text("identical payload", encoding="utf-8")
    f2.write_text("identical payload", encoding="utf-8")
    f3.write_text("print(1)", encoding="utf-8")

    # 1. Scan
    summary = scan_directory_summary(str(tmp_path))
    assert len(summary) == 3

    # 2. Duplicate detection via SHA-256
    dups = find_duplicate_files(str(tmp_path))
    assert len(dups) == 1
    assert dups[0].endswith("doc1_copy.txt")

    # 3. Safe delete to trash
    res = safe_delete_file(dups[0], trash_dir=str(trash))
    assert res["status"] == "trashed"
    assert not f2.exists()
    assert (trash / "doc1_copy.txt").exists()

    # 4. Auto-organize remaining files
    org = auto_organize_directory(str(tmp_path))
    assert "Documents" in org
    assert "Code" in org
    assert (tmp_path / "Documents" / "doc1.txt").exists()
    assert (tmp_path / "Code" / "script.py").exists()


from docx import Document
from doc_forge import DocumentSpec, DocSection, KeyValueRow, compile_docx

def test_doc_forge_compilation(tmp_path: Path):
    spec = DocumentSpec(
        filename="test_report",
        title="System Diagnostic Report",
        sections=[
            DocSection(
                heading="Memory Analysis",
                body="All allocations nominal.",
                bullet_points=["8GB VRAM", "16GB System RAM"],
            )
        ],
        summary_table=[KeyValueRow(metric="Status", value="HEALTHY")],
    )

    out_file = compile_docx(spec, output_dir=str(tmp_path))
    assert Path(out_file).exists()
    assert out_file.endswith("test_report.docx")

    # Re-open the generated .docx file and verify its contents!
    loaded = Document(out_file)
    all_text = "\n".join(p.text for p in loaded.paragraphs)
    assert "System Diagnostic Report" in all_text
    assert "Memory Analysis" in all_text
    assert len(loaded.tables) == 1
    assert loaded.tables[0].rows[1].cells[0].text == "Status"
    assert loaded.tables[0].rows[1].cells[1].text == "HEALTHY"


from aether_agent import OSAgentPlan, execute_os_plan

def test_aether_agent_full_pipeline_execution(tmp_path: Path):
    # Create duplicate + mixed files in tmp_path
    (tmp_path / "a.txt").write_text("same content", encoding="utf-8")
    (tmp_path / "a_dup.txt").write_text("same content", encoding="utf-8")
    (tmp_path / "data.csv").write_text("x,y\n1,2", encoding="utf-8")

    plan = OSAgentPlan(
        thought_process="Clean duplicates, organize files, and generate audit report.",
        action_type="full_steward_pipeline",
        target_directory=str(tmp_path),
        document_spec=DocumentSpec(
            filename="audit.docx",
            title="Storage Audit",
            sections=[DocSection(heading="Summary", body="Cleaned 1 duplicate.")],
        ),
    )

    res = execute_os_plan(plan)
    assert len(res["trashed_duplicates"]) == 1
    assert "Documents" in res["organized_files"]
    assert "Data" in res["organized_files"]
    assert res["generated_docx"] is not None
    assert Path(res["generated_docx"]).exists()


from storage_steward import restore_from_trash
from daemon import daemon_tick

def test_restore_from_trash(tmp_path: Path):
    target_file = tmp_path / "important_key.txt"
    trash_dir = tmp_path / ".trash"
    target_file.write_text("SECRET_PAYLOAD", encoding="utf-8")

    # 1. Safe delete
    safe_delete_file(str(target_file), trash_dir=str(trash_dir))
    assert not target_file.exists()

    # 2. Restore from trash using manifest.json
    res = restore_from_trash("important_key.txt", trash_dir=str(trash_dir))
    assert res["status"] == "restored"
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "SECRET_PAYLOAD"


def test_daemon_tick_idempotency(tmp_path: Path):
    watch_dir = tmp_path / "watch"
    trash_dir = tmp_path / ".trash"
    log_file = tmp_path / "daemon.jsonl"
    watch_dir.mkdir()

    (watch_dir / "a.txt").write_text("dup", encoding="utf-8")
    (watch_dir / "b.txt").write_text("dup", encoding="utf-8")
    (watch_dir / "code.py").write_text("x = 1", encoding="utf-8")

    # Tick 1: Should trash 1 duplicate, organize remaining 2 files, and log event
    ev1 = daemon_tick(str(watch_dir), trash_dir=str(trash_dir), log_file=str(log_file))
    assert ev1["action_taken"] is True
    assert len(ev1["trashed"]) == 1
    assert "Documents" in ev1["organized"]
    assert "Code" in ev1["organized"]
    assert log_file.exists()

    # Tick 2: Folder is already clean; should take NO action
    ev2 = daemon_tick(str(watch_dir), trash_dir=str(trash_dir), log_file=str(log_file))
    assert ev2["action_taken"] is False
    assert len(log_file.read_text(encoding="utf-8").strip().splitlines()) == 1
