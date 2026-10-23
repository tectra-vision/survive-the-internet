# Verify a signed record and an exact original

```bash
pip install pynacl
python verify_receipt.py receipt.json --video checked-copy.mp4 \
  --original registered-original.mp4 --key EXPECTED_PUBLIC_KEY_HEX
```

Obtain the expected signing key separately from the receipt. The current key and instructions are on [Tectra's transparency page](https://tectra.vision/transparency#verify-a-check-receipt).

`--video` compares the supplied copy with the hash in the signed check statement. `--original` compares the supplied original with the registered delivered-file commitment. The latter requires log v2; requesting it with a legacy v1 receipt fails explicitly. A valid receipt does not independently rerun watermark detection or establish that a depicted event happened. Read the individual checks; pending or skipped timestamps are not independently confirmed.

The public face sample uses a legacy v1 registration. It can demonstrate receipt verification with `--video`, but cannot demonstrate the registered-original check. Create a new log-v2 registration for that.

```bash
python -m unittest discover -s tests -v
```
