"""Locate and drive the globally installed 1688-cli through node."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROFILE_DIR = Path(os.path.expanduser("~")) / ".1688" / "profiles" / "default"


class CliError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message or code)
        self.code = code

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.code}: {self.args[0]}" if self.args and self.args[0] else self.code


def _which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for cand in (
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "nodejs" / f"{name}.exe",
        Path(os.environ.get("APPDATA", "")) / "npm" / f"{name}.cmd",
    ):
        if cand.exists():
            return str(cand)
    return None


NODE = _which("node")

_CANDIDATE_ROOTS = [
    os.environ.get("BB1688_NODE_ROOT"),
    os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules"),
    "/usr/local/lib/node_modules",
    "/usr/lib/node_modules",
]


def _global_roots() -> list[Path]:
    roots: list[Path] = []
    for raw in _CANDIDATE_ROOTS:
        if not raw:
            continue
        p = Path(raw)
        if p.exists():
            roots.append(p)
    if not roots and NODE:
        try:
            out = subprocess.run([NODE, "-e", "process.stdout.write(require('path').dirname(require.resolve('1688-cli/package.json')))"],
                                 capture_output=True, text=True, timeout=30)
            if out.returncode == 0 and out.stdout.strip():
                roots.append(Path(out.stdout.strip()).parent)
        except Exception:
            pass
    return roots


def cli_js() -> str:
    env_override = os.environ.get("BB1688_CLI_JS")
    if env_override and Path(env_override).exists():
        return env_override
    for root in _global_roots():
        cand = root / "1688-cli" / "dist" / "cli.js"
        if cand.exists():
            return str(cand)
    raise CliError("CLI_NOT_FOUND", "1688-cli is not installed globally (npm i -g 1688-cli)")


def chrome_path() -> str | None:
    for c in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
    ):
        if c.exists():
            return str(c)
    return None


def run(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    if not NODE:
        raise CliError("NODE_MISSING", "node executable not found in PATH")
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    cmd = [NODE, cli_js(), *args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env, timeout=timeout)


def _parse_json(text: str):
    """CLI prints progress lines to stdout, so fall back to slicing the payload."""
    text = text.replace("\ufeff", "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                continue
    return None


def run_json(args: list[str], timeout: int = 300) -> dict:
    proc = run([*args, "--json"], timeout=timeout)
    data = _parse_json(proc.stdout)
    if data is None:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise CliError("BAD_OUTPUT", msg[:400] or "1688-cli returned no JSON")
    if data.get("ok") is False:
        raise CliError(str(data.get("code") or "ERROR"), str(data.get("message") or ""))
    return data


def doctor() -> dict:
    proc = run(["doctor", "--json"], timeout=180)
    return _parse_json(proc.stdout) or {}


def whoami() -> dict:
    proc = run(["whoami", "--json"], timeout=120)
    return _parse_json(proc.stdout) or {}


def offer_details(offer_ids: list[str], chunk: int = 10, pause: float = 2.0) -> dict[str, dict]:
    """Fetch offer detail (MOQ, price tiers, supplier) for a batch of offer ids."""
    import time

    out: dict[str, dict] = {}
    ids = [str(i) for i in offer_ids if i]
    for i in range(0, len(ids), chunk):
        batch = ids[i:i + chunk]
        try:
            data = run_json(["offer", *batch], timeout=420)
        except CliError:
            continue
        offers = data.get("offers")
        if offers is None and data.get("offerId"):
            offers = [data]  # single-id calls return the offer object itself
        for o in offers or []:
            oid = str(o.get("offerId") or "")
            if oid:
                out[oid] = o
        if i + chunk < len(ids):
            time.sleep(pause)
    return out


def daemon_running() -> bool:
    proc = run(["daemon", "status", "--json"], timeout=60)
    data = _parse_json(proc.stdout) or {}
    return bool(data.get("running"))


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
