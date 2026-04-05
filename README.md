# Foundry UI (Real Local Pipeline)

Mobile-first local app for Foundry pipeline:
- Generate (Gemini API)
- Style (`apply_style.py`)
- Upscale (`upscale_image.py`)
- Trace (`trace_vector.py`)

## Run

```bash
cd foundry-ui-claude-real
python server.py
# open http://127.0.0.1:8787
```

## Notes

- Upload flow is fully tested end-to-end.
- Generate flow uses Gemini image endpoint; if model access differs in your account, use Upload mode.
- Outputs are written to `working/`.
