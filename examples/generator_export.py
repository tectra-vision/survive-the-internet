"""Tectra integration example: an AI-video generator's export step.

What a generator adds to its pipeline:

    1. register at export: upload the rendered video, declare its origin, choose a profile
    2. deliver the marked file (with its signed C2PA manifest) to the end user
    3. verify a shared copy (any copy, after any platform) -> who registered it, what they declared

Also records the pilot metrics we ask every pilot to report: latency of each step, the quality
report for the delivered file, and detection outcomes on copies.

    pip install requests
    export TECTRA_API_KEY=tk_live_...
    python generator_export.py render.mp4 --model "MyVideoModel v3" --profile balanced
    python generator_export.py --verify shared_copy.mp4

Profiles: balanced (Standard, default: most robust) | fidelity (Maximum quality: least visible).
Provenance: ai_generated (default here) | ai_edited | camera_captured | unspecified. Tectra records
who declared it; it does not verify it.
"""
import argparse
import json
import os
import sys
import time

import requests

API = os.environ.get("TECTRA_API", "https://tectra.vision")
KEY = os.environ.get("TECTRA_API_KEY", "")
H = {"Authorization": f"Bearer {KEY}"}
LOG = os.environ.get("TECTRA_PILOT_LOG", "tectra_pilot_log.jsonl")


def log(event: dict):
    """Pilot log: one JSON line per event (share this file with Tectra at the end of the pilot)."""
    with open(LOG, "a") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **event}) + "\n")


def register(path: str, model: str, profile: str = "balanced", provenance: str = "ai_generated",
             out: str | None = None) -> dict:
    """Export hook: mark + register a rendered video. Returns the delivery info."""
    t0 = time.time()
    with open(path, "rb") as f:
        r = requests.post(f"{API}/api/v1/marks", headers=H, files={"file": f},
                          data={"tool": model, "profile": profile, "provenance": provenance}, timeout=600)
    if r.status_code != 200:
        log({"event": "register_failed", "file": path, "status": r.status_code, "detail": r.text[:300]})
        raise SystemExit(f"register failed: {r.status_code} {r.text[:300]}")
    job = r.json()
    while True:
        s = requests.get(f"{API}/api/v1/marks/{job['job_id']}", headers=H, timeout=30).json()
        if s["status"] in ("done", "error"):
            break
        time.sleep(3)
    if s["status"] == "error":
        # e.g. Maximum quality could not meet its quality floor: nothing delivered, no quota used
        log({"event": "register_refused", "file": path, "profile": profile, "detail": s.get("error"),
             "seconds": round(time.time() - t0, 1)})
        raise SystemExit(f"not delivered: {s.get('error')}")
    out = out or os.path.splitext(path)[0] + "_tectra.mp4"
    url = s["download_url"] if s["download_url"].startswith("http") else API + s["download_url"]
    with requests.get(url, headers=H, stream=True, timeout=600) as d, open(out, "wb") as f:
        for chunk in d.iter_content(1 << 20):
            f.write(chunk)
    v = s.get("video") or {}
    q = v.get("quality") or {}
    info = {"event": "registered", "file": path, "delivered": out, "mark_id": job["mark_id"], "profile": profile,
            "provenance": provenance, "seconds": round(time.time() - t0, 1),
            "vmaf_mean": q.get("vmaf_mean"), "vmaf_worst_second": q.get("vmaf_worst_window"),
            "robustness_self_test": v.get("robustness_pass", v.get("self_test_pass")), "c2pa": v.get("c2pa")}
    log(info)
    if info["robustness_self_test"] is False:
        print("note: Maximum quality kept this mark below its robustness target to protect quality; "
              "re-mark with --profile balanced if detection after re-sharing matters more.", file=sys.stderr)
    return info


def verify(path: str, expected_mark: str | None = None) -> dict:
    """Check any copy. A found mark = who registered it + what they declared. It does NOT mean unedited."""
    t0 = time.time()
    with open(path, "rb") as f:
        j = requests.post(f"{API}/api/v1/check", headers=H, files={"file": f}, timeout=600).json()
    res = {"event": "verified", "file": path, "seconds": round(time.time() - t0, 1), "found": j.get("found"),
           "mark_id": j.get("mark_id"), "registrant": j.get("workspace"), "declared": (j.get("provenance") or {}).get("declared"),
           "method": j.get("method"), "verdict": j.get("verdict"), "integrity": (j.get("integrity") or {}).get("status")}
    if expected_mark:
        res["expected_mark"] = expected_mark
        res["outcome"] = "correct" if j.get("mark_id") == expected_mark else ("miss" if not j.get("found") else "WRONG")
    log(res)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--model", default="AI video model")
    ap.add_argument("--profile", default="balanced", choices=["balanced", "fidelity"])
    ap.add_argument("--provenance", default="ai_generated", choices=["ai_generated", "ai_edited", "camera_captured", "unspecified"])
    ap.add_argument("--verify", metavar="COPY")
    ap.add_argument("--expect", metavar="MARK_ID", help="with --verify: the mark you registered (for pilot scoring)")
    a = ap.parse_args()
    if not KEY:
        sys.exit("set TECTRA_API_KEY")
    if a.verify:
        print(json.dumps(verify(a.verify, a.expect), indent=1))
    elif a.video:
        print(json.dumps(register(a.video, a.model, a.profile, a.provenance), indent=1))
    else:
        ap.print_help()
