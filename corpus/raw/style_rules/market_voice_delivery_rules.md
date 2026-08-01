# Market Voice-Delivery Rules
## Initial policy for C.Walts

**Status:** approved seed policy  
**Purpose:** market-facing voice-over, explainer, technical narration, professional introductions, and educational narration  
**Priority:** professional market practice first; owner preference only as a narrow adjustment

---

# 1. Non-negotiable delivery qualities

A target performance should sound:

- human and intentional;
- clear without sounding over-enunciated;
- confident without sounding like an announcer;
- conversational without becoming casual or sloppy;
- paced by meaning rather than punctuation alone;
- varied in emphasis and sentence contour;
- appropriate to the subject, audience, and platform.

Reject performances that sound:

- uniformly stressed;
- mechanically timed;
- flat at every sentence ending;
- artificially cheerful;
- over-explained;
- excessively theatrical;
- chopped into identical phrase lengths;
- detached from the meaning;
- like generic assistant narration.

---

# 2. Script construction

## Use one principal thought per breath group

Long written sentences should be divided into natural spoken units. Each unit should carry one clear idea.

## Lead with the point

For commercial and product content:

1. hook or problem;
2. clear benefit;
3. concise explanation or proof;
4. call to action.

For technical content:

1. identify the risk or concept;
2. explain what it does;
3. explain what it does not do;
4. state the operational consequence.

## Write for the ear

Prefer:

- familiar words;
- direct verbs;
- contractions where the register permits;
- sentence-length variation;
- explicit transitions only when needed;
- punctuation that supports a natural read.

Avoid:

- stacked subordinate clauses;
- strings of nouns;
- repeated introductory phrases;
- parenthetical overload;
- a written-paper cadence read aloud unchanged.

---

# 3. Pace policy

There is no universal words-per-minute target.

Use these as project test ranges:

| Register | Initial target | Notes |
|---|---:|---|
| Commercial or short explainer | 140–165 WPM | Maintain energy without rushing the CTA |
| Professional introduction | 135–160 WPM | B. Lawson reference is approximately 146 WPM |
| Technical explainer | 90–135 WPM | Slow at permission boundaries, warnings, and exact terms |
| Reflective or theological narration | 90–120 WPM | Space is acceptable when it serves meaning |
| Dense legal or compliance material | 85–125 WPM | Clarity and preservation outrank speed |

These ranges are evaluation targets, not universal facts. Content density, visuals, music, unfamiliar terminology, and audience expertise may require adjustment.

Avoid constant pace. Familiar phrases can move faster; new, high-risk, or technical information should receive more space.

---

# 4. Pause and emphasis

Use pauses to:

- separate ideas;
- prepare a contrast;
- give the listener time to absorb a technical point;
- create a deliberate transition;
- frame a CTA.

Do not pause after every comma or insert dramatic pauses without semantic purpose.

Emphasize:

- the primary benefit;
- the contrast word;
- the risk boundary;
- the action;
- the protected technical term.

Do not emphasize every adjective, brand term, or sentence ending.

---

# 5. ElevenLabs baseline

Official ElevenLabs guidance describes common starting settings near:

```yaml
speed: 1.00
stability: 0.50
similarity_boost: 0.75
style_exaggeration: 0.00
```

The supplied positive files cluster near that baseline:

| Voice | Speed | Stability | Similarity | Style |
|---|---:|---:|---:|---:|
| Hanna | 1.08 | 0.50 | 0.75 | 0.04 |
| Jessica | 1.00 | 0.40 | 0.65 | 0.15 |
| Seán | 1.00 | 0.50 | 0.75 | 0.00 |
| B. Lawson | 1.01 | 0.47 | 0.72 | 0.09 |

Treat filenames as provenance metadata. Do not assume the encoded values alone caused the preferred result.

Operational rules:

- choose the voice before over-tuning sliders;
- use preview text that matches the intended emotion and register;
- use a full sentence or short paragraph when testing subtle delivery;
- keep style exaggeration restrained unless evaluation shows a benefit;
- generate multiple takes;
- select by listener evaluation and preservation checks;
- avoid extreme speed or stability settings without a measured reason.

---

# 6. Platform-facing commercial rules

For paid or short-form video:

- establish the message and brand early;
- use high-quality human-sounding voice-over;
- keep the CTA consistent across voice, caption, and visual;
- tailor duration and energy to the placement;
- create horizontal, vertical, and square versions where required;
- assume some viewers will initially watch without sound, so captions and visuals must still communicate the point.

---

# 7. Evaluation dimensions

Score each performance from 1 to 5:

| Dimension | 1 | 5 |
|---|---|---|
| Naturalness | robotic | convincingly human |
| Meaning-led phrasing | arbitrary | phrasing follows ideas |
| Pace control | uniform or rushed | adaptive and clear |
| Emphasis | random or flat | selective and meaningful |
| Professional credibility | synthetic or amateur | passes a blind A/B against a human read |
| Genre fit | mismatched | appropriate |
| Preservation | changes meaning | exact meaning retained |
| Listener effort | tiring | easy to follow |

## Acceptance criteria

These are the thresholds a take must MEET. They are measurements to be taken,
not a statement about any take's current standing.

1. Mean score across the eight dimensions is at least 4.0.
2. Preservation scores 5. No other dimension may compensate for it — a take that
   changes meaning is rejected at any average.
3. No single dimension scores below 3.
4. Professional credibility is scored by blind A/B: at least three listeners who
   have not seen the script compare the take against a human read of the same
   copy. A score of 5 requires that no listener identifies the take as synthetic
   more often than chance.
5. Every protected term listed for the script survives verbatim.

A take that misses any one of these is re-recorded or rewritten. Passing them
qualifies the take against this policy and nothing wider.

---

# 8. Sources used for the initial policy

Official and current sources:

- ElevenLabs Voice Design documentation: voice, age, emotion, timbre, pacing, and delivery should be specified; preview text should match the intended performance.
- ElevenLabs Text-to-Speech best practices: voice selection is central; natural narrative writing and restrained pause controls improve delivery.
- ElevenLabs voice settings documentation: lower stability increases variation; high stability may become monotonous; style exaggeration can reduce stability; speed extremes may affect quality.
- Google Ads creative guidance: high-quality human voice-over is a recognized video creative attribute.
- Google Demand Gen creative guidance: CTA should be reinforced in voice-over and visual text.
- Descript voice-over guidance: commercial and explainer reads often test around 150–160 WPM.

URLs are recorded in `docs/web-research-sources.md`.
