# SymbolScribe OMR Studio - Render Free Blueprint

This version deploys as a **native Python** web service on Render's **Free** plan.
It does **not** use Docker, Node/npm, a paid persistent disk, Postgres, Audiveris, or a paid API.

## Deploy on Render - no payment required

1. Extract this ZIP. Upload its **contents directly to the root** of your GitHub `Score-Condenser` repository, replacing its existing files (especially `render.yaml`). The repository root must contain `app.py`, `engine.py`, `requirements.txt`, `static/`, and `render.yaml`.
2. Commit the changes to branch `master`.
3. In Render, choose **New > Blueprint**, connect the repository, select `master`, and let Render read the root `render.yaml`.
4. Confirm the plan is **Free**. If Render presents a paid plan or asks for payment, **stop; don't approve it**. The Blueprint intentionally provisions only one free Python service.
5. After deployment, open the provided `onrender.com` URL. `/health` should respond with `{"status":"ok"}`.

Render free services may sleep when idle, have limited memory, and have monthly usage quotas. The app limits each import to 12 image/PDF pages and each file to 12 MB for better compatibility; large or complex pages can still exceed memory. The browser stores the symbol label library in localStorage; export backups regularly.

## Features

- Import PDF or multiple photos (PNG/JPG/WebP/TIFF).
- Detect *candidate* shapes/staves, label or ignore every candidate, manually box missed symbols.
- Label noteheads including **breve** and **longa**, enter staff/measure/beat/pitch details.
- Remember labeled symbol crops **on your device/browser** with JSON backup/restore.
- Preview basic staff notation in browser. Export MusicXML, compressed `.mxl`, and basic notation PDF.

## Accuracy limitation

This is a manual-proofreading prototype, **not note-perfect automatic music recognition**. Detector may miss symbols or present false detections; pitches, historical clefs, timing, meter and voice structure require manual verification. PDF engraving is basic and does not reproduce all notation accurately. No server-side uploads are retained.

## Local run

```sh
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```
