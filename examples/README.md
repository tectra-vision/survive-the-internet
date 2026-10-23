# Video authentication with the hosted API

Sign your videos, verify registered originals and identify shared copies. This example calls the current dashboard/API video engine. It does not require the legacy Python SDK or access to local watermark keys.

## Sign, share, verify

Create a workspace on [Tectra](https://tectra.vision) and securely set `TECTRA_API_KEY` in your server environment. Do not put it in a browser application.

```bash
python -m pip install requests
python video_authentication.py mark render.mp4 --out signed.mp4 \
  --source ai_generated --profile maximum-quality \
  --label "My export" --tool "My generating model"

python video_authentication.py check signed.mp4 --out check.json
```

The example waits for the job, saves `signed.mp4.job.json`, and downloads only a completed result. Maximum quality must explicitly pass its quality floor. Refusals and other errors stop the download. A delivered file may fail its separate robustness self-test; the CLI reports that notice. It never overwrites an existing output.

Files are limited to 100 MB and hosted marking processes up to ten minutes per job. Retain the delivered video and report in your system; hosted download files expire. A timeout leaves the existing job running—poll its job ID instead of submitting another chargeable job.

`standard` maps to the API's `balanced`; `maximum-quality` maps to `fidelity`. Source categories are `ai_generated`, `ai_edited`, `camera_captured` and `unspecified`. A source category is the registrant's declaration.

## Authenticate an exact original

A successful source check is not an exact-file verdict. When a check returns a receipt, the example saves `check.receipt.json`.

Use the published verifier and a trusted expected signing key obtained separately from the receipt:

```bash
python -m pip install pynacl
curl --fail -O https://tectra.vision/verify_receipt.py
python verify_receipt.py check.receipt.json --video signed.mp4 \
  --original signed.mp4 --key EXPECTED_PUBLIC_KEY_HEX
```

`--video` checks which file the receipt describes. `--original` separately compares a supplied file with the registered delivered-file commitment; it requires a log-v2 receipt. Legacy v1 receipts cannot authenticate that original. A record awaiting batch inclusion cannot yet pass the full proof. A missing receipt, unsupported binding or failed signature is not successful authentication.

Read the individual results. An independently verified receipt does not replay watermark detection, and a skipped or pending Bitcoin timestamp is not a confirmed timestamp. The current signing key and instructions are on the [transparency page](https://tectra.vision/transparency).

## Shared copies

```bash
python video_authentication.py check downloaded-copy.mp4 --out shared-check.json
```

A detected watermark identifies a registration after supported transformations. It can remain on edited content. No mark found is not a human-made classification. The current profiles have different quality and sharing resilience: [inspect the samples and measured results](https://tectra.vision/benchmarks).

## Camera recordings and video editions

For recordings, pass `--source camera_captured` and label the export using your own recording identifier. Authenticating capture needs protected device credentials and a camera/recorder integration; an uploaded-file declaration alone does not establish capture authenticity.

For an NFT or video edition, label the registered master with your edition identifier and link the registration proof in your platform's metadata. Tectra's record binds the registered file. Your platform handles minting, ownership transfers and edition rules.

## Running the example checks

```bash
python -m unittest discover -s tests -v
```

These checks cover API workflow behavior and failure handling. They do not measure watermark accuracy.
