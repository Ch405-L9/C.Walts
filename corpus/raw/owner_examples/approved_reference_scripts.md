# Approved Delivery-Ready Reference Scripts

Derived from `references/transcripts/reference_scripts.md` in the C.Walts handoff
package. Only the two high-confidence, owner-produced scripts appear here.

**Excluded from this file and from the collection:** the Hanna reflective
passage. It was reconstructed from an imperfect automated transcript and its
original publication provenance was not established. It remains
evaluation-only under `references/transcripts/` (local, never committed, never
ingested) per the C.Walts README limitation.

---

## SCR-001 — Professional introduction (matches POS-004, B. Lawson)

- Register: professional introduction
- Reference pace: approximately 146 WPM
- Transcript confidence: high
- Use: target for modern professional and commercial pacing

> I help teams turn complex ideas into clear, practical solutions, and I like
> building systems that feel fast, reliable, and easy to use. Whether I'm
> designing a workflow, refining a product, or solving a technical problem, I
> focus on clarity, confidence, and strong execution from start to finish.

Why this reads well aloud: the first clause states the benefit before the
method; the second uses a three-item parallel list that gives the reader three
natural breath groups; the closing phrase carries the emphasis rather than
trailing off.

---

## SCR-002 — Technical security explanation (matches POS-002 Jessica, POS-003 Seán)

- Register: technical explainer
- Reference pace: approximately 76–92 WPM
- Transcript confidence: high for intended meaning; punctuation and minor
  wording normalized from the supplied transcript
- Protected terms: `domain-wide authority`, `service account`, `impersonate`,
  `OAuth scopes`, `Admin console`, `principle of least privilege`
- Use: evaluate clarity on dense security language and exact terminology

> Important security consideration: understanding impersonation. When you
> delegate domain-wide authority, you are not granting the service account
> direct access to all user data. Instead, you are authorizing it to impersonate
> specific users when making API calls. Access is on behalf of a user. Your
> application must specify which user to impersonate for each API request. The
> application then acts with the permissions of that specific user, not with
> elevated or domain-wide privileges. Access is constrained by two factors: the
> permissions of the impersonated user and the OAuth scopes authorized in the
> Admin console. It cannot access data that the impersonated user cannot access.
> Principle of least privilege.

Why this reads well aloud: it names the concept, states what it does not do
before what it does, and keeps each constraint in its own short unit. The
slower measured pace is a function of information density, not a universal
default.

---

## Provenance rule

Transcript corrections are not authoritative quotations. Verify original
publication before any public reuse.
