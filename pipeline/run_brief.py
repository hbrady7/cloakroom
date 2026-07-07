"""Run the Claude briefing layer end to end.

  build input -> claude -p (subscription OAuth, no API key) -> strip fences
  -> schema + grounding validation -> on failure retry ONCE with the
  validator errors appended -> on total failure write {"status":
  "engine_only"} so the site renders raw engine candidates instead of
  breaking.

Model policy: try CLOAKROOM_BRIEF_MODEL (default "opus"), then fall back to
the next strongest available on the plan.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from build_brief_input import build_payload
from validate_brief import validate

from lib.common import DATA, load_json, save_json, set_status, utcnow_iso

PIPELINE = Path(__file__).resolve().parent
INPUT = PIPELINE / "brief_input.txt"
MODELS = [os.environ.get("CLOAKROOM_BRIEF_MODEL", "opus"), "sonnet"]
TIMEOUT_S = int(os.environ.get("CLOAKROOM_BRIEF_TIMEOUT", "900"))


def strip_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    # tolerate stray prose around the object
    start, end = t.find("{"), t.rfind("}")
    return t[start:end + 1] if start != -1 and end > start else t


def call_claude(prompt: str, model: str) -> str | None:
    """One claude -p invocation; returns the model's text or None."""
    workdir = PIPELINE / ".cache" / "briefwork"  # neutral cwd: no CLAUDE.md pickup
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = ["claude", "-p", "--model", model, "--output-format", "json"]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=TIMEOUT_S, cwd=workdir)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[brief] claude ({model}) failed to run: {e}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"[brief] claude ({model}) exit {proc.returncode}: "
              f"{(proc.stderr or proc.stdout)[:400]}", file=sys.stderr)
        return None
    try:
        wrapper = json.loads(proc.stdout)
        if wrapper.get("is_error"):
            print(f"[brief] claude ({model}) is_error: "
                  f"{str(wrapper.get('result'))[:400]}", file=sys.stderr)
            return None
        return wrapper.get("result") or None
    except json.JSONDecodeError:
        return proc.stdout or None


def attempt(prompt: str, model: str) -> tuple[dict | None, list[str]]:
    raw = call_claude(prompt, model)
    if raw is None:
        return None, ["cli: no output"]
    try:
        brief = json.loads(strip_fences(raw))
    except json.JSONDecodeError as e:
        return None, [f"json: {e}"]
    return brief, validate(brief)


def main() -> None:
    payload = build_payload()
    if not payload["engine"]["candidates"]:
        raise RuntimeError("no candidates - run score.py first")
    prompt = ((PIPELINE / "brief_prompt.md").read_text() + "\n=== INPUT ===\n" +
              json.dumps(payload, indent=1, ensure_ascii=False))
    INPUT.write_text(prompt)
    print(f"[brief] input ready ({INPUT.stat().st_size // 1024} KB)")

    brief = errors = None
    used_model = None
    for model in dict.fromkeys(MODELS):  # dedupe, keep order
        brief, errors = attempt(prompt, model)
        if brief is None and errors == ["cli: no output"]:
            continue  # model unavailable on this plan -> next model
        if not errors:
            used_model = model
            break
        print(f"[brief] validation failed ({len(errors)}), retrying once", file=sys.stderr)
        retry_prompt = (prompt +
                        "\n\n=== VALIDATOR ERRORS FROM YOUR PREVIOUS ATTEMPT ===\n" +
                        "\n".join(errors[:40]) +
                        "\nReturn the corrected JSON object only.")
        brief, errors = attempt(retry_prompt, model)
        if not errors and brief is not None:
            used_model = model
            break

    if used_model is None or brief is None:
        for e in (errors or [])[:20]:
            print(f"[brief]   {e}", file=sys.stderr)
        save_json(DATA / "brief-latest.json",
                  {"status": "engine_only", "generated_at": utcnow_iso(),
                   "as_of": payload["as_of"]})
        set_status("brief", False, "engine_only fallback", count=0)
        print("[brief] FAILED -> engine_only fallback written")
        return

    out = {"status": "ok", "model": used_model, "generated_at": utcnow_iso(), **brief}
    save_json(DATA / "brief-latest.json", out)
    archive = DATA / "archive" / f"brief-{brief['date']}.json"
    save_json(archive, out)
    set_status("brief", True, f"model={used_model}", count=len(brief["picks"]))
    print(f"[brief] ok: {len(brief['picks'])} picks, "
          f"{len(brief['caution_list'])} caution, {len(brief['skipped'])} skipped "
          f"(model={used_model}) -> {archive.name}")


if __name__ == "__main__":
    from lib.common import run_fail_soft
    run_fail_soft("brief", main)
