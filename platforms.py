"""Platform transcoding profiles, modelled on each platform's published upload
specs and commonly measured delivery settings. These are *emulations* — they
reproduce the geometry (scaling/letterboxing) and approximate bitrate/codec of
what each platform serves back, not their exact proprietary encoders.

Each profile is a list of ffmpeg "hops"; multi-hop profiles model re-sharing
(e.g. downloaded from TikTok, then forwarded on WhatsApp).
"""

H264 = ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"]

# 16:9 source placed in a 9:16 canvas with black bars (TikTok/Reels/Shorts default)
LETTERBOX_916 = "scale=1080:-2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"

PROFILES: dict[str, dict] = {
    "tiktok": {
        "label": "TikTok (16:9 upload, letterboxed into 9:16)",
        "hops": [["-vf", f"{LETTERBOX_916},scale=720:1280", *H264, "-b:v", "1500k", "-maxrate", "2000k", "-bufsize", "3000k"]],
    },
    "reels": {
        "label": "Instagram Reels (letterboxed 9:16, 1080p)",
        "hops": [["-vf", LETTERBOX_916, *H264, "-b:v", "3500k", "-maxrate", "4500k", "-bufsize", "7000k"]],
    },
    "shorts": {
        "label": "YouTube Shorts (letterboxed 9:16, VP9)",
        "hops": [["-vf", f"{LETTERBOX_916},scale=720:1280", "-c:v", "libvpx-vp9", "-b:v", "1200k",
                  "-deadline", "realtime", "-cpu-used", "8", "-pix_fmt", "yuv420p", "-f", "webm"]],
        "ext": ".webm",
    },
    "youtube": {
        "label": "YouTube (720p VP9)",
        "hops": [["-vf", "scale=-2:720", "-c:v", "libvpx-vp9", "-b:v", "1500k",
                  "-deadline", "realtime", "-cpu-used", "8", "-pix_fmt", "yuv420p", "-f", "webm"]],
        "ext": ".webm",
    },
    "x": {
        "label": "X / Twitter (720p, ~2 Mbps)",
        "hops": [["-vf", "scale=-2:720", *H264, "-b:v", "2000k", "-maxrate", "2500k", "-bufsize", "4000k"]],
    },
    "whatsapp": {
        "label": "WhatsApp (480p, ~700 kbps)",
        "hops": [["-vf", "scale=-2:480", *H264, "-profile:v", "baseline", "-b:v", "700k", "-maxrate", "900k", "-bufsize", "1400k"]],
    },
    "telegram": {
        "label": "Telegram (compressed, 640px)",
        "hops": [["-vf", "scale=-2:360", *H264, "-crf", "30"]],
    },
    "screenrec": {
        "label": "Phone screen-recording of the video (UI bars, gamma shift)",
        "hops": [["-vf", "scale=1080:-2,pad=1080:1920:0:(oh-ih)/2-120:0x101010,"
                         "drawbox=x=0:y=1700:w=1080:h=220:color=0x202020:t=fill,eq=gamma=1.08:saturation=0.95,"
                         "scale=720:1280", *H264, "-crf", "26"]],
    },
    "tiktok_then_whatsapp": {
        "label": "Downloaded from TikTok, forwarded on WhatsApp",
        "hops": [["-vf", f"{LETTERBOX_916},scale=720:1280", *H264, "-b:v", "1500k", "-maxrate", "2000k", "-bufsize", "3000k"],
                 ["-vf", "scale=-2:640", *H264, "-profile:v", "baseline", "-b:v", "600k", "-maxrate", "800k", "-bufsize", "1200k"]],
    },
    "x_then_reels_then_whatsapp": {
        "label": "X → re-posted as a Reel → WhatsApp",
        "hops": [["-vf", "scale=-2:720", *H264, "-b:v", "2000k", "-maxrate", "2500k", "-bufsize", "4000k"],
                 ["-vf", LETTERBOX_916, *H264, "-b:v", "3500k", "-maxrate", "4500k", "-bufsize", "7000k"],
                 ["-vf", "scale=-2:640", *H264, "-profile:v", "baseline", "-b:v", "600k", "-maxrate", "800k", "-bufsize", "1200k"]],
    },
}
