#!/usr/bin/env python3
"""Survive-the-Internet benchmark for video watermarks (v1).

    pip install imageio-ffmpeg numpy opencv-python-headless
    python fetch_clips.py                       # downloads public-domain AI clips (Wikimedia Commons)
    python run_benchmark.py adapters/my_system.py [--set evaluation|holdout-v1|all]

An adapter is a Python file defining two functions:

    def embed(src_path: str, dst_path: str) -> str      # mark src, write dst, return the embedded ID
    def detect(path: str) -> str | None                 # return the ID found in path, or None

Scoring (per clip x pipeline): a copy is IDENTIFIED if detect() returns exactly the
embedded ID. Each clip's unmarked original is also processed by every pipeline and
must return None (negative control). Visual quality (PSNR/SSIM of marked vs original)
is reported alongside, so robustness can't be bought silently with visibility.
Report the false-positive budget your detect() is calibrated to.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import tempfile

import cv2
import imageio_ffmpeg
import numpy as np

from platforms import PROFILES

HERE = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
SECONDS = 8


def run(args):
    subprocess.run([FF, "-y", "-loglevel", "error", *args], check=True)


def apply(src, key, d):
    cur = src
    prof = PROFILES[key]
    for i, hop in enumerate(prof["hops"]):
        ext = prof.get("ext", ".mp4") if i == len(prof["hops"]) - 1 else ".mp4"
        out = os.path.join(d, f"{os.path.basename(src)}.{key}.{i}{ext}")
        run(["-i", cur, "-t", str(SECONDS), *hop, "-an", out])
        cur = out
    return cur


def gray_frames(p, n=40):
    r = imageio_ffmpeg.read_frames(p, pix_fmt="gray", bits_per_pixel=8)
    m = next(r)
    w, h = m["size"]
    out = [np.frombuffer(b, np.uint8).reshape(h, w).astype(np.float32) for _, b in zip(range(n), r)]
    r.close()
    return out


def quality(a, b):
    A, B = gray_frames(a), gray_frames(b)
    g = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)  # noqa: E731
    ps, ss = [], []
    for x, y in zip(A, B):
        ps.append(10 * np.log10(255 ** 2 / max(np.mean((x - y) ** 2), 1e-9)))
        mx, my = g(x), g(y)
        sx, sy, sxy = g(x * x) - mx ** 2, g(y * y) - my ** 2, g(x * y) - mx * my
        ss.append(float((((2 * mx * my + 6.5025) * (2 * sxy + 58.5225)) / ((mx ** 2 + my ** 2 + 6.5025) * (sx + sy + 58.5225))).mean()))
    return float(np.mean(ps)), float(np.mean(ss))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("adapter")
    ap.add_argument("--set", default="all")
    ap.add_argument("--out", default="results.json")
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("adapter", a.adapter)
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    clips = [c for c in json.load(open(os.path.join(HERE, "clips.json"))) if a.set == "all" or c["set"] == a.set]
    res = {"adapter": os.path.basename(a.adapter), "pipelines": list(PROFILES), "clips": []}
    for c in clips:
        src_full = os.path.join(HERE, "clips", c["file"])
        if not os.path.exists(src_full):
            print("missing", c["file"], "- run fetch_clips.py")
            continue
        with tempfile.TemporaryDirectory() as d:
            ref = os.path.join(d, "ref.mp4")
            run(["-i", src_full, "-t", str(SECONDS), "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-crf", "14",
                 "-pix_fmt", "yuv420p", "-an", ref])
            marked = os.path.join(d, "marked.mp4")
            mid = A.embed(ref, marked)
            row = {"clip": c["file"], "set": c["set"], "quality": quality(ref, marked), "identified": {}, "false_positive": {}}
            for k in PROFILES:
                row["identified"][k] = A.detect(apply(marked, k, d)) == mid
                row["false_positive"][k] = A.detect(apply(ref, k, d)) is not None
            res["clips"].append(row)
            print(f"{c['file'][:28]:28s} identified {sum(row['identified'].values())}/{len(PROFILES)}  "
                  f"false+ {sum(row['false_positive'].values())}  PSNR {row['quality'][0]:.1f}", flush=True)
    n = len(res["clips"])
    print("\n" + f"{'pipeline':54s} identified   false positives")
    for k in PROFILES:
        print(f"  {PROFILES[k]['label'][:52]:52s} {sum(r['identified'][k] for r in res['clips']):>3d}/{n}      "
              f"{sum(r['false_positive'][k] for r in res['clips'])}/{n}")
    tot = sum(sum(r["identified"].values()) for r in res["clips"])
    print(f"  TOTAL identified {tot}/{n * len(PROFILES)} · mean PSNR {np.mean([r['quality'][0] for r in res['clips']]):.1f} dB")
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
