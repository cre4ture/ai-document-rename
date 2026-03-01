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
python rename_doc_ai.py "C:\path\to\document.pdf"
```

Rename automatically:

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" --rename
```

Auto-start local Ollama if needed (and stop it when done):

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" --rename --auto-start-ollama
```

Use another local model:

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" --model llama3.1:8b --rename
```

Keep auto-started Ollama running after the script exits:

```powershell
python rename_doc_ai.py "C:\path\to\document.pdf" --auto-start-ollama --keep-ollama-running
```

## Notes

- The script uses `http://127.0.0.1:11434` by default (local Ollama API).
- `--auto-start-ollama` only works for local hosts (`localhost`, `127.0.0.1`, `::1`).
- By default, if this script starts Ollama, it stops that started process at the end.
- If the generated name already exists, it appends `_2`, `_3`, etc.
- Nothing is uploaded to cloud services by this script.
