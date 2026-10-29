"""Merge Voz transcript segments with Who speaker turns → speaker-labeled segments."""
from __future__ import annotations

from dataclasses import dataclass

from .diarize import Turn
from .whisper_wrapper import Segment


@dataclass
class LabeledSegment:
    start: float
    end: float
    text: str
    speaker: str  # "A", "B", "C", ...


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _relabel_speakers(turns: list[Turn]) -> dict[str, str]:
    """Map SPEAKER_XX → stable A/B/C order (by first appearance).
    For >26 speakers (over-segmented diarize) falls back to S27, S28..."""
    mapping: dict[str, str] = {}
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for t in sorted(turns, key=lambda x: x.start):
        if t.speaker not in mapping:
            i = len(mapping)
            mapping[t.speaker] = letters[i] if i < 26 else f"S{i+1}"
    return mapping


def merge(segments: list[Segment], turns: list[Turn]) -> list[LabeledSegment]:
    """Assign each whisper segment the speaker with max temporal overlap."""
    if not turns:
        return [LabeledSegment(s.start, s.end, s.text, "A") for s in segments]

    relabel = _relabel_speakers(turns)
    out: list[LabeledSegment] = []

    for seg in segments:
        best_speaker = None
        best_overlap = 0.0
        for t in turns:
            if t.end < seg.start:
                continue
            if t.start > seg.end:
                break
            ov = _overlap(seg.start, seg.end, t.start, t.end)
            if ov > best_overlap:
                best_overlap = ov
                best_speaker = relabel[t.speaker]
        speaker = best_speaker or "?"
        out.append(LabeledSegment(seg.start, seg.end, seg.text, speaker))

    # collapse consecutive segments by same speaker
    collapsed: list[LabeledSegment] = []
    for seg in out:
        if collapsed and collapsed[-1].speaker == seg.speaker and seg.start - collapsed[-1].end < 1.5:
            collapsed[-1] = LabeledSegment(
                start=collapsed[-1].start,
                end=seg.end,
                text=collapsed[-1].text + " " + seg.text,
                speaker=seg.speaker,
            )
        else:
            collapsed.append(seg)
    return collapsed


def count_speakers(labeled: list[LabeledSegment]) -> int:
    return len({s.speaker for s in labeled if s.speaker != "?"})
