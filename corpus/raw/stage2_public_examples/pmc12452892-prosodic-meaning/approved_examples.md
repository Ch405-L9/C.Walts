## CW-049 — Identifier, limit, negation, and modality preservation

**Before**

i) Chunks should contain at least two IUs by the same speaker, so that the model may learn IU switches; ii) chunks should not contain long pauses, for efficiency of computation and to avoid IU switches that are too obvious; iii) the presence of multiple speakers in a chunk may be beneficial, as it better reflects real-life speech situations; and iv) chunks should not exceed 30 s or 448 tokens, as per WHISPER’s requirements.

**After**

Chunks should contain at least two IUs from the same speaker, so the model may learn IU switches. They should not contain long pauses, both for efficient computation and to avoid IU switches that are too obvious. The presence of multiple speakers in a chunk may be beneficial because it better reflects real-life speech situations. Finally, chunks should not exceed 30 s or 448 tokens, in line with WHISPER’s requirements.
