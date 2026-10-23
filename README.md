# Tectra: Your video. Your signature.

**Watermark any video, verify the original, and trace every copy back to you.**

Since 2 August 2026, the EU AI Act (Article 50) requires AI-generated video to carry a machine-readable, robust mark. Most labels today are metadata, and metadata rarely survives a re-upload: when we uploaded a C2PA-signed AI video to YouTube, YouTube replaced the manifest and the "AI-generated" declaration was gone.

[Tectra](https://tectra.vision) puts a mark in the picture and registers who made the video, so copies that were re-encoded, reframed to 9:16 or forwarded through WhatsApp can still be traced back to their source. This repository holds the open benchmark harness, the current API example, the receipt verifier and the published profile evidence.

## Start here

- [Working Python example](examples/README.md): sign an export through the current hosted API, save the report, check a copy and retain its available receipt.
- [Receipt verifier](verification/README.md): authenticate a signed receipt and, for a log-v2 record, compare an exact original file.
- [Watch and download samples](https://tectra.vision/benchmarks), [get an API key](https://tectra.vision/developers), or [try the public checker](https://tectra.vision/check).

A watermark identifies a registration. It can remain on edited content. Exact-file verification uses the committed file fingerprint and a signed record; ordinary compression may break that exact match. No mark found does not classify a video as human-made. Reliable shared-copy tamper localization remains research.

## Current product results

The current profile evidence is a **post-fix re-evaluation of 28 source videos under 15 simulated transformations**. These are ffmpeg simulations, not live platform uploads. The same holdout was re-used after an export defect was fixed; this is not a fresh untouched test.

| Profile | Source videos delivered | Correctly identified copies | Mean VMAF | Single worst second |
|---|---:|---:|---:|---:|
| Standard | 28/28 | 420/420 | 80.5 | 67.2 |
| Maximum quality | 27/28 | 317/405 (78.3%) | 96.8 | 93.9 |

No wrong-owner credits among the 825 marked copies; no credits among 1,245 unmarked or unregistered-owner copies. These observations do not establish a one-in-a-million service error rate.

Standard prioritizes identification and can be visible. Maximum quality refused one video below its quality floor. Of its 27 delivered files, 12 failed the separate robustness self-test; customers see that result at marking time. It is weaker after screen recording and repeated sharing. VMAF estimates quality against an unmarked export; it is not a blinded viewing test.

The [full method and platform table](https://tectra.vision/benchmarks/methodology), [raw evidence archive](https://tectra.vision/evidence/tectra-profile-evidence-2026-10-23.zip), [machine-readable summary](results/profile-summary-2026-10-23.json) and [whitepaper](https://tectra.vision/tectra-whitepaper.pdf) disclose the scope and corrections.

## Reusable benchmark harness

The original open benchmark harness is retained here for testing other watermark implementations. Its 21-clip manifest, `evaluation` / `holdout-v1` sets and **10** versioned simulation pipelines are historical and do **not** reproduce the newer 28-source / 15-transformation product table above. That table is supported by the separately published raw profile evidence. Keep these datasets and protocols distinct.

```bash
pip install imageio-ffmpeg numpy opencv-python-headless
python fetch_clips.py
python run_benchmark.py adapters/your_adapter.py --set all
```

An adapter supplies two functions:

```python
def embed(src_path: str, dst_path: str) -> str: ...
def detect(path: str) -> str | None: ...
```

`adapters/videoseal_adapter.py` is a historical integration example. Check the model's code and weight licences before use. This repository does not publish a current superiority comparison against Video Seal.

Report exact-ID identification, false attributions, operating thresholds and image quality together. Simulated pipelines are versioned; [FIELD_PROTOCOL.md](FIELD_PROTOCOL.md) describes real uploads and returned-file checks.

## Historical results and corrections

[HISTORICAL_RESULTS.md](HISTORICAL_RESULTS.md) preserves the earlier v2.2/v2.3 tables, the five-clip Video Seal experiment and known holdout-v1 contamination/calibration issues. Those results are not the current profiles. Pre-fix v2.4/v2.5 detection and quality figures are withdrawn. The [current corrections register](https://tectra.vision/benchmarks/methodology#method-and-disclosures) explains the export defect and re-evaluation.

## Licences and support

Benchmark code, the API example and published verifier in this repository use the [MIT licence](LICENSE). Media licences are recorded in `clips.json` and must be checked at each source. Access to the hosted service requires a workspace/API key and is subject to its terms and quotas. Publishing these tools does not publish or license Tectra's hosted watermark engine.

The archived `sdk-ts` / `tectra-verify` repositories and the legacy `tectravision-sdk` package do not implement the current measured video pipeline. Start new integrations with the example above. Customer-hosted marking is restricted and requires a separate arrangement.
