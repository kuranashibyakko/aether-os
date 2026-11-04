import json
import re
from typing import Literal, Any
from dotenv import load_dotenv
from groq import Groq
import ollama
from pydantic import BaseModel, Field

from storage_steward import (
    scan_directory_summary,
    find_duplicate_files,
    safe_delete_file,
    auto_organize_directory,
)
from doc_forge import DocumentSpec, compile_docx

load_dotenv()
groq_client = Groq(timeout=25.0)
GROQ_MODEL = "openai/gpt-oss-20b"
OLLAMA_MODEL = "qwen2.5:7b"


class OSAgentPlan(BaseModel):
    thought_process: str = Field(
        description="Brief reasoning explaining which OS actions are needed for the user's request"
    )
    action_type: Literal[
        "deduplicate_and_clean",
        "organize_folder",
        "create_document",
        "full_steward_pipeline",
    ] = Field(description="The OS operation to perform")
    target_directory: str = Field(
        default="sandbox_dir",
        description="Target directory path to manage or save documents into",
    )
    document_spec: DocumentSpec | None = Field(
        default=None,
        description="Required if action_type is 'create_document' or 'full_steward_pipeline'",
    )


def clean_json_output(raw_text: str) -> str:
    """Strips markdown ```json ... ``` fences if present."""
    match = re.search(r"```(?:json)?\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else raw_text.strip()


def plan_os_task(
    user_command: str,
    target_dir: str = "sandbox_dir",
    use_local_ollama: bool = False,
) -> OSAgentPlan:
    """Inspects live directory state and uses the LLM (Ollama offline or Groq)
    to generate a validated OSAgentPlan.
    """
    current_files = scan_directory_summary(target_dir)
    schema_str = json.dumps(OSAgentPlan.model_json_schema(), indent=2)

    system_prompt = (
        "You are Aether-OS, an autonomous Linux system and document steward.\n"
        "Output ONLY a valid JSON instance conforming to the OSAgentPlan schema below.\n"
        "Do NOT output the schema definition itself or extra commentary.\n"
        f"JSON Schema:\n{schema_str}"
    )

    user_prompt = (
        f"TARGET DIRECTORY: {target_dir}\n"
        f"LIVE DIRECTORY FILES: {json.dumps(current_files)}\n"
        f"USER COMMAND: {user_command}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # TODO 1 (Hybrid Offline Ollama / Cloud Groq Call):
    if use_local_ollama:
        res = ollama.chat(model=OLLAMA_MODEL, messages=messages, format="json")
        raw_reply = res["message"]["content"]
    else:
        res = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.0,
        )
        raw_reply = res.choices[0].message.content or ""

    return OSAgentPlan.model_validate_json(clean_json_output(raw_reply))


def execute_os_plan(plan: OSAgentPlan) -> dict[str, Any]:
    """Deterministically executes a validated OSAgentPlan against the local filesystem."""
    results: dict[str, Any] = {
        "action_type": plan.action_type,
        "thought_process": plan.thought_process,
        "trashed_duplicates": [],
        "organized_files": {},
        "generated_docx": None,
    }

    # TODO 2 (Storage Deduplication & Organization):
    # 1. Deduplicate & Clean
    if plan.action_type in ("deduplicate_and_clean", "full_steward_pipeline"):
        dups = find_duplicate_files(plan.target_directory)
        for d in dups:
            safe_delete_file(d)
            results["trashed_duplicates"].append(d)

    # 2. Auto-organize
    if plan.action_type in ("organize_folder", "full_steward_pipeline"):
        results["organized_files"] = auto_organize_directory(plan.target_directory)

    # TODO 3 (LibreOffice / Word Document Generation):
    if plan.action_type in ("create_document", "full_steward_pipeline") and plan.document_spec is not None:
        results["generated_docx"] = compile_docx(
            plan.document_spec, output_dir=plan.target_directory
        )

    return results


if __name__ == "__main__":
    import shutil
    from pathlib import Path

    # Prepare messy sandbox directory
    sandbox = Path("sandbox_dir")
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(exist_ok=True)

    (sandbox / "kernel_log.txt").write_text("GPU VRAM nominal at 4.2GB", encoding="utf-8")
    (sandbox / "kernel_log_backup_copy.txt").write_text("GPU VRAM nominal at 4.2GB", encoding="utf-8")
    (sandbox / "telemetry.csv").write_text("temp,fan\n62,1800", encoding="utf-8")
    (sandbox / "cleanup.py").write_text("print('cleaning')", encoding="utf-8")

    command = (
        "Run a full steward pipeline on sandbox_dir: remove any duplicate files, "
        "organize the remaining files into folders, and create a Word document named "
        "'storage_audit_report.docx' summarizing the directory cleanup and file metrics."
    )

    print(f"🚀 [Aether-OS] Executing Command:\n  '{command}'\n")
    plan = plan_os_task(command, target_dir="sandbox_dir", use_local_ollama=False)
    print(f"🧠 Agent Plan ({plan.action_type}): {plan.thought_process}")

    summary = execute_os_plan(plan)
    print("\n✅ Execution Telemetry:")
    print(json.dumps(summary, indent=2))