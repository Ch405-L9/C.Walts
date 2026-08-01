# Approved Before/After Pairs — Set 2
## Depth set added for v0.3.0-rc.2

**Status:** approved
**Use:** textual ingestion and retrieval evaluation
**Relationship to set 1:** CW-001 through CW-012 remain authoritative. This set adds twenty-five pairs across the five registers the delivery policy names, so that each register is represented by more than one or two instances.

Each pair names the prosodic mechanism the rewrite uses, in the vocabulary fixed by the prosody glossary. That is deliberate: "sounds better" is not a reusable instruction, and "the rewrite moves the prominence onto the contrasted word and gives it its own phrase" is.

---

## Pair CW-013 — Commercial: subscription app hook

**Register:** commercial voice-over
**Audience:** cold mobile viewers, sound often off at first
**Preserve:** seven days, no card

### Before

Our app is a comprehensive productivity solution designed to help busy professionals manage their tasks, calendars, and notes in one unified workspace, and you can try it free for seven days with no card required.

### After

Tasks in one app. Calendar in another. Notes somewhere else.

One workspace instead. Seven days free, no card.

### Why the after works

- the opening three fragments build a pattern, then break it — the break is where the prominence lands;
- each fragment is one breath group, so the read has somewhere to breathe;
- the offer moves to the end where a falling ending gives it finality;
- the stacked-noun run "tasks, calendars, and notes" is replaced by three short units a narrator can vary;
- both protected terms survive verbatim.

---

## Pair CW-014 — Commercial: price-objection handling

**Register:** commercial voice-over
**Audience:** viewers who have seen the price
**Preserve:** $12 a month, cancel anytime

### Before

At just $12 a month, which we think represents excellent value compared to competing products on the market, you get full access to every feature we offer, and of course you can cancel anytime.

### After

$12 a month. Every feature — not a tier, not an upsell.

Cancel anytime.

### Why the after works

- opens on the number instead of hedging toward it with "at just";
- "not a tier, not an upsell" is contrastive focus: it names the alternatives the listener is actually weighing;
- removes the self-praise, which a listener discounts and a narrator cannot say convincingly;
- three sentences of visibly different length break the uniform pulse the original had.

---

## Pair CW-015 — Commercial: fifteen-second product spot

**Register:** commercial voice-over
**Audience:** paid social placement, hard fifteen-second cap
**Preserve:** BADGR Bolt

### Before

BADGR Bolt is a reading application that centers words on the screen and allows you to adjust your reading speed to your preference, and it also includes optional comprehension quizzes so that you can check your understanding as you go.

### After

Your eyes stop moving. The words come to you.

BADGR Bolt centres each word, at whatever speed you set. Quizzes when you want them.

Read faster. Actually keep it.

### Why the after works

- the first two lines describe the experience before naming the product, which buys attention before the brand;
- "at whatever speed you set" replaces "adjust to your preference" — fewer syllables, same meaning;
- the final line carries the contrast the whole spot exists for, and it sits alone so the prominence has nothing to compete with;
- fits fifteen seconds at a commercial pace without rushing the last line.

---

## Pair CW-016 — Commercial: business-to-business service open

**Register:** commercial voice-over
**Audience:** operations leads at mid-size firms

### Before

We understand that in today's fast-paced business environment, organisations are facing unprecedented challenges when it comes to managing their operational workflows efficiently and effectively at scale.

### After

Your team runs on six tools that don't talk to each other.

You already know that. What you may not know is how much of the week it costs you.

### Why the after works

- deletes the entire empty opening — "in today's fast-paced business environment" carries no information and no narrator can make it land;
- replaces a generic claim with one concrete image the listener can check against their own week;
- "You already know that" concedes rather than lectures, which changes the register from pitch to conversation;
- sets up the next line with a genuine question rather than a transition phrase.

---

## Pair CW-017 — Commercial: closing call to action

**Register:** commercial voice-over
**Audience:** end of a sixty-second spot
**Preserve:** badgr.dev/start

### Before

So if any of this sounds like something that might be useful for you and your team, then head over to badgr.dev/start today and get yourself signed up so you can begin your journey with us.

### After

If any of that sounded like your week — badgr.dev/start.

Ten minutes to set up. Today, ideally.

### Why the after works

