#!/usr/bin/env python3
"""Verify a Tectra check receipt against an externally supplied or published key.

    pip install pynacl            # (optional: pip install opentimestamps-client  for the Bitcoin check)
    python verify_receipt.py receipt.json [--video copy.mp4] [--key <published hex public key>]

Checks, independently:
  1. Signature    the statement was signed by Tectra's published receipt key.
  2. File         (optional) the receipt is about THIS file (SHA-256 match).
  3. Opening      the mark's commitment = SHA256(salt || owner || label || tool)  (who it was issued to).
  4. Leaf         leaf = SHA256(00 || "tectra-log-v1" || mark_id || issued_at || commitment).
  5. Inclusion    the leaf is in the batch's Merkle root (RFC 6962 audit path).
  6. Chain        chain = SHA256("tectra-chain-v1" || prev_chain || root || N); N is the registry size
                  publicly committed by that batch.
  7. Threshold    t(N) recomputed from the stated N and the 1e-6 wrong-attribution budget, N >= the
                  committed log size at check time, and score >= t(N).
  8. Timestamp    (optional, via OpenTimestamps) the chain hash is anchored in Bitcoin, so the mark
                  provably existed before that block - it cannot have been added or back-dated later.
No Tectra account is needed. A verified signature authenticates the issuer's
statement; it does not independently replay the watermark detection or prove
that a scene happened. A key embedded in the receipt is never a trust anchor.
"""

import argparse
import base64
import hashlib
import json
import math
import re
import struct
import subprocess
import sys
import tempfile
import urllib.request

N_BITS = 80


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha(*p):
    h = hashlib.sha256()
    for x in p:
        h.update(x)
    return h.digest()


def node(a, b):
    return sha(b"\x01", a, b)


def verify_inclusion(leaf, index, size, path, root):
    if index >= size:
        return False
    fn, sn, r = index, size - 1, leaf
    for p in path:
        p = bytes.fromhex(p)
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node(p, r)
            if not fn & 1:
                while fn and not fn & 1:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


