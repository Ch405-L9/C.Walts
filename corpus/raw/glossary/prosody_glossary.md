# C.Walts Prosody Glossary
## Authoritative working vocabulary for voice direction

**Status:** approved reference vocabulary
**Owner:** BADGRTechnologies LLC
**Purpose:** give every rule, evaluation, and rewrite in this corpus one fixed meaning per term

This glossary is owner-authored. Its definitions are grounded in seven
open-access works licensed CC BY 4.0, each retrieved and license-verified on
2026-08-01 by reading the license statement out of the retrieved article itself.
The full audit, including refused and quarantined candidates, is
`config/glossary_sources.yaml`; attribution is in `NOTICE`.

Every entry names the approved source that grounds it, using the source ids from
that register. Three entries are marked **C.Walts production term**: they name
something a voice director needs a word for that the phonology literature does
not carve out under that name. Those entries say so, and name the approved
source their concept sits against, rather than borrowing authority they do not
have.

One deliberate absence. The canonical ToBI labelling guidelines from the Ohio
State University Research Foundation are restricted to non-commercial use and
may not be redistributed. No text from them is used here. The ToBI entries below
are grounded in CC BY literature that describes the system.

---

## prosody

**Class:** core concept
**Grounded in:** labphon-29-new-methods, labphon-11-ipra

Prosody is the organisation of speech above the individual consonant and vowel:
pitch and its movement over time, the timing and rhythm of syllables, pausing,
loudness, speaking rate, and the relative prominence of words against their
neighbours. It is what carries the difference between two readings of identical
words.

Two facts about prosody govern how this corpus treats it. First, prosody is
structured, not decorative: the same sentence read with different phrasing and
prominence conveys different information, so prosodic choices are meaning
choices. Second, prosody is described at two different levels that must not be
confused — as abstract categories a listener perceives, and as continuous
measurements taken from the signal. This corpus keeps those apart as
`textual prosody` and `acoustic prosody`.

The standards-body formulation agrees: W3C's SSML 1.1 Recommendation describes
prosody as the set of features including pitch (also called intonation or
melody), timing (or rhythm), pausing, speaking rate, and the emphasis on words.
SSML is cited here and deliberately not ingested — see the register.

---

## textual prosody

**Class:** C.Walts production term
**Grounded in:** pmc11592126-silent-reading-rhythm

**This is a C.Walts production term.** The literature does not standardly split
prosody into a textual and an acoustic kind under these names; the split is ours,
and it exists because the whole C.Walts premise depends on it.

Textual prosody is the prosodic structure a reader builds from written text
alone, before any voice exists. Where a sentence invites a break, which word it
pushes into prominence, how long its runs of unstressed syllables are, whether
its clauses can be delivered on one breath — all of this is determined by the
words and their order, and is fixed before a narrator or a synthesiser touches
it.

The anchor for treating this as real rather than a convenient fiction is direct:
readers engaged in *silent* reading, with no acoustic signal present at all,
show neural markers of speech-rhythm processing. Rhythmic and prominence
structure is constructed from the text itself.

This is why a rewrite is a delivery intervention. Changing the words changes the
prosody the reader — human or model — will construct, and it does so before any
setting is tuned.

---

## acoustic prosody

**Class:** core concept
**Grounded in:** labphon-29-new-methods

Acoustic prosody is prosodic structure as measured in the speech signal:
fundamental frequency (F0) and its contour, segment and syllable duration,
intensity, pause length, and voice-quality changes such as creak at phrase edges.

The distinction from `textual prosody` is the distinction between two families
of prosodic description. One family annotates speech with abstract phonological
categories — the labels of `ToBI` are of this kind. The other computes
continuous measures, mainly F0, directly from the signal. They answer different
questions: the abstract labels say which category a listener perceives, the
acoustic measures say what the waveform did.

The practical consequence for C.Walts work: an acoustic measurement never
settles a delivery question by itself. A take can measure well on pitch range
and still be judged wrong, because prominence and phrasing are perceptual
categories that integrate several cues at once and depend on how each stretch
compares with its neighbours.

