# Survive the Internet: a benchmark for video watermarks

Most watermark benchmarks apply synthetic distortions (JPEG quality, Gaussian noise, rotation). AI video doesn't get attacked that way. It gets **posted**: letterboxed into 9:16 by TikTok and Reels, re-encoded to VP9 by YouTube, crushed by WhatsApp, screen-recorded, and re-shared across platforms.

This benchmark measures exactly that, on **real AI-generated video**.

## What's in it

| | |
|---|---|
| **Clips** | 21 public-domain AI videos from Wikimedia Commons (OpenAI Sora and Sora 2, Google Veo 2/3/3.1, CogVideoX and others), including vertical and square formats. `clips.json` lists sources, licences and SHA-256 hashes. |
| **Sets** | `evaluation` (8 clips) and `holdout-v1` (13 clips, sealed and Bitcoin-timestamped *before* first use; see `SEAL.json` and `SEAL.json.ots`). |
| **Pipelines** | 10 named, versioned ffmpeg reproductions of platform processing (`platforms.py`): TikTok, Reels, Shorts, YouTube, X, WhatsApp, Telegram, phone screen-recording, and two multi-hop re-share chains. |
| **Metric** | **Identification rate**: the exact embedded ID is returned. Not bit accuracy. |
| **Controls** | Every unmarked original is pushed through every pipeline and must return nothing (false positives reported). |
| **Quality** | PSNR and SSIM of marked vs. original, reported next to robustness. |

## Run it on your watermark

```bash
pip install imageio-ffmpeg numpy opencv-python-headless
python fetch_clips.py
python run_benchmark.py adapters/your_adapter.py --set all
```

An adapter is two functions; `adapters/videoseal_adapter.py` is a worked example for Meta's open-source Video Seal:

```python
def embed(src_path: str, dst_path: str) -> str: ...      # returns the embedded ID
def detect(path: str) -> str | None: ...                 # returns the ID found, or None
```

Please report the false-attribution budget your `detect()` is calibrated to, plus PSNR and SSIM.

## Published results

| System | Identified (evaluation + platform sets) | False positives | PSNR |
|---|---|---|---|
| Tectra v2.3 (sealed holdout-v1)* | 128/130 (98.5%) | 0 | 39.0 dB (VMAF 82.2, range 61–93) |
| Tectra v2.2 (sealed holdout-v1) | 124/130 (95.4%) | 0 | 37.0 dB (VMAF 75.2) |
| Meta Video Seal v1.0 (default strength) | 36/50 on 5 clips × 10 pipelines | 0 | 42.2 dB |

## Known issues in holdout-v1

*v2.3: the first run scored 118/130 because one clip failed from a calibration bug; the bug was diagnosed on that clip and fixed before the 128/130 re-run, so that figure is not a fully clean held-out result. The next release will use a newly sealed holdout-v2.


one sealed-test clip (“Borneo wildlife”) turned out to be a duplicate upload of a development clip (“Birds over river”) on Wikimedia Commons; our fingerprint index found it. Excluding it, the sealed result is 118/120 (98.3%) for v2.3 and 114/120 (95.0%) for v2.2. Holdout v2 will exclude near-duplicates automatically.

## Limits

- Pipelines **reproduce** platform processing from published specs; they are not live uploads. A field protocol (post → download → check) is in `FIELD_PROTOCOL.md`.
- Platforms change their encoders; pipelines are versioned (`v1`), and new versions are added rather than edited.

Licence: benchmark code MIT; clips are public domain (see each source page). Maintained by Tectra (tectra.vision).
