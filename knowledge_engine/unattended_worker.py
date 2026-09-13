from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

Status = Literal[
    "PASS",
    "FAIL",
    "REVIEW_REQUIRED",
    "PRODUCT_REALITY_REQUIRED",
    "ENVIRONMENT_FAILURE",
    "BUSY",
]
Probe = Literal["preflight", "ollama_health"]

REPOSITORY = "jweter/knowledge-engine-core"
EXPECTED_ORIGIN = "https://github.com/jweter/knowledge-engine-core.git"
SCHEMA_VERSION = 1
LOCK_NAME = "worker.lock"
DEFAULT_TIMEOUT_SECONDS = 3600
MAX_TIMEOUT_SECONDS = 7200
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_state_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "KnowledgeEngine" / "unattended-worker"
    return Path.home() / ".knowledge-engine" / "unattended-worker"


def normalize_origin(value: str) -> str:
    text = value.strip().replace("\\", "/")
    if text.endswith("/"):
        text = text[:-1]
    if text.startswith("git@github.com:"):
        text = "https://github.com/" + text.removeprefix("git@github.com:")
    return text.lower().removesuffix(".git")


def origin_is_expected(value: str) -> bool:
    return normalize_origin(value) == normalize_origin(EXPECTED_ORIGIN)


@dataclass(frozen=True)
class VerificationRequest:
    request_id: str
    repository: str
    branch: str
    commit_sha: str
    probe: Probe
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "VerificationRequest":
        allowed = {
            "schema_version",
            "request_id",
            "repository",
            "branch",
            "commit_sha",
            "probe",
            "timeout_seconds",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"Unknown request fields: {', '.join(sorted(unknown))}")
        if payload.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError("Unsupported request schema_version")
        request_id = str(payload.get("request_id") or "")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", request_id):
            raise ValueError("request_id must be 1-120 safe identifier characters")
        repository = str(payload.get("repository") or "")
        if repository != REPOSITORY:
            raise ValueError(f"repository must be {REPOSITORY}")
        branch = str(payload.get("branch") or "")
        if not branch or len(branch) > 200 or any(ch.isspace() for ch in branch):
            raise ValueError("branch must be a non-empty ref name without whitespace")
        commit_sha = str(payload.get("commit_sha") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise ValueError("commit_sha must be an exact 40-character Git SHA")
        probe_raw = str(payload.get("probe") or "")
        if probe_raw not in {"preflight", "ollama_health"}:
            raise ValueError("probe is not authorized")
        timeout_raw = payload.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        if isinstance(timeout_raw, bool):
            raise ValueError("timeout_seconds must be an integer")
        timeout_seconds = int(timeout_raw)
        if timeout_seconds < 1 or timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise ValueError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
        return cls(
            request_id=request_id,
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            probe=cast(Probe, probe_raw),
            timeout_seconds=timeout_seconds,
        )


@dataclass
class VerificationResult:
    request_id: str
    repository: str
    branch: str
    commit_sha: str
    probe: Probe
    status: Status
    started_at: str
    finished_at: str
    duration_seconds: float
    environment: dict[str, str]
    verification: dict[str, Any]
    reason: str = ""
    schema_version: int = SCHEMA_VERSION

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def load_request(path: Path) -> VerificationRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request document must be a JSON object")
    return VerificationRequest.from_mapping(payload)


def run_capture(
    args: list[str], *, cwd: Path | None = None, timeout_seconds: float = 30.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def git_output(repo_root: Path, *args: str) -> str:
    proc = run_capture(["git", "-C", str(repo_root), *args], timeout_seconds=60.0)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "git command failed").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail[:500]}")
    return proc.stdout.strip()