---

## ToBI

**Class:** annotation standard
**Grounded in:** labphon-11-ipra, pmc8092678-prosodic-boundaries, labphon-32-introducing-apt

ToBI stands for **Tones and Break Indices**. It is a consensus system for
labelling spoken utterances, developed to mark the intonational events that are
phonologically contrastive in a language — that is, the tonal distinctions that
change interpretation rather than merely varying between speakers.

Its theoretical basis is the Autosegmental-Metrical model of intonational
phonology. That model treats an intonation contour not as a single melodic
gesture but as a sequence of discrete tonal targets, each anchored either to a
stressed syllable or to a phrase edge, with the pitch between targets
interpolated.

A ToBI annotation is organised in parallel tiers. The **tone tier** carries the
pitch accents (see `pitch accent`, `H*`) and the edge tones (see
`boundary tone`, `L-L%`). The **break-index tier** carries a number per word
boundary recording perceived disjuncture (see `break index`). An orthographic
tier aligns both to words.

ToBI was originally designed for American English. Language-specific systems
were developed afterwards — K-ToBI for Korean, Sp_ToBI for Spanish, and others —
and their label inventories are **not** interchangeable: the same symbol can
denote different phonetic realisations across systems, which is a known and
documented problem rather than a settled matter.

ToBI is a transcription convention, not a law of speech. The system is actively
revised and contested in the literature, and this corpus uses it as shared
vocabulary for talking precisely about delivery, not as a specification any take
must satisfy.

---

## pitch accent

**Class:** tonal event
**Grounded in:** labphon-11-ipra, pmc12468771-l2-prosody-perception

A pitch accent is a tonal event associated with a lexically stressed syllable,
marking that syllable — and through it, its word — as prominent. It is the main
mechanism by which English signals which word in a phrase matters.

In ToBI notation the asterisk marks the tone that aligns with the stressed
syllable. Accents are either **simple**, carrying one tone (`H*`, `L*`), or
**bitonal**, carrying a target plus a leading or trailing tone (`L+H*`, `L*+H`,
`H+!H*`). The difference between `L+H*` and `L*+H` is not cosmetic: they place
the pitch peak differently relative to the stressed syllable, and they are used
for different discourse effects.

A downstepped accent is written with a leading exclamation mark (`!H*`),
indicating a high target realised lower than the preceding high because of
downstep rather than because it is phonologically low.

Not every language works this way. Mandarin, for example, has no pitch accents
or phrase accents at all — tone is specified lexically — which is why prosodic
habits transfer badly between languages and why a delivery note that works for
one narrator may not for another.

---

## H*

**Class:** tonal label
**Grounded in:** labphon-11-ipra, pmc12468771-l2-prosody-perception

`H*` is the **high pitch accent**: a high tonal target aligned to a lexically
stressed syllable. It is the most common accent in ordinary English declarative
speech and the default way a word is made to stand out without additional
implication.

Its systematic contrast is `L*`, the low pitch accent, which aligns a low target
to the stressed syllable. The contrast is perceptually real and asymmetric in
difficulty: listeners identify stressed syllables cued by the high accent `H*`
more reliably than those cued by the low accent `L*`.

`H*` is the starred element of several larger configurations and should not be
confused with them. `L+H*` is a bitonal accent with a low leading tone, heard as
a sharper rise into the accented syllable and typically carrying contrastive
force. `!H*` is the downstepped variant. `H*` followed by phrase and boundary
tones forms a complete nuclear configuration such as `H* L-L%`.

In C.Walts direction, "put the accent here" means placing a pitch accent — in
most neutral copy an `H*` — on the syllable that carries the point, and removing
the competing accents around it.

---

## boundary tone

**Class:** tonal event
**Grounded in:** labphon-48-seoul-korean-focus, pmc12468771-l2-prosody-perception

