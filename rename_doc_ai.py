#!/usr/bin/env python3
"""
Generate a good document filename with a local offline LLM, optionally rename file.

Example:
  python rename_doc_ai.py "C:\\docs\\scan.pdf" --rename
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

import fitz  # PyMuPDF
import requests
from docx import Document


def extract_text_from_pdf(path: Path, max_pages: int, max_chars: int) -> str:
    chunks: list[str] = []
    total = 0
    with fitz.open(path) as doc:
        for page_index in range(min(len(doc), max_pages)):
            page_text = doc[page_index].get_text("text").strip()
            if not page_text:
                continue
            remaining = max_chars - total
            if remaining <= 0:
                break
            if len(page_text) > remaining:
                page_text = page_text[:remaining]
            chunks.append(page_text)
            total += len(page_text)
    return "\n\n".join(chunks).strip()


def extract_text_from_docx(path: Path, max_chars: int) -> str:
    doc = Document(str(path))
    joined = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return joined[:max_chars].strip()


def extract_text(path: Path, max_pages: int, max_chars: int) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path, max_pages=max_pages, max_chars=max_chars)
    if suffix == ".docx":
        return extract_text_from_docx(path, max_chars=max_chars)
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars].strip()
    raise ValueError(
        f"Unsupported file type: {suffix}. Supported: .pdf, .docx, .txt, .md, .csv, .json"
    )


def build_prompt(document_text: str, original_name: str) -> str:
    return f"""
You create precise, human-friendly file names for documents.
Return only one filename stem (no file extension), no quotes, no markdown.
Use this format when possible: YYYY-MM-DD_topic_or_title_optional_source
Rules:
- Keep it short and specific.
- Use lowercase snake_case.
- Include date only if clearly present in the text.
- Avoid generic words like document/file/scan/new.
- Do not invent facts.

Original filename: {original_name}

Document content:
{document_text}
""".strip()


def query_ollama(prompt: str, model: str, host: str, timeout_sec: int = 120) -> str:
    url = host.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        response = requests.post(url, json=payload, timeout=timeout_sec)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            "Could not reach local Ollama server. Is it running?\n"
            f"Host: {host}\n"
            f"Original error: {exc}"
        ) from exc

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama returned non-JSON response.") from exc

    text = data.get("response", "").strip()
    if not text:
        raise RuntimeError("Ollama returned an empty response.")
    return text.splitlines()[0].strip()


def is_local_ollama_host(host: str) -> bool:
    parsed = urlparse(host)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def ollama_is_healthy(host: str, timeout_sec: int = 2) -> bool:
    url = host.rstrip("/") + "/api/tags"
    try:
        response = requests.get(url, timeout=timeout_sec)
        return response.ok
    except requests.RequestException:
        return False


def start_ollama_serve() -> subprocess.Popen:
    try:
        return subprocess.Popen(  # noqa: S603
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Could not start Ollama automatically because `ollama` was not found in PATH."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to start `ollama serve`: {exc}") from exc


def wait_for_ollama(host: str, timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if ollama_is_healthy(host):
            return True
        time.sleep(0.4)
    return False


def stop_ollama_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    with suppress(OSError):
        proc.terminate()
    try:
        proc.wait(timeout=4)
    except subprocess.TimeoutExpired:
        with suppress(OSError):
            proc.kill()


def sanitize_stem(stem: str, fallback: str = "renamed_document") -> str:
    # Strip common wrappers from LLM output.
    stem = stem.strip().strip("\"'`")
    stem = re.sub(r"^[a-zA-Z0-9 _-]*:\s*", "", stem)

    # Normalize separators and remove invalid Windows filename chars.
    stem = stem.replace(" ", "_")
    stem = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "", stem)
    stem = re.sub(r"_+", "_", stem)
    stem = stem.strip("._- ")

    if not stem:
        stem = fallback
    return stem[:120]


def unique_target_path(original: Path, new_stem: str) -> Path:
    candidate = original.with_name(new_stem + original.suffix.lower())
    if not candidate.exists() or candidate == original:
        return candidate

    n = 2
    while True:
        numbered = original.with_name(f"{new_stem}_{n}{original.suffix.lower()}")
        if not numbered.exists():
            return numbered
        n += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a proper document name with an offline local AI model."
    )
    parser.add_argument("input_file", type=Path, help="Path to the input document.")
    parser.add_argument(
        "--model",
        default="qwen2.5:14b-instruct",
        help="Local Ollama model name (default: qwen2.5:14b-instruct).",
    )
    parser.add_argument(
        "--host",
        default="http://127.0.0.1:11434",
        help="Ollama API host (default: http://127.0.0.1:11434).",
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Actually rename the input file to the AI-suggested name.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=8,
        help="Maximum PDF pages to read (default: 8).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=16000,
        help="Maximum characters extracted from document (default: 16000).",
    )
    parser.add_argument(
        "--auto-start-ollama",
        action="store_true",
        help="Start `ollama serve` automatically if the Ollama API is not reachable.",
    )
    parser.add_argument(
        "--keep-ollama-running",
        action="store_true",
        help="If auto-start was used, do not stop the started Ollama process at the end.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=30,
        help="Seconds to wait for auto-started Ollama to become ready (default: 30).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path: Path = args.input_file.expanduser().resolve()
    started_ollama_proc: subprocess.Popen | None = None

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1
    if not input_path.is_file():
        print(f"Error: Not a file: {input_path}", file=sys.stderr)
        return 1

    try:
        if args.auto_start_ollama and not ollama_is_healthy(args.host):
            if not is_local_ollama_host(args.host):
                raise RuntimeError(
                    "Auto-start is only supported for local hosts "
                    "(localhost / 127.0.0.1 / ::1)."
                )
            print("Ollama not reachable. Starting `ollama serve`...")
            started_ollama_proc = start_ollama_serve()
            if not wait_for_ollama(args.host, timeout_sec=max(3, args.startup_timeout)):
                raise RuntimeError(
                    "Started `ollama serve`, but API did not become ready in time."
                )
            print("Ollama is ready.")

        text = extract_text(
            input_path,
            max_pages=max(1, args.max_pages),
            max_chars=max(1000, args.max_chars),
        )
        if not text:
            raise RuntimeError("No readable text found in document.")

        prompt = build_prompt(text, input_path.stem)
        raw_name = query_ollama(prompt, model=args.model, host=args.host)
        safe_stem = sanitize_stem(raw_name, fallback=input_path.stem)
        target = unique_target_path(input_path, safe_stem)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if started_ollama_proc and not args.keep_ollama_running:
            print("Stopping auto-started Ollama process...")
            stop_ollama_process(started_ollama_proc)

    print(f"Suggested name: {target.name}")
    if not args.rename:
        print("Preview mode only. Re-run with --rename to apply.")
        return 0

    try:
        input_path.rename(target)
    except OSError as exc:
        print(f"Rename failed: {exc}", file=sys.stderr)
        return 3

    print(f"Renamed:\n  {input_path.name}\n  -> {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