def threshold(n, fp=1e-6):
    target, lo, hi = fp / max(n, 1), 0.0, 12.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if 0.5 * math.erfc(mid / math.sqrt(2)) > target else (lo, mid)
    return hi / math.sqrt(N_BITS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("receipt")
    ap.add_argument("--video", help="the checked copy (verifies the receipt's file hash)")
    ap.add_argument("--original", help="v2 receipts: a file you hold, tested against the registered delivered file")
    ap.add_argument("--key", help="expected public key (hex); default: fetch from https://tectra.vision/api/v1/log")
    a = ap.parse_args()
    with open(a.receipt) as f:
        R = json.load(f)
    st, ok_all = R["statement"], True

    def check(name, ok, detail=""):
        nonlocal ok_all
        ok_all &= bool(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  - ' + detail) if detail else ''}")

    print("Tectra receipt verification")
    key = a.key
    if not key:
        try:
            key = json.load(urllib.request.urlopen("https://tectra.vision/api/v1/log", timeout=15))["receipt_public_key"]
        except Exception:
            print("  FAIL  trusted key unavailable; supply --key from an independently trusted source")
            return sys.exit(2)
    try:
        from nacl.signing import VerifyKey
        VerifyKey(bytes.fromhex(key)).verify(json.dumps(st, sort_keys=True, separators=(",", ":")).encode(),
                                             base64.b64decode(R["signature"]))
        check("1 signature", key == R["public_key"], f"key {key[:16]}...")
    except Exception as e:
        check("1 signature", False, str(e))

    if a.video:
        h = file_sha256(a.video)
        check("2 file hash", h == st["file_sha256"], h[:16] + "...")
    else:
        print("  skip  2 file hash (no --video given)")

    P, res = st.get("proof"), st["result"]
    if not isinstance(P, dict):
        check("3 registration proof", False, "not available yet; obtain a fresh receipt after the registration log is updated")
        return sys.exit(1)
    mid = int(P["mark_id"], 16)
    commit = bytes.fromhex(P["commitment"])
    if P.get("opening"):
        o = P["opening"]
        enc = lambda s: (s or "").encode()  # noqa: E731
        c2 = sha(bytes.fromhex(o["salt"]), b"\x1f", enc(o["owner"]), b"\x1f", enc(res.get("label")), b"\x1f", enc(res.get("tool")))
        check("3 opening", c2 == commit, f"issued to \"{o['owner']}\"" + (f", AI tool \"{res['tool']}\"" if res.get("tool") else ""))
    else:
        print("  info  3 opening withheld (owner data erased on request; the mark's existence and date remain provable)")
    ver = P.get("log_version", 1)
    if ver >= 2:
        C = P["content"]
        rec = sha(b"tectra-content-v1", bytes.fromhex(C["delivered_sha256"]), struct.pack(">Q", C["delivered_size"]),
                  bytes.fromhex(C["reference_manifest_sha256"]))
        ok_m = C.get("reference_manifest") is None or hashlib.sha256(C["reference_manifest"].encode()).hexdigest() == C["reference_manifest_sha256"]
        check("4a content record", rec.hex() == C["record"] and ok_m,
              f"log commits to delivered file {C['delivered_sha256'][:16]}... ({C['delivered_size']} bytes) + reference manifest")
        if a.original:
            h0 = file_sha256(a.original)
            check("4b original file", h0 == C["delivered_sha256"], "the file you hold IS the registered delivered file"
                  if h0 == C["delivered_sha256"] else "this file is NOT the registered delivered file")
        leaf = sha(b"\x00", b"tectra-log-v2", mid.to_bytes(6, "big"), struct.pack(">Q", P["issued_at"]), commit, rec)
    else:
        print("  info  4a content: v1 receipt - the log binds who/when, NOT the video content (weaker binding)")
        if a.original:
            check("4b original file", False, "this receipt has no registered-file commitment; exact-file verification is unavailable")
        leaf = sha(b"\x00", b"tectra-log-v1", mid.to_bytes(6, "big"), struct.pack(">Q", P["issued_at"]), commit)
    check("4 leaf", leaf.hex() == P["leaf"], f"mark {P['mark_id']} issued {P['issued_at']} (log v{ver})")

    B = P.get("batch")
    if not B:
        check("5 inclusion", False, "mark not yet sealed into a batch (re-check later)")
        return sys.exit(1)
    root = bytes.fromhex(B["root"])
    check("5 inclusion", verify_inclusion(leaf, B["index"], B["leaf_count"], B["path"], root),
          f"leaf {B['index']} of {B['leaf_count']} in batch {B['id']}")
    chain = sha(b"tectra-chain-v1", bytes.fromhex(B["prev_chain"]), root, struct.pack(">Q", B["total_size"]))
    check("6 chain", chain.hex() == B["chain"], f"batch commits registry size N={B['total_size']}")

    n_used, t_stated = res["registry_size_used"], res["threshold"]
    g = int(res.get("geometry_candidates", 1))  # v2.3 receipts: alignments tried per ID (older receipts: 1)
    fp = float(res.get("fp_budget", 1e-6))
    if res["method"] == "assisted":
        # v2.5 fingerprint-assisted decision: union bound over the H hypotheses actually scored
        H = int(res["assisted_hypotheses"])
        t_re = threshold(H, fp)
        ok_t = abs(t_re - t_stated) < 1e-3 and res["score"] >= t_re and fp <= 5e-7 + 1e-12
        check("7 threshold", ok_t, f"assisted: H={H} hypotheses, budget {fp:g}, t(H)={t_re:.4f}, score={res['score']} "
              "(blind path used the other half of the 1e-6 budget; candidate set is not reproducible offline)")
    else:
        t_re = threshold(n_used * g, fp)
        ok_t = abs(t_re - t_stated) < 1e-3 and n_used >= st["log"]["committed_size"] and (res["score"] >= t_re or res["method"] == "checksum")
        check("7 threshold", ok_t, f"N={n_used} >= committed {st['log']['committed_size']}, alignments={g}, budget {fp:g}, "
              f"t(N*{g})={t_re:.4f}, score={res['score']}")

    try:
        bt = json.load(urllib.request.urlopen(f"https://tectra.vision/api/v1/log/batches/{B['id']}", timeout=15))
        if bt.get("ots_proof_b64") and bt["chain"] == B["chain"]:
            with tempfile.TemporaryDirectory() as d:
                open(f"{d}/c.bin", "wb").write(bytes.fromhex(B["chain"]))
                open(f"{d}/c.bin.ots", "wb").write(base64.b64decode(bt["ots_proof_b64"]))
                import os
                import shutil
                ots = shutil.which("ots") or os.path.join(os.path.dirname(sys.executable), "ots")
                if not os.path.exists(ots):
                    raise FileNotFoundError
                r = subprocess.run([ots, "verify", f"{d}/c.bin.ots"], capture_output=True, text=True, timeout=120)
                out = (r.stdout + r.stderr).strip().splitlines()
                msg = next((l for l in out if "Bitcoin block" in l or "Pending" in l or "pending" in l), out[-1] if out else "")
                if "Bitcoin node" in msg or "bitcoin.conf" in msg:  # no local node: show the attestation instead
                    info = subprocess.run([ots, "info", f"{d}/c.bin.ots"], capture_output=True, text=True, timeout=60).stdout
                    blocks = sorted(set(re.findall(r"BitcoinBlockHeaderAttestation\((\d+)\)", info)))
                    print(f"  skip  8 bitcoin timestamp - attested in Bitcoin block {', '.join(blocks) or '?'}; "
                          "full check needs a Bitcoin node (or paste the .ots at https://opentimestamps.org)")
                elif "ending" in msg:
                    print(f"  wait  8 bitcoin timestamp - {msg} (anchoring takes a few hours)")
                else:
                    check("8 bitcoin timestamp", "Bitcoin block" in msg or "Success" in msg, msg)
        else:
            print("  skip  8 bitcoin timestamp (no proof published yet)")
    except FileNotFoundError:
        print("  skip  8 bitcoin timestamp (install: pip install opentimestamps-client)")
    except Exception as e:  # noqa: BLE001
        print(f"  skip  8 bitcoin timestamp ({e})")

    print("\nRESULT:", "VALID" if ok_all else "INVALID")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
