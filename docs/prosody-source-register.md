# Prosody Source Register — v0.3.0-rc.2

Narrative companion to `config/glossary_sources.yaml`, which is the authority.
Every field the owner asked to record — title, publisher, URL, access date,
license, commercial-ingestion status, checksum, approved-or-quarantined status —
lives in that YAML file, one block per source.

Access date for every source: **2026-08-01**.

## What was decided, and why

**The canonical ToBI source cannot be used.** The Guidelines for ToBI Labelling
(Beckman & Ayers Elam, Ohio State University Research Foundation) are the
document everyone cites, and their terms of use restrict the accompanying
material to non-commercial use and prohibit redistribution by other sites. That
is the same refusal class as the Buckeye corpus in `config/sources.yaml`. It is
recorded as `refused`, with a checksum, so the exclusion is auditable rather
than merely claimed. MIT OpenCourseWare's ToBI course is CC BY-NC-SA 4.0 and is
refused on the same grounds.

This is worth stating plainly because it shapes everything else: the glossary's
ToBI entry is grounded in **CC BY literature that describes the system**, not in
the OSU document. No byte of the OSU or MIT material appears in this repository.

**Seven CC BY 4.0 sources carry the definitions.** Four Laboratory Phonology
articles and three open-access journal articles, all verified by reading the
JATS `<license>` element out of the retrieved article XML rather than trusting a
publisher web page. Snapshots are committed under
`docs/evidence/source-snapshots/` and can be checked independently:

```
sha256sum -c docs/evidence/source-snapshots/SHA256SUMS
```

CC BY 4.0 permits commercial use and redistribution with attribution.
Attribution is given in `NOTICE`.

**Two sources are cited but not ingested.** The W3C SSML 1.1 Recommendation is
the standards-body definition of prosody, but the W3C Document License permits
reproduction only without modification — and chunking a specification for
retrieval is a modification. That is the same unresolved-derivative question
that quarantined the Santa Barbara corpus, so SSML is `quarantined`: cited,
never embedded. Universitat Pompeu Fabra's Sp_ToBI training material is
directly on point about break-index levels but carries **no license statement at
all**, and an absent license is not a permissive one.

## Coverage: 14 grounded, 3 project-defined

Of the seventeen required terms, fourteen are defined against the approved CC BY
sources. Three are **C.Walts production terms** — they name things a voice
director needs to talk about that the phonology literature does not carve out
under those names:

| Term | Status | Anchor |
|---|---|---|
| textual prosody | project term | `pmc11592126-silent-reading-rhythm` — readers build rhythm and prominence from text with no signal present |
| breath group | project term | `pmc12468771-l2-prosody-perception` uses it as a constituent above the prosodic word |
| cadence | project term | `pmc11592126-silent-reading-rhythm`; the production sense is C.Walts', not the literature's |

Each of the three says so in its own glossary entry and names its anchor. They
are not presented as established phonological categories, and they carry the
same source and license metadata as every other chunk, so a retrieval result can
always be traced to an approved record.

## What this register does not claim

- It does not claim the glossary is a substitute for the ToBI guidelines. It is
  a working vocabulary for voice direction that stays consistent with the
  published record.
- It does not claim the CC BY sources agree with each other. `labphon-32`
  is included precisely because it documents that transcription systems are
  contested and revisable.
- Checksums fix what was retrieved on 2026-08-01. They are not a guarantee that
  the live URL still serves those bytes.
