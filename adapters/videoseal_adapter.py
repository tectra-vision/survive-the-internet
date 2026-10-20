"""Example adapter: Meta Video Seal v1.0 (MIT). Requires the videoseal repo installed.

Decision rule: a copy is identified if >= 82% of the 256 message bits match
(chance for a random video ~1e-27). Frames are processed in chunks of 16.
"""

import os

import imageio_ffmpeg
import numpy as np
import torch
import videoseal

_VS = videoseal.load("videoseal").eval()
_MSGS = {}
CHUNK, THRESH = 16, 0.82


def _frames(path, n=None):
    r = imageio_ffmpeg.read_frames(path, pix_fmt="rgb24")
    m = next(r)
    w, h = m["size"]
    out = [np.frombuffer(b, np.uint8).reshape(h, w, 3) for i, b in enumerate(r) if n is None or i < n]
    r.close()
    return out, m["fps"]


def embed(src, dst):
    frames, fps = _frames(src)
    msg = _VS.get_random_msg()
    out = []
    for i in range(0, len(frames), CHUNK):
        x = torch.from_numpy(np.stack(frames[i:i + CHUNK])).permute(0, 3, 1, 2).float() / 255
        with torch.no_grad():
            out.extend((_VS.embed(x, msgs=msg, is_video=True)["imgs_w"].clamp(0, 1) * 255).round().byte().permute(0, 2, 3, 1).numpy())
    h, w = out[0].shape[:2]
    wr = imageio_ffmpeg.write_frames(dst, (w, h), fps=fps, codec="libx264", pix_fmt_in="rgb24", macro_block_size=1,
                                     output_params=["-crf", "16", "-pix_fmt", "yuv420p"])
    wr.send(None)
    for f in out:
        wr.send(np.ascontiguousarray(f))
    wr.close()
    key = "".join(map(str, msg[0].tolist()))
    _MSGS[key] = msg[0].numpy()
    return key


def detect(path):
    frames, _ = _frames(path, 240)
    acc = None
    for i in range(0, len(frames), CHUNK):
        x = torch.from_numpy(np.stack(frames[i:i + CHUNK])).permute(0, 3, 1, 2).float() / 255
        with torch.no_grad():
            p = _VS.detect(x, is_video=True)["preds"][:, 1:].sum(0)
        acc = p if acc is None else acc + p
    bits = (acc > 0).numpy().astype(np.int64)
    best = max(_MSGS.items(), key=lambda kv: (bits == kv[1]).mean(), default=None)
    return best[0] if best and (bits == best[1]).mean() >= THRESH else None
