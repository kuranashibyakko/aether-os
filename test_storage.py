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
