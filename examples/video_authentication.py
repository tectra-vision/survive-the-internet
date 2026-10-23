#!/usr/bin/env python3
"""Hosted video API example. Keep TECTRA_API_KEY in your server environment.

    pip install requests
    python video_authentication.py mark render.mp4 --out signed.mp4 --source ai_generated
    python video_authentication.py check signed.mp4 --out check.json

Signing, source identification and exact-file authentication are separate outcomes.
For exact-file verification, use verify_receipt.py with --original and a log-v2 receipt.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse

import requests

PROFILES = {"standard": "balanced", "maximum-quality": "fidelity"}
SOURCES = ("ai_generated", "ai_edited", "camera_captured", "unspecified")


class TectraAPI:
    def __init__(self, api_key: str, base_url: str = "https://tectra.vision", session=None):
        url = urlparse(base_url)
        if url.scheme != "https" and not (url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")):
            raise ValueError("Use HTTPS, or HTTP on localhost for development.")
        if not url.netloc or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise ValueError("Base URL must be an origin such as https://tectra.vision.")
        if not api_key:
            raise ValueError("Set TECTRA_API_KEY in your environment.")
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.session = session or requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"

    def _request(self, method: str, path: str, **kwargs):
        # Do not resend a marking POST automatically or follow redirects with credentials.
        response = self.session.request(method, self.base_url + path, timeout=(10, 120),
                                        allow_redirects=False, **kwargs)
        if 300 <= response.status_code < 400:
            response.close()
            raise RuntimeError("Unexpected API redirect; check the configured origin.")
        response.raise_for_status()
        return response

    @staticmethod
    def _fresh_outputs(*paths: Path):
        for path in paths:
            if path.exists():
                raise FileExistsError(f"Output already exists: {path}")
            if not path.parent.is_dir():
                raise ValueError(f"Output directory does not exist: {path.parent}")

    @staticmethod
    def _save_json(path: Path, data):
        with path.open("x") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def mark(self, source: Path, output: Path, *, provenance="unspecified", profile="standard",
             label="", tool="", wait_seconds=1800, poll_seconds=2) -> dict:
        report_path = output.with_suffix(output.suffix + ".job.json")
        self._fresh_outputs(output, report_path)
        if profile not in PROFILES or provenance not in SOURCES:
            raise ValueError("Unknown profile or source declaration.")
        if source.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("Hosted marking accepts files up to 100 MB.")
        with source.open("rb") as f:
            with self._request("POST", "/marks", files={"file": (source.name, f)},
                               data={"profile": PROFILES[profile], "provenance": provenance,
                                     "label": label, "tool": tool}) as response:
                started = response.json()
        job_id = started["job_id"]
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise RuntimeError("Unexpected job ID in response.")
        deadline = time.monotonic() + wait_seconds
        while True:
            with self._request("GET", f"/marks/{job_id}") as response:
                job = response.json()
            status = job.get("status")
            if status in ("done", "error"):
                self._save_json(report_path, job)
                if status == "error":
                    raise RuntimeError(f"Marking did not deliver a file. See {report_path}.")
                break
            if status not in ("queued", "marking", "testing"):
                raise RuntimeError(f"Unexpected job status: {status!r}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Job {job_id} is still processing. Poll this job; do not resubmit it.")
            time.sleep(poll_seconds)
        video = job.get("video") or {}
        if profile == "maximum-quality" and video.get("quality_pass") is not True:
            raise RuntimeError(f"Maximum quality was not confirmed. Download withheld; see {report_path}.")
        # Build the download path from the validated job ID, not an arbitrary response URL.
        created = False
        try:
            with self._request("GET", f"/marks/{job_id}/download", stream=True) as response:
                with output.open("xb") as f:
                    created = True
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
        except BaseException:
            if created:
                output.unlink(missing_ok=True)
            raise
        return job

    def check(self, source: Path, output: Path) -> dict:
        receipt_path = output.with_suffix(".receipt.json")
        if receipt_path == output:
            raise ValueError("Use a result filename such as check.json, not *.receipt.json.")
        self._fresh_outputs(output, receipt_path)
        with source.open("rb") as f:
            with self._request("POST", "/check", files={"file": (source.name, f)}) as response:
                result = response.json()
        self._save_json(output, result)
        if result.get("receipt"):
            self._save_json(receipt_path, result["receipt"])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://tectra.vision")
    sub = parser.add_subparsers(dest="command", required=True)
    mark = sub.add_parser("mark", help="Sign/register through the current hosted video pipeline")
    mark.add_argument("file", type=Path)
    mark.add_argument("--out", required=True, type=Path)
    mark.add_argument("--source", choices=SOURCES, default="unspecified")
    mark.add_argument("--profile", choices=PROFILES, default="standard")
    mark.add_argument("--label", default="")
    mark.add_argument("--tool", default="")
    mark.add_argument("--wait-seconds", type=float, default=1800)
    check = sub.add_parser("check", help="Identify a registration and save available signed evidence")
    check.add_argument("file", type=Path)
    check.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        api = TectraAPI(os.environ.get("TECTRA_API_KEY", ""), args.base_url)
        if args.command == "mark":
            result = api.mark(args.file, args.out, provenance=args.source, profile=args.profile,
                              label=args.label, tool=args.tool, wait_seconds=args.wait_seconds)
            print(f"Delivered: {args.out}\nJob report: {args.out}.job.json")
            video = result.get("video") or {}
            if video.get("robustness_pass") is False:
                print("NOTICE: This file failed its robustness self-test; its mark may not survive sharing.")
            if video.get("c2pa") is not True:
                print("NOTICE: Embedded Content Credentials were not confirmed; inspect the job report.")
            print("Retain the file and report. Check the file to obtain available signed evidence.")
        else:
            result = api.check(args.file, args.out)
            if result.get("found"):
                print(f"Registered source: {result.get('workspace') or result.get('label') or 'not disclosed'}")
            else:
                print("No registered mark found. This does not classify the video as human-made.")
            print("Shared-copy tampering is not assessed.")
            receipt = result.get("receipt")
            if receipt:
                print(f"Receipt saved: {args.out.with_suffix('.receipt.json')}")
                proof = (receipt.get("statement") or {}).get("proof")
                if not proof:
                    print("NOTICE: Registration proof is pending. Obtain a fresh receipt after the log is updated.")
                elif proof.get("log_version", 1) != 2:
                    print("NOTICE: This receipt does not supply the current exact-file binding.")
                elif not proof.get("batch"):
                    print("NOTICE: Batch inclusion is pending; the full receipt proof cannot pass yet.")
                print("Authenticate the receipt separately with verify_receipt.py and an expected signing key.")
            else:
                print("NOTICE: No signed receipt returned; there is no receipt to authenticate.")
        return 0
    except (ValueError, KeyError, OSError, RuntimeError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
