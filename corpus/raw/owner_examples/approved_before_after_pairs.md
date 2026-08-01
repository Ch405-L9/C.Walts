# Approved Before/After Seed Pairs
## Market-facing natural-language and voice-delivery examples

**Status:** approved seed set  
**Use:** textual ingestion and retrieval evaluation  
**Important:** These examples teach market-facing spoken clarity. They do not attempt to clone the owner's personal speaking style.

---

## Pair CW-001 — Technical security explainer

**Register:** technical explainer  
**Audience:** administrators and developers  
**Preserve:** domain-wide authority, service account, impersonation, OAuth scopes, Admin console, principle of least privilege

### Before

When you delegate domain-wide authority, you are not granting the service account direct access to all user data, instead you are authorizing it to impersonate specific users when making API calls, access is on behalf of a user, your application must specify which user to impersonate for each API request and the application then acts with the permissions of that specific user and not with elevated or domain-wide privileges.

### After

Domain-wide authority does **not** give a service account unrestricted access to every user's data.

It allows the service account to impersonate a specific user when it makes an API request. The application must name that user for each request. It then operates with that user's permissions and only the OAuth scopes approved in the Admin console.

That is the boundary: the service account cannot access data the impersonated user cannot access. This is the principle of least privilege.

### Why the after works

- leads with the security boundary;
- uses short, meaning-based units;
- separates what the feature does from what it does not do;
- preserves every technical term;
- creates natural emphasis points.

---

## Pair CW-002 — Professional introduction

**Register:** professional brand introduction  
**Audience:** prospective clients and partners

### Before

I help teams turn complex ideas into clear practical solutions and I like building systems that feel fast reliable and easy to use whether I am designing a workflow refining a product or solving a technical problem I focus on clarity confidence and strong execution from start to finish.

### After

I help teams turn complex ideas into clear, practical solutions.

Whether I'm designing a workflow, refining a product, or solving a technical problem, I focus on the same three things: clarity, confidence, and strong execution from start to finish.

The result is a system that feels fast, reliable, and easy to use.

### Why the after works

- removes the run-on cadence;
- introduces a clear three-part emphasis;
- saves the outcome for a clean final line;
- fits a confident professional read.

---

## Pair CW-003 — Reflective scholarly narration

**Register:** reflective narration  
**Audience:** general-interest listeners  
**Source status:** transcript-derived; provenance must be verified before production reuse

### Before

With regard to the Wisdom of Solomon the time of theories is past they must still be chronicled but they are never final all that remains is to secure a rational exegesis for which much has yet to be done.

### After

With regard to the *Wisdom of Solomon*, the time of theories is past.

Those theories should still be recorded, but none of them is final. What remains is the harder task: establishing a rational exegesis. And much work is still left to do.

### Why the after works

- preserves the reflective register;
- gives the contrast room to land;
- varies sentence length;
- avoids artificial drama.

---

## Pair CW-004 — Product explainer opening

**Register:** commercial explainer  
**Audience:** mobile readers  
**Product facts:** must be checked against the current product build before external publication

### Before

BADGR Bolt uses RSVP and ORP technology and it shows words in a way that helps keep your eyes still and you can change the speed and use quizzes to see what you remember.

### After

Still chasing every line across the screen?

BADGR Bolt keeps the words centered, highlights the optimal recognition point, and lets you control the pace. When you finish a chapter, an optional quiz can help you check what actually stuck.

Read with less visual movement. Adjust the speed. Keep more of what you read.

### Why the after works

- begins with a recognizable problem;
- explains the mechanism without a technical lecture;
- turns features into listener benefits;
- uses a three-beat closing cadence.

---

## Pair CW-005 — Technical warning

**Register:** calm technical warning  
**Audience:** system owner

### Before

This is important because the database permissions are currently world writable and that could allow another local process to change the file and it should be fixed before the system is treated as secure.

### After

The database is currently world-writable. That means another local process could modify it.

Correct the permissions before treating this installation as secure.

### Why the after works

- states the condition;
- states the consequence;
- states the required action;
- avoids panic and filler.

---

## Pair CW-006 — Setup instruction

**Register:** spoken tutorial  
**Audience:** technical user

### Before

You need to first open the terminal and after that go to the project directory and then activate the virtual environment before you run the health check command so it uses the correct dependencies.

### After

Open a terminal and move into the project directory.

Activate the project's virtual environment, then run the health check. That ensures the command uses the correct dependencies.

### Why the after works

- removes repeated transition words;
- explains the reason after the action;
- creates two easy spoken steps.

---

## Pair CW-007 — Feature explanation

**Register:** product demonstration  
**Audience:** prospective user

### Before

The reading speed is adjustable which means you do not necessarily have to speed read because you can use 250 words per minute and increase it later as you become more comfortable.

### After

You don't have to start fast.

Set the reader to a comfortable pace, even 250 words per minute, and increase it when you're ready. The speed adapts to you, not the other way around.

### Why the after works

- opens with reassurance;
- preserves the exact number;
- ends on a memorable contrast.

---

## Pair CW-008 — Service offer

**Register:** small-business promotional voice-over  
**Audience:** startups and small businesses  
**Claims:** confirm current offer before publication

### Before

BADGRTechnologies LLC also offers full-stack web development design optimization and hosting and small businesses and startups under two years old receive a discount on one service.

### After

Need a faster, clearer, more reliable website?

BADGRTechnologies LLC provides full-stack development, design optimization, and hosting. Qualifying small businesses and startups under two years old can receive a discount on one service.

### Why the after works

- leads with the customer problem;
- presents services in one clean unit;
- keeps the qualification attached to the offer;
- avoids exaggerated sales language.

---

## Pair CW-009 — Educational explanation

**Register:** e-learning narration  
**Audience:** learners

### Before

Retrieval augmented generation works by taking a question and searching a collection for relevant chunks and then giving those chunks to the model so it can answer using that information.

### After

Retrieval-augmented generation has two main steps.

First, the system searches its collection for passages related to the question. Then it gives the most relevant passages to the model as evidence for the answer.

The model still needs rules, evaluation, and source controls. Retrieval alone does not guarantee correctness.

### Why the after works

- organizes the concept into two steps;
- distinguishes evidence from correctness;
- introduces a meaningful final caution.

---

## Pair CW-010 — Call to action

**Register:** short commercial CTA  
**Audience:** mobile viewers

### Before

Click the link and download the app so you can try it and see if it works for you.

### After

Try BADGR Bolt and set the pace that works for you. Open the link to get started.

### Why the after works

- gives a concrete benefit before the action;
- removes hesitant wording;
- remains direct without shouting.

---

## Pair CW-011 — Voice-selection explanation

**Register:** production guidance  
**Audience:** content producer

### Before

The voice settings matter but you can keep changing the settings and still not get the right sound if the voice itself is not right for the content.

### After

Start with the voice, not the sliders.

A voice that fits the message will usually outperform a mismatched voice with aggressive settings. Choose the right delivery first, then make small adjustments.

### Why the after works

- leads with the operating rule;
- gives the reason;
- ends with a practical sequence.

---

## Pair CW-012 — Honest build status

**Register:** executive technical status  
**Audience:** project owner

### Before

The framework is mostly complete and all the tests passed but it is not actually usable yet because there is no corpus and the MCP is not registered and no end to end test has been done.

### After

The framework is built, and the unit tests pass. The capability is not active yet.

Three items remain: populate the corpus, register the project MCP server, and pass an end-to-end retrieval test from a fresh session.

### Why the after works

- separates progress from readiness;
- names the remaining work;
- avoids overstating completion.
