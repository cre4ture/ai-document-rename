# AI Document Rename (Offline, Local Model)

This project provides a simple Python script that:

1. Reads document text (PDF, DOCX, TXT/MD/CSV/JSON)
2. Sends it to a local offline LLM via Ollama
3. Suggests a clean filename
4. Optionally renames the file automatically

## 1) Install prerequisites

- Python 3.10+. E.g. `winget install 9NQ7512CXL7T` in PowerShell worked for me.
- [Ollama](https://ollama.com/) installed locally. E.g. `irm https://ollama.com/install.ps1 | iex` in PowerShell worked for me.

Then pull a strong local model (example):

```powershell
ollama pull qwen2.5:14b-instruct
```

## 2) Install Python deps

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3) Usage

Preview suggested name only:

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" "C:\path\to\invoice.docx"
```

Rename automatically:

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" "C:\path\to\invoice.docx" --rename
```

Auto-start local Ollama if needed (and stop it when done):

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" "C:\path\to\invoice.docx" --rename --auto-start-ollama
```

Use another local model:

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" "C:\path\to\invoice.docx" --model llama3.1:8b --rename
```

Increase generation timeout for slower local inference (CPU / large model):

```powershell
python rename_doc_ai.py "*.pdf" --request-timeout 600
```

Keep auto-started Ollama running after the script exits:

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" "C:\path\to\invoice.docx" --auto-start-ollama --keep-ollama-running
```

Wildcard input (`*.pdf`):

```powershell
python rename_doc_ai.py "*.pdf"
python rename_doc_ai.py ".\inbox\*.pdf" ".\inbox\*.docx" --rename
python rename_doc_ai.py "**/*.pdf" --rename
```

Windows shell behavior:

- On Linux/macOS shells (bash/zsh), unquoted wildcards are usually expanded by the shell.
- On Windows `PowerShell` and `cmd.exe`, native app arguments are usually passed through, so shell expansion is not guaranteed.
- This script expands glob patterns itself, so quoted patterns like `"*.pdf"` work consistently across shells.

## Notes

- The script uses `http://127.0.0.1:11434` by default (local Ollama API).
- `--auto-start-ollama` only works for local hosts (`localhost`, `127.0.0.1`, `::1`).
- By default, if this script starts Ollama, it stops that started process at the end.
- With multiple files, auto-start/stop is done once for the whole run, not per file.
- You can pass one or many input files in a single run.
- If the generated name already exists, it appends `_2`, `_3`, etc.
- Nothing is uploaded to cloud services by this script.
- If you get generation timeouts, increase `--request-timeout` and/or reduce `--max-pages` and `--max-chars`.
