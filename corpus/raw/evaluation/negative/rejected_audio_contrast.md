# Rejected and Contrast Voice References

**Status:** evaluation-only  
**Owner classification:** examples of delivery that should not be reproduced

## Negative-pattern labels

Use the screen-recording references to test for:

- robotic or device-like cadence;
- excessive explanatory tone;
- uniform speed;
- phrase boundaries driven only by punctuation;
- unnatural pauses;
- flat or repetitive sentence contour;
- over-enunciation;
- generic assistant affect;
- delivery that ignores genre and information density.

## File-level policy

### `screen_recorder_07-30-26_18-26-39.mp4`

- Initial class: `negative_contrast`
- Visible context: device reader playback
- Use: short contrast sample
- Do not ingest as a positive exemplar

### `screen_recorder_07-30-26_19-47-19.mp4`

- Initial class: `context_only`
- Visible context: voice-selection interface
- Use: configuration provenance only
- Do not score as a complete performance

### `screen_recorder_08-01-26_07-27-53.mp4`

- Initial class: `negative_contrast`
- Visible context: long device-reader playback
- Use: primary contrast asset for mechanical or explaining delivery
- Do not ingest as a positive exemplar

### `screen_recorder_08-01-26_07-36-40.mp4`

- Initial class: `excluded`
- Visible context: wireless-debugging settings
- Reason: unrelated to voice-delivery quality

## Contamination test

A retrieval result for a request such as “make this sound natural” must not cite a negative recording as positive guidance.

Negative-pattern documents may be returned only when the request explicitly asks:

- what to avoid;
- why a read sounds robotic;
- contrastive analysis;
- rejection testing.