A boundary tone is a tonal event anchored to the **edge of a prosodic phrase**
rather than to a stressed syllable. In ToBI-family notation it is written with a
trailing percent sign: `L%` for a low phrase ending, `H%` for a high one.

Because it is anchored to the edge rather than to a stressed syllable, a
boundary tone is not about which word is important — it is about how the phrase
finishes, and therefore about whether the phrase sounds complete, suspended,
questioning, or continuing.

The inventory is language-specific and can be much larger than English's two.
Korean K-ToBI describes nine intonational-phrase boundary tones — `L%`, `H%`,
`LH%`, `HL%`, `LHL%`, `HLH%`, and longer sequences — used to carry pragmatic
meaning, with still more complex movements observed in spontaneous speech.

Boundary tones are also sensitive to information structure: bitonal boundary
tones are more likely to occur at the edges of constituents under focus than
monotonal ones.

In practice this is the entry that governs the C.Walts rule against flat
sentence endings. "Flat at every sentence ending" is a criticism of boundary-tone
monotony — the same low ending on every phrase regardless of whether the thought
is finished.

---

## L-L%

**Class:** tonal label (nuclear configuration ending)
**Grounded in:** labphon-11-ipra, pmc12468771-l2-prosody-perception

`L-L%` is a **compound label made of two separate tonal events**, and reading it
as a single symbol is the usual mistake.

- `L-` is a **phrase accent**: a low tone marking the end of an *intermediate*
  phrase. The trailing hyphen is what identifies it.
- `L%` is a **boundary tone**: a low tone marking the end of the *intonational*
  phrase that contains it. The trailing percent sign identifies it.

Written together, `L-L%` describes a phrase that ends low at both levels — the
ordinary falling, finished-sounding ending of an English declarative. A complete
nuclear configuration names the accent as well, giving forms such as `H* L-L%`
or, with a downstepped accent, `!H* L-L%`.

The parallel forms make the compositional pattern visible: `H-H%` gives the
high, rising, question-like ending; `L*H-H%` places a low accent under a rising
ending. Listeners' native language affects how reliably these are told apart —
falling contexts such as `H*L-L%` are perceived more accurately by some
listener groups than rising ones.

For C.Walts purposes `L-L%` is the notation for finality. A take that applies it
to every phrase reads as a list of finished statements rather than a connected
argument; a take that never applies it never sounds like it has landed.

---

## break index

**Class:** annotation tier value
**Grounded in:** pmc8092678-prosodic-boundaries, labphon-29-new-methods

A break index is a number recording the **perceived degree of separation between
one word and the next** — how strongly a listener hears a juncture there. It is
the second of ToBI's two core tiers, the counterpart to the tone tier, and it
annotates boundaries rather than prominences.

The prosodic hierarchy assumed by the Autosegmental-Metrical approach, which is
the theoretical basis of ToBI, distinguishes **five levels** of break indices,
conventionally numbered 0 to 4. At the low end, a value of 0 marks words so
closely joined that no separation is heard, as in cliticisation; 1 marks an
ordinary word boundary within a phrase. At the high end sit the two boundaries
that matter most: the **intermediate phrase** boundary and the **full
intonational phrase** boundary, the latter being the strongest juncture and the
one that carries a boundary tone.

Independent training material from the Sp_ToBI project describes the same
arrangement — index 4 at the end of intonational phrases, index 3 for a weaker
internal rupture. That material carries no license statement and is used here
only as corroboration, never as a source.

A break index is a **perceptual judgement**, not a measured pause length. A
strong break can be realised by final lengthening, by pitch movement, by silence,
or by a combination, and the cues trade off against each other — where final
lengthening is less, the following pause tends to be longer.

This is the entry behind the C.Walts rule to pace by meaning rather than
punctuation. Punctuation is not a break-index tier: a comma does not require a
break, and a strong break is often needed where no punctuation appears.

---

## intermediate phrase

**Class:** prosodic constituent
**Grounded in:** labphon-48-seoul-korean-focus, pmc8092678-prosodic-boundaries

