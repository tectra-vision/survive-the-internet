# Real-platform field test (≈15 minutes)

Goal: prove that a Tectra-marked video is still attributed to you after a real
platform has processed it. The automated benchmark (`research/wmbench/platform_bench.py`)
*emulates* platforms; this is the real thing.

## 1. Make marked clips

Use 2–3 short (10–20 s) AI-generated clips — ideally one calm shot, one busy
(foliage / water / crowds) and one with fast motion.

```bash
pip install requests
export TECTRA_API_KEY=tk_live_...        # https://tectra.vision/app → API
python fieldtest.py make clip1.mp4 clip2.mp4 clip3.mp4
# -> fieldtest_out/clip1_tectra.mp4 ...
```

## 2. Post, then download each platform's copy

| Platform | Post as | Get the copy back |
|---|---|---|
| TikTok | public or private video | "Save video" in the app, or screen-record it playing |
| Instagram | Reel | screen-record it playing (Instagram has no download) |
| YouTube Shorts | unlisted Short | `yt-dlp <url>` |
| X / Twitter | post with video | `yt-dlp <url>` |
| WhatsApp | send to yourself / a friend | "Save" on the receiving phone |
| Telegram | send as video (not file) | save on receiving device |

Also try at least one **re-share chain**: download from TikTok → send via WhatsApp → save.

Name each downloaded file `<platform>__<anything>.mp4`, e.g. `tiktok__clip1.mp4`,
`reels_screenrec__clip2.mp4`, `tiktok_whatsapp__clip1.mp4`, and put them in one folder.
Add one never-marked video as `control__x.mp4` — it must come back ❌.

## 3. Score

```bash
python fieldtest.py score ./downloads
```

Prints ✅/❌ per file and per platform and writes `fieldtest_report.csv`.
Send the CSV back and we'll publish the results on the site.
