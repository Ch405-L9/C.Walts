# Source Analysis and Decisions

## What the supplied media establishes

The owner supplied two explicit classes:

1. **Desired:** standalone ElevenLabs recordings.
2. **Undesired:** device or explanatory screen recordings in the source bundle.

This classification is owner-provided and controls corpus labeling.

## Positive media mapping

A waveform comparison against `11labs_voxs.m4a` aligned the standalone files with the supplied transcript at approximately:

| File | Approximate start in compilation | Transcript section |
|---|---:|---|
| Hanna | 00:21 | reflective / theological passage |
| Jessica | 06:58 | technical security passage |
| Seán | 07:42 | technical security passage |
| B. Lawson | 08:36 | professional workflow introduction |

The mapping supports the script assignments. It does not establish universal acoustic superiority.

## Visual inspection of screen recordings

- `07-30-26_18-26-39`: device reader playback;
- `07-30-26_19-47-19`: voice-selection interface;
- `08-01-26_07-27-53`: extended device-reader playback;
- `08-01-26_07-36-40`: wireless-debugging settings, unrelated to delivery.

## Important limitation

The complete negative recordings were not professionally transcribed in this package. Their negative classification comes directly from the owner. Claude must not invent detailed acoustic defects that have not been measured.

## Corpus decision

The initial production collection receives:

- textual market rules;
- approved before/after pairs;
- positive-reference annotations;
- evaluation prompts;
- source metadata.

The following remain outside the text collection:

- MP3, M4A, MP4, ZIP, and PDF binaries;
- excluded wireless-debugging media;
- full source texts with unresolved licensing;
- raw negative recordings as positive exemplars.