def validate_checkout(repo_root: Path, request: VerificationRequest) -> None:
    if not (repo_root / ".git").exists():
        raise RuntimeError(f"Not a Git checkout: {repo_root}")
    origin = git_output(repo_root, "remote", "get-url", "origin")
    if not origin_is_expected(origin):
        raise RuntimeError(f"Unexpected origin remote: {origin}")
    head = git_output(repo_root, "rev-parse", "HEAD").lower()
    if head != request.commit_sha:
        raise RuntimeError(
            f"Checkout identity mismatch: expected {request.commit_sha}, got {head}"
        )


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        proc = run_capture(
            ["tasklist.exe", "/FI", f"PID eq {pid}", "/NH"], timeout_seconds=10.0
        )
        return proc.returncode == 0 and re.search(rf"\b{pid}\b", proc.stdout) is not None
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_lock(state_dir: Path) -> tuple[int | None, bool]:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / LOCK_NAME
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            return fd, True
        except FileExistsError:
            try:
                pid = int(path.read_text(encoding="ascii").strip())
            except (OSError, ValueError):
                if attempt == 0:
                    time.sleep(0.05)
                    continue
                pid = -1
            if pid_is_alive(pid):
                return None, False
            path.unlink(missing_ok=True)
    return None, False


def release_lock(state_dir: Path, fd: int) -> None:
    try:
        os.close(fd)
    finally:
        (state_dir / LOCK_NAME).unlink(missing_ok=True)


def sanitize_text(text: str, *, repo_root: Path) -> str:
    result = text
    replacements = [
        (str(repo_root), "<REPO_ROOT>"),
        (str(Path.home()), "%USERPROFILE%"),
    ]
    for raw, replacement in replacements:
        if raw:
            result = result.replace(raw, replacement)
            result = result.replace(raw.replace("\\", "/"), replacement)
    result = re.sub(
        r"(?i)\b(authorization|api[_-]?key|token|password)\b\s*[:=]\s*\S+",
        r"\1=<REDACTED>",
        result,
    )
    return result


