#!/usr/bin/env python3
"""Download the benchmark's public-domain AI clips from Wikimedia Commons and verify hashes."""

import hashlib
import json
import os
import subprocess
import urllib.request

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FF = imageio_ffmpeg.get_ffmpeg_exe()
os.makedirs(os.path.join(HERE, "clips"), exist_ok=True)
for c in json.load(open(os.path.join(HERE, "clips.json"))):
    out = os.path.join(HERE, "clips", c["file"])
    if os.path.exists(out) or not c.get("source_url"):
        continue
    raw = out + ".src"
    req = urllib.request.Request(c["source_url"], headers={"User-Agent": "SurviveTheInternetBenchmark/1.0"})
    open(raw, "wb").write(urllib.request.urlopen(req, timeout=180).read())
    if c.get("source_sha256"):
        got = hashlib.sha256(open(raw, "rb").read()).hexdigest()
        assert got == c["source_sha256"], f"hash mismatch for {c['file']}: {got}"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", raw, "-t", "10", "-vf", "scale='min(1920,iw)':-2",
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", out], check=True)
    os.unlink(raw)
    print("ok", c["file"], c["license"])