- one conditional, one address; the original took twenty-eight words to say it;
- "your week" refers back to the concrete image rather than restating the offer abstractly;
- "Today, ideally" is a light push instead of "begin your journey", which a listener hears as filler;
- the URL sits before the final phrase, so the read does not end on an unfamiliar string.

---

## Pair CW-018 — Technical: retry and backoff behaviour

**Register:** technical explainer
**Audience:** integrating engineers
**Preserve:** 429, exponential backoff, Retry-After, idempotency key

### Before

When the API returns a 429 response the client should implement exponential backoff, and it should also respect the Retry-After header if one is present, and requests should include an idempotency key so that retried requests are not processed twice by the server.

### After

A 429 means you are being rate-limited, not that the request failed.

Back off exponentially. If a Retry-After header is present, it wins — use that value rather than your own.

Send an idempotency key on every request. Without one, a retry the server already processed becomes a second charge.

### Why the after works

- corrects the reader's likely mental model first, before giving instructions;
- "it wins" states the precedence rule that the original left implicit in "also respect";
- gives the consequence of skipping the idempotency key, which is what makes the instruction stick;
- three paragraphs, each one breath group, at a technical pace with room to slow at the exact terms;
- every protected term survives verbatim.

---

## Pair CW-019 — Technical: what a feature does not do

**Register:** technical explainer
**Audience:** security reviewers
**Preserve:** at rest, in transit, end-to-end encryption

### Before

Our platform encrypts all customer data at rest and in transit using industry-standard encryption, providing comprehensive protection for your sensitive information at every stage of its lifecycle.

### After

Data is encrypted at rest and in transit.

It is not end-to-end encryption. We hold the keys, which means we can decrypt your data — and so can anyone who compels us to.

If that boundary matters to your threat model, this is the paragraph to read twice.

### Why the after works

- states the limit rather than letting "comprehensive protection at every stage" imply something stronger than the truth;
- the second paragraph is the one a reviewer needs and the original omitted entirely;
- "read twice" is an explicit instruction to slow down — a narrator can act on it, where "sensitive information" gives no direction;
- keeps the claim accurate at the cost of sounding weaker, which is the correct trade.

---

## Pair CW-020 — Technical: migration warning

**Register:** technical explainer
**Audience:** operators running the upgrade
**Preserve:** must, before, v3.2, irreversible

### Before

Users should be aware that the migration to v3.2 will rewrite the schema and this is irreversible, so it is recommended that a backup is taken before proceeding with the upgrade process.

### After

The v3.2 migration rewrites the schema. It is irreversible.

You must take a verified backup before you start. Not a snapshot you assume exists — one you have restored from and checked.

### Why the after works

- "must" replaces "it is recommended that", restoring the strength the original quietly dropped;
- active voice puts the operator in the sentence: "you must take", not "a backup is taken";
- "verified" and the sentence explaining it close the gap between having a backup and having a backup that works;
- the short second sentence "It is irreversible" gets its own phrase, which is where the prominence belongs.

---

## Pair CW-021 — Technical: dense architecture paragraph

**Register:** technical explainer
**Audience:** engineers new to the codebase
**Preserve:** read replica, primary, replication lag

### Before

The implementation of the read replica configuration initialisation requires validation of all environment-specific connection parameter resolution conditions prior to the execution of any query routing logic against the primary.

### After

Reads go to a replica. Writes go to the primary.

Before routing anything, the service checks that the replica is actually reachable and that its replication lag is inside the limit. If either check fails, the read goes to the primary instead.

The cost of that fallback is load on the primary. The cost of skipping it is serving stale data.

### Why the after works

- opens with the rule in seven words, which the original never states at all;
- breaks a nine-word noun stack — "read replica configuration initialisation ... parameter resolution conditions" — into clauses with verbs, so prominences have somewhere to land;
- the closing pair names the trade-off, which is the part an engineer needs to remember;
- the original is close to unreadable aloud; the rewrite is three comfortable breath groups per paragraph.

---

## Pair CW-022 — Technical: permission boundary

**Register:** technical explainer
**Audience:** administrators
**Preserve:** read-only, audit log, cannot

### Before

The auditor role has been designed to provide read-only visibility into the system for compliance purposes and users assigned this role are able to view the audit log but they cannot make any modifications to system configuration.

### After

The auditor role is read-only.

It can see everything, including the audit log. It cannot change anything — not configuration, not users, not its own permissions.