def write_result(path: Path, result: VerificationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result.to_mapping(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run_logged(
    args: list[str],
    *,
    cwd: Path,
    log_path: Path,
    timeout_seconds: float,
) -> tuple[int, float, bool]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    timed_out = False
    with log_path.open("w", encoding="utf-8", errors="replace") as handle:
        try:
            proc = subprocess.run(
                args,
                cwd=str(cwd),
                check=False,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
            )
            code = int(proc.returncode)
        except subprocess.TimeoutExpired:
            handle.write(f"\nTIMEOUT after {timeout_seconds:.0f} seconds\n")
            code = 124
            timed_out = True
    return code, time.monotonic() - started, timed_out


def log_tail(path: Path, *, repo_root: Path, lines: int = 40) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return sanitize_text("\n".join(content[-lines:]), repo_root=repo_root)


def run_preflight(
    repo_root: Path, state_dir: Path, timeout_seconds: int
) -> tuple[Status, dict[str, Any], str]:
    script = repo_root / "engineering" / "preflight.py"
    if not script.is_file():
        return "REVIEW_REQUIRED", {}, "engineering/preflight.py is missing"
    log_path = state_dir / "logs" / "preflight.log"
    evidence_path = state_dir / "preflight-evidence.json"
    command = [
        sys.executable,
        str(script),
        "--evidence",
        str(evidence_path),
    ]
    code, duration, timed_out = run_logged(
        command,
        cwd=repo_root,
        log_path=log_path,
        timeout_seconds=float(timeout_seconds),
    )
    verification = {
        "command": [
            "python",
            "engineering/preflight.py",
            "--evidence",
            "<STATE_DIR>/preflight-evidence.json",
        ],
        "exit_code": code,
        "duration_seconds": round(duration, 3),
        "timed_out": timed_out,
        "failure_tail": "" if code == 0 else log_tail(log_path, repo_root=repo_root),
    }
    if timed_out:
        return "ENVIRONMENT_FAILURE", verification, "canonical preflight timed out"
    if code != 0:
        return "FAIL", verification, "canonical preflight failed"
    return "PASS", verification, ""


def run_ollama_health(timeout_seconds: int) -> tuple[Status, dict[str, Any], str]:
    timeout = min(float(timeout_seconds), 20.0)
    request = urllib.request.Request(
        OLLAMA_TAGS_URL,
        headers={"User-Agent": "KnowledgeEngine-Unattended-Verification/1"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            code = int(response.status)
    except (
        OSError,
        urllib.error.URLError,
        TimeoutError,
        socket.timeout,
        json.JSONDecodeError,
    ) as exc:
        return (
            "ENVIRONMENT_FAILURE",
            {"duration_seconds": round(time.monotonic() - started, 3)},
            f"Ollama health probe unavailable: {type(exc).__name__}",
        )
    if code != 200 or not isinstance(payload, dict):
        return (
            "ENVIRONMENT_FAILURE",
            {
                "http_status": code,
                "duration_seconds": round(time.monotonic() - started, 3),
            },
            "Ollama health probe returned an unexpected response",
        )
    models = payload.get("models")
    model_count = len(models) if isinstance(models, list) else 0
    return (
        "PASS",
        {
            "http_status": code,
            "duration_seconds": round(time.monotonic() - started, 3),
            "model_count": model_count,
            "endpoint": OLLAMA_TAGS_URL,
        },
        "",
    )


def execute_request(
    request: VerificationRequest,
    *,
    repo_root: Path,
    state_dir: Path,
) -> VerificationResult:
    started_at = utc_now()
    started = time.monotonic()
    environment = {
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }
    try:
        validate_checkout(repo_root, request)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return VerificationResult(
            request_id=request.request_id,
            repository=request.repository,
            branch=request.branch,
            commit_sha=request.commit_sha,
            probe=request.probe,
            status="ENVIRONMENT_FAILURE",
            started_at=started_at,
            finished_at=utc_now(),
            duration_seconds=round(time.monotonic() - started, 3),
            environment=environment,
            verification={},
            reason=sanitize_text(str(exc), repo_root=repo_root),
        )

    if request.probe == "preflight":
        status, verification, reason = run_preflight(
            repo_root, state_dir, request.timeout_seconds
        )
    elif request.probe == "ollama_health":
        status, verification, reason = run_ollama_health(request.timeout_seconds)
    else:
        status, verification, reason = "REVIEW_REQUIRED", {}, "probe is not authorized"

    return VerificationResult(
        request_id=request.request_id,
        repository=request.repository,
        branch=request.branch,
        commit_sha=request.commit_sha,
        probe=request.probe,
        status=status,
        started_at=started_at,
        finished_at=utc_now(),
        duration_seconds=round(time.monotonic() - started, 3),
        environment=environment,
        verification=verification,
        reason=reason,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one bounded unattended Knowledge Engine verification request."
    )
    parser.add_argument(
        "--request", type=Path, required=True, help="Path to the request JSON document."
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="Knowledge Engine Core checkout."
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=default_state_dir(),
        help="Private local worker state directory.",
    )
    parser.add_argument(
        "--result", type=Path, default=None, help="Optional explicit result JSON path."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state_dir = args.state_dir.expanduser().resolve()
    result_path = args.result or state_dir / "latest-result.json"
    try:
        request = load_request(args.request)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"REVIEW_REQUIRED: invalid request: {exc}", file=sys.stderr)
        return 2

    lock_fd, acquired = acquire_lock(state_dir)
    if not acquired or lock_fd is None:
        busy = VerificationResult(
            request_id=request.request_id,
            repository=request.repository,
            branch=request.branch,
            commit_sha=request.commit_sha,
            probe=request.probe,
            status="BUSY",
            started_at=utc_now(),
            finished_at=utc_now(),
            duration_seconds=0.0,
            environment={"python": sys.version.split()[0], "platform": sys.platform},
            verification={},
            reason="another unattended verification run owns the worker lock",
        )
        write_result(result_path, busy)
        return 3

    try:
        result = execute_request(
            request,
            repo_root=args.repo_root.expanduser().resolve(),
            state_dir=state_dir,
        )
        write_result(result_path, result)
    finally:
        release_lock(state_dir, lock_fd)

    print(json.dumps(result.to_mapping(), sort_keys=True))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
