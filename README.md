# 🖥️ aether-os (`v2.0`)

An offline-capable **Linux System & Document Steward Agent** powered by local LLM inference (**Ollama** / **Groq**), **Pydantic** schema enforcement, transactional **Trash Manifest Recovery**, a **Background Watchdog Daemon**, and headless **LibreOffice / Word (`.docx`)** compilation.

## ✨ Core Architecture (`v2.0`)
1. **Transactional Storage Steward (`storage_steward.py`):**
   - Scans live directory metadata without loading heavy file payloads into context.
   - Eliminates redundant files with 100% mathematical certainty via **SHA-256** chunked content hashing.
   - Protects against accidental deletion using a reversible `.aether_trash` vault and `restore_from_trash()` recovery via `manifest.json`.
2. **Background Watchdog Daemon (`daemon.py`):**
   - Continuously monitors target directories using an atomic, idempotent `daemon_tick()` architecture.
   - Automatically deduplicates and sorts newly dropped files while writing structured audit events to `.aether_daemon.jsonl`.
3. **Headless Document Forge (`doc_forge.py`):**
   - Compiles nested Pydantic `DocumentSpec` schemas directly into formatted `.docx` reports (headings, bullet lists, and metric tables) for LibreOffice Writer or MS Word.
4. **Hybrid Offline/Cloud Agent Brain (`aether_agent.py`):**
   - Routes natural-language OS commands into strictly validated `OSAgentPlan` actions using local 7B models on an 8GB VRAM budget (`qwen2.5:7b` via Ollama) or cloud inference (`Groq`).

## 🚀 Quickstart
```bash
pytest -v
python storage_steward.py
python doc_forge.py
python aether_agent.py
python daemon.py