That last one matters: an auditor cannot promote themselves.

### Why the after works

- the one-line opening is the whole rule; everything after it is elaboration;
- "not configuration, not users, not its own permissions" is a three-part list that builds to the one that matters, rather than the flat "any modifications to system configuration";
- the closing line states the security property the list implies, so the reader does not have to infer it;
- "cannot" is preserved and lands on a prominence in both places.

---

## Pair CW-023 — Professional introduction: conference bio

**Register:** professional introduction
**Audience:** event audience, read by a host

### Before

Anthony is a highly experienced technology professional with a diverse background spanning multiple industries and disciplines, and he has a proven track record of delivering innovative solutions to complex problems for organisations of all sizes.

### After

Anthony builds the unglamorous parts — the pipelines, the audit trails, the things that have to work at three in the morning.

He has done it for two-person teams and for companies with compliance departments. The problems turn out to be the same size.

### Why the after works

- replaces four unfalsifiable adjectives with one concrete image;
- "three in the morning" is the kind of detail a room reacts to; "proven track record" is not;
- the closing observation gives the host a line with a point to land on, rather than a list to get through;
- reads in about fifteen seconds at introduction pace, where the original runs long and flat.

---

## Pair CW-024 — Professional introduction: first thirty seconds of a call

**Register:** professional introduction
**Audience:** a prospective client, first meeting

### Before

Thanks so much for taking the time to speak with me today, I really appreciate it, so just to give you a bit of background about myself and what we do, I've been working in this space for about eight years now across a range of different sectors.

### After

Thanks for the time. I'll keep the background short.

Eight years building data systems, mostly in regulated industries. Which means I have opinions about audit logs, and I will try to keep them to myself.

So — what made you take this call?

### Why the after works

- "I'll keep the background short" then actually keeping it short earns credibility in two sentences;
- the aside is warm without being casual, which is the register a first call needs;
- ends by handing over, so the introduction does its actual job;
- the original spends forty-eight words before any information; the rewrite reaches the handover in forty-four with information in all of them.

---

## Pair CW-025 — Professional introduction: website about page, read aloud

**Register:** professional introduction
**Audience:** site visitors, voiced version of written copy

### Before

I am passionate about leveraging cutting-edge technology to drive meaningful outcomes and I thrive in fast-paced collaborative environments where I can utilise my skills to add value across the entire organisation.

### After

I like problems that have a right answer and a deadline.

Most of my work is making systems legible — to the people who run them, to the people who audit them, and to whoever inherits them next.

### Why the after works

- removes every word from the stock vocabulary: passionate, leveraging, cutting-edge, thrive, fast-paced, utilise, add value;
- the first line is a genuine preference, which is what the section is for;
- the three-part list ends on "inherits them next", the item with the most weight, so the sentence has a shape a narrator can build;
- written copy read aloud unchanged is the failure the delivery policy warns about; this version was written for the ear.

---

## Pair CW-026 — Professional introduction: panel self-introduction

**Register:** professional introduction
**Audience:** industry panel, sixty seconds each

### Before

Hi everyone, my name is Anthony and I'm the founder of BADGR Technologies where we focus on building tools and infrastructure for teams that need reliable systems, and I'm really excited to be here today to discuss this important topic with such a distinguished group of panellists.

### After

Anthony, BADGR Technologies. We build infrastructure for teams who get audited.

I'm here because I think we're about to disagree about observability, and I'd rather do that in public.

### Why the after works

- the name-and-company line is four words, which is all a panel introduction needs;
- "teams who get audited" is more specific than "teams that need reliable systems" and does the same work;
- naming the disagreement gives the moderator something to use and the audience a reason to keep listening;
- drops "excited to be here" and "distinguished group", which are the two phrases every other panellist will also say.

---

## Pair CW-027 — Professional introduction: handover to a colleague

**Register:** professional introduction
**Audience:** internal meeting

### Before

I'd now like to hand over to my colleague Priya who is going to walk us through the technical details of the implementation, and Priya has been working on this project for quite some time now so she knows it inside out.

### After

Priya has been on this for eight months. She found the bug none of us believed in.

Priya — the implementation.

### Why the after works

- gives one specific credential instead of the vague "quite some time" and "inside out";
- the second sentence is a genuine endorsement, which is what a handover is for;
- the final fragment is a clean transfer with no dead words, and the dash carries the break;
- shortens twelve seconds to five without losing anything the room needed.