The intermediate phrase, abbreviated **ip**, is a prosodic constituent smaller
than the intonational phrase and larger than the prosodic word. It groups
material that belongs together without closing off the larger thought.

In the prosodic hierarchy above the syllable, four levels are commonly defined:
the Phonological Word, the Accentual Phrase, the Intermediate Phrase (ip), and
the Intonational Phrase (IP). The ip ends in a **phrase accent** — a tone
written with a trailing hyphen, such as `L-` or `H-` — and, unlike the
intonational phrase, does not take a boundary tone of its own.

The ip is a genuinely difficult unit. It was added to some ToBI systems in later
revisions, and demarcating intermediate phrases reliably in real speech data is
not straightforward; some analyses exclude the level for exactly that reason.
This glossary records it because `L-L%` cannot be explained without it, not
because its boundaries are easy to place.

In direction terms, an ip boundary is the break that says "still going" — enough
separation to let a clause land, not enough to end the sentence.

---

## intonational phrase

**Class:** prosodic constituent
**Grounded in:** pmc8092678-prosodic-boundaries, labphon-48-seoul-korean-focus

The intonational phrase, abbreviated **IP**, is the largest prosodic constituent
in the hierarchy and the domain of a complete tune. One IP carries one or more
pitch accents plus the edge tones that finish it — a phrase accent and a
boundary tone.

It ends at the strongest juncture, break index 4, and is typically marked by some
combination of final lengthening, pitch movement, and silence.

Its size is empirically constrained rather than arbitrary: intonational phrases
run about one second and three to four words on average. That figure is the most
useful single number in this glossary for script construction, because it says
roughly how much material an audience processes as one unit.

Under contrastive focus the IP does real work: a focused constituent is more
likely to be realised as its own intonational phrase, separated from what
surrounds it.

The C.Walts rule "one principal thought per breath group" is this unit,
approached from the writing side rather than the annotation side.

---

## prominence

**Class:** perceptual property
**Grounded in:** labphon-29-new-methods, labphon-48-seoul-korean-focus

Prominence is the perceptual property of a syllable or word **standing out
relative to its neighbours**. It is what "emphasis" means when the term is used
precisely.

Three things about prominence are load-bearing for this corpus.

It is **relative, not absolute.** A syllable is prominent compared with the
syllables around it. This is why emphasising every important word emphasises
nothing: prominence marked everywhere is prominence nowhere, and it is the
mechanism behind the rejection of uniformly stressed delivery.

It is **multi-cued.** Pitch movement, duration, loudness, and vowel quality all
contribute, and a listener integrates them together with the relationships
between neighbouring prosodic elements — comparing successive accents and
successive junctures rather than judging each in isolation.

It is a **judgement, not a measurement.** No single acoustic threshold defines
it. Loudness and pitch each predict it imperfectly, which is why this corpus
scores delivery by listener evaluation and treats acoustic settings as inputs
rather than as verdicts.

---

## contrastive focus

**Class:** information-structural category
**Grounded in:** labphon-48-seoul-korean-focus, pmc12468771-l2-prosody-perception

Contrastive focus marks a constituent as **picked out against alternatives** —
this one, not the others that were available. It differs from ordinary new-
information focus in that the alternatives are live in the context.

Its prosodic marking is not simply "say it louder". A focused constituent
consistently initiates a new prosodic phrase, and is more likely to be realised
as a full intonational phrase than its unfocused counterpart. Within the focused
material, duration expands — particularly at the phrase edges — the pitch range
expands, and the register is raised. Bitonal boundary tones become more likely
than monotonal ones at its edges. In English the accent placement itself carries
contrast, with `L+H*` the characteristic contrastive accent.

The practical consequence, and the reason this entry exists in a voice-direction
corpus: **contrast is marked by restructuring the phrase, not by increasing
volume.** A direction to "hit that word harder" usually produces a louder
uniform read. The change that actually reads as contrast is to give the word its
own phrase, lengthen its edges, and take the competing accents off the words
around it.

---

## information structure

