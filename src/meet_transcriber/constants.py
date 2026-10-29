"""Hard-coded pipeline constants.

The pipeline currently has no per-call tuneables — transcription (voz-cli) and
diarization (who-cli) are both single-model Swift binaries with no runtime
knobs. This file is kept as the home for anything that becomes tweakable later.
"""
from __future__ import annotations