---

## Pair CW-028 — Educational narration: explaining a mechanism

**Register:** educational narration
**Audience:** learners with no background
**Preserve:** hash function, one-way

### Before

A hash function is a mathematical algorithm that takes an input of arbitrary length and produces a fixed-length output known as a hash value or digest, and it is designed to be a one-way function meaning that it is computationally infeasible to reverse.

### After

A hash function turns any input — a word, a file, a whole library — into a short string of fixed length.

The useful part is that it only runs one way. Given the input, you can compute the string in an instant. Given the string, you cannot get back to the input.

That asymmetry is the whole idea. Everything a hash function is used for depends on it.

### Why the after works

- gives the shape of the thing before naming its properties;
- "a word, a file, a whole library" makes "arbitrary length" concrete in three beats;
- the two symmetrical sentences — given the input, given the string — put the contrast in parallel structure, which is where a narrator's contrastive prominence goes naturally;
- the closing paragraph tells the learner what to retain, which the original leaves them to work out.

---

## Pair CW-029 — Educational narration: correcting a common error

**Register:** educational narration
**Audience:** intermediate learners

### Before

It is a common misconception that correlation implies causation, however this is not the case, as two variables may be correlated due to the influence of a confounding third variable or purely by coincidence.

### After

Ice cream sales and drowning deaths rise together. Every summer, reliably.

Nobody thinks ice cream causes drowning. Something else moves both — it is hot, so more people buy ice cream, and more people swim.

That third thing has a name: a confounder. Looking for it is most of the work.

### Why the after works

- opens with the example rather than the rule, so the learner arrives at the correction themselves;
- withholds the term "confounder" until the concept is already understood, which is the reverse of the original;
- "Every summer, reliably" is a short second phrase that gives the narrator a place to sit before the turn;
- the closing line tells the learner what to do, not just what to avoid believing.

---

## Pair CW-030 — Educational narration: sequence of steps

**Register:** educational narration
**Audience:** learners following along
**Preserve:** commit, push, pull request

### Before

Once you have made your changes you will want to commit them to your local repository and then push that commit to the remote, after which you can open a pull request so that your changes can be reviewed by your team before being merged.

### After

Three moves, and they happen in three different places.

Commit saves your work to your own machine. Nothing has left your laptop yet.

Push sends it to the shared server. Now other people can see it, but nothing has changed for them.

A pull request asks for it to become part of the main line. That is the one that needs another human.

### Why the after works

- names the count up front, so the listener knows how much is coming;
- each step gets its own paragraph with a "what this does not do yet" clause — the part learners consistently get wrong;
- "That is the one that needs another human" is the practical distinction the original buries in a subordinate clause;
- one long sentence becomes seven short ones, each inside a comfortable breath group at teaching pace.

---

## Pair CW-031 — Educational narration: defining a boundary

**Register:** educational narration
**Audience:** learners meeting the term for the first time
**Preserve:** latency, throughput

### Before

Latency and throughput are two different performance metrics that are often confused with one another, where latency refers to the time taken for a single operation to complete while throughput refers to the number of operations that can be completed in a given time period.

### After

Latency is how long one thing takes. Throughput is how many things get done.

A wider motorway does not make your car faster. It moves more cars.

That is why a system can get slower for you while getting better overall — and why "we improved performance" is never a complete sentence.

### Why the after works

- the two definitions are the same length and the same shape, so the contrast is audible;
- the motorway image does the work of a paragraph of explanation in eleven words;
- the closing line gives the learner something to be sceptical about, which is more durable than a definition;
- both protected terms appear once each, early, where they can carry a prominence.

---

## Pair CW-032 — Educational narration: closing a lesson

**Register:** educational narration
**Audience:** end of a training module

### Before

So in summary, today we have covered a number of important topics including the fundamentals of the subject area, some practical applications, and we also looked at some of the common pitfalls that people encounter when they are getting started.

### After

Two things to keep from this.

One: the asymmetry is the point — easy one way, impossible the other.

Two: when someone claims a performance improvement, ask which metric.

Everything else you can look up.

### Why the after works

- replaces an inventory of topics with the two claims worth retaining;
- numbering gives the narrator two clear prominence peaks instead of one flat list;
- "Everything else you can look up" is honest and lowers the pressure to memorise;
- the original summary is the kind of paragraph a listener stops attending to; this one has content.