**Class:** organising principle
**Grounded in:** labphon-48-seoul-korean-focus, labphon-29-new-methods

Information structure is the organisation of a sentence according to **how its
content stands relative to the discourse** — what is already given against what
is new, what the sentence is about against what is said about it, what is in
focus against what is background.

It matters here because it is the layer that decides where prosody goes.
Prominence and phrasing are not distributed evenly or by syntax alone; they are
placed according to which material is new, contrastive, or being picked out. The
location of pitch accents contributes to marking information structure, and
gradient variation in how an accent is realised — mainly its pitch excursion and
duration — conveys degree of emphasis.

The relationship is not a fixed mapping. The assumption of a direct link between
focal structure and pitch-accent distribution holds imperfectly even within
English and is empirically inadequate across languages.

For script work this is the layer above word choice. When a rewrite improves
delivery, it usually did so by changing what is presented as given and what is
presented as new — putting the known material first and the new material where a
prominence can land on it.

---

## breath group

**Class:** C.Walts production term
**Grounded in:** pmc12468771-l2-prosody-perception, cwalts_style_rules §2

**This is a C.Walts production term.** It appears in the prosody literature as a
constituent above the prosodic word in some languages' prosodic structure, but it
is not a ToBI tier and it is not part of the Autosegmental-Metrical label
inventory. The C.Walts sense is narrower and is a writing instruction.

A breath group is a stretch of script intended to be delivered **on one
exhalation, carrying one principal thought**. It is the unit the C.Walts
script-construction rule is stated in: long written sentences are divided into
natural spoken units, each carrying one clear idea.

Its practical relative in the annotation vocabulary is the `intonational phrase`,
which runs about one second and three to four words on average. A breath group
that materially exceeds that is a warning that the sentence will need a break the
writer did not plan, and the narrator will put it somewhere arbitrary.

The term is kept separate from `intonational phrase` because they are reached
from opposite directions: an intonational phrase is observed in a recording, a
breath group is decided in a script.

---

## cadence

**Class:** C.Walts production term
**Grounded in:** pmc11592126-silent-reading-rhythm (rhythm anchor only)

**This is a C.Walts production term with no direct equivalent in the phonology
literature.** It is a direction word, recorded here so that it means one thing
across this corpus rather than drifting.

Cadence is the **recognisable shape of a speaker's phrase endings together with
the regularity of their phrase lengths** across a passage. It is a property of a
stretch of delivery, not of a single phrase.

Two failure modes name themselves in this vocabulary. A take **chopped into
identical phrase lengths** has a cadence problem: the phrase lengths have become
regular enough to be predicted. A take **flat at every sentence ending** has a
cadence problem of the other kind: the endings have collapsed onto one boundary
shape, in ToBI terms `L-L%` everywhere regardless of whether the thought is
finished.

The nearest precise terms are `sentence rhythm` for the timing half and
`boundary tone` for the ending half. Where a note can be written in those terms
instead, it should be — they are measurable and this one is not.

---

## sentence rhythm

**Class:** timing property
**Grounded in:** pmc11592126-silent-reading-rhythm, labphon-29-new-methods

Sentence rhythm is the **pattern formed by the alternation of prominent and
non-prominent syllables** across a sentence, and the timing that results from it.

The property that makes it a writing concern rather than only a performance
concern is that it is constructed from text. Silent reading, with no acoustic
signal at all, engages speech-rhythm processing — readers build rhythmic
structure from the words in front of them. Word choice and word order therefore
fix a good part of the rhythm before delivery begins.

Two writing patterns predictably damage it, and both are rejected elsewhere in
this corpus for this reason. **Stacked nouns** produce long runs with no natural
place for a prominence to land, so a narrator must either flatten the run or
invent an emphasis the sentence does not support. **Uniform sentence length**
produces a regular pulse that a listener stops attending to.

Sentence rhythm is measurable from the text — syllable counts per unit, distance
between candidate prominences, run length without a break — and is the preferred
term whenever a note might otherwise be written as `cadence`.