---

## Pair CW-033 — Reflective narration: holding an open question

**Register:** reflective narration
**Audience:** general-interest listeners

### Before

It must be acknowledged that these theories, while certainly valuable and worthy of continued documentation, cannot be regarded as conclusive at the present time, since the work of rational interpretation remains substantially incomplete.

### After

The theories are worth recording. They are not settled.

What is missing is not more evidence — it is the harder work of deciding what the evidence means.

That work is not finished. It may not be finishable in the way we would like.

### Why the after works

- keeps the original's caution exactly, without the hedging vocabulary that made it hard to say;
- "worth recording" and "not settled" are a two-part contrast in eight words, where the original took twenty-six;
- the final sentence adds the doubt the original gestures at with "at the present time" but never states;
- the pace fits reflective narration: short sentences with room between them, and no melodrama.

---

## Pair CW-034 — Reflective narration: describing a change of mind

**Register:** reflective narration
**Audience:** essay or long-form audio

### Before

Over the course of many years I gradually came to the realisation that my initial position on this matter had been substantially mistaken and that I had been giving insufficient weight to a number of considerations that I now regard as being of central importance.

### After

I was wrong about this for about a decade.

Not wrong in an interesting way — I simply was not counting the things that turned out to matter. They were in front of me. I had decided they were someone else's problem.

It is not a comfortable thing to describe.

### Why the after works

- says the thing plainly in the first line instead of arriving at it after forty words;
- "not wrong in an interesting way" refuses the flattering version of the admission;
- the three short sentences in the middle have decreasing length, which pulls the pace down naturally;
- the closing line does not resolve, which is what reflective narration is for.

---

## Pair CW-035 — Reflective narration: a scene

**Register:** reflective narration
**Audience:** long-form audio

### Before

I have a distinct recollection of standing in the kitchen of my grandmother's house on a particular afternoon and becoming aware, in a way that felt quite sudden, of the fact that the adults around me did not actually know what they were doing.

### After

My grandmother's kitchen. A weekday afternoon, nothing happening.

And then the thought, arriving all at once: none of them know either.

I was nine. It was not frightening. It was more like being handed something.

### Why the after works

- the fragments set a scene without a main verb, which slows the read the way the moment deserves;
- "none of them know either" is placed alone so the pause before it does the work that "in a way that felt quite sudden" was doing badly;
- three short sentences at the end, the last one incomplete in the right way;
- avoids the theatrical register — no dramatic pause is asked for, the sentence lengths supply it.

---

## Pair CW-036 — Reflective narration: qualifying a claim without weakening it

**Register:** reflective narration
**Audience:** general-interest listeners
**Preserve:** may, has not been shown

### Before

While the configuration may serve to reduce the overall risk profile in certain circumstances, it has not been shown to prevent the failure mode in question and should therefore not be relied upon as a sole mitigation.

### After

The configuration may reduce the risk. That is worth having.

But it has not been shown to prevent the failure. Not "rarely" — not shown. Those are different claims, and the difference is the whole reason for saying it slowly.

Do not let it be the only thing standing between you and the failure.

### Why the after works

- "may" and "has not been shown" both survive verbatim, and both land on a prominence;
- "Not 'rarely' — not shown" is contrastive focus doing exactly what the glossary describes: the alternative is named so the contrast is audible;
- the instruction to say it slowly is a direction a narrator can act on;
- the original's certainty is preserved precisely — neither raised nor lowered.

---

## Pair CW-037 — Reflective narration: ending without resolution

**Register:** reflective narration
**Audience:** close of a long-form piece

### Before

Ultimately, while it is clear that there is still a great deal more work to be done in this area, I remain fundamentally optimistic that we will eventually arrive at a fuller understanding of these matters in due course.

### After

There is more work here than I will finish.

I do not know whether that bothers me. Some days it reads as a failure. Most days it reads as the job.

Either way, tomorrow there is a paragraph to write.

### Why the after works

- replaces borrowed optimism with an honest uncertainty, which is more credible in this register;
- "Some days / most days" is a parallel pair that gives the narrator two matched prominences;
- the closing line is concrete and small, which lands better than "fuller understanding in due course";
- removes "ultimately", "fundamentally", and "in due course" — three words that ask a narrator to sound significant without giving them anything to be significant about.
