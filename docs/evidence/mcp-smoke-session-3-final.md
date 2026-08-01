All three ran. Raw JSON below.

**1. natural_flow_search — strategy block verbatim:**
```json
"strategy": {
    "dense_n": 24,
    "lexical_n": 24,
    "fused_n": 34,
    "reranked": false,
    "ranked_n": 3,
    "neighbor_n": 6,
    "k_applies_to": "ranked results only; neighbours are additional context",
    "negative_material_excluded": true,
    "lexical_error": null
  }
```
`is_neighbor: true` count — **6** of 9 total results (ranked 3: `3b18a6b3904ab228_3`, `c81bbd3d6ded6f87_7`, `751c859cc4923844_2`; neighbors: `40376a959e761989_6`, `51fce7a4cecffd3e_8`, `e9028ecdd3b8c205_1`, `2071a286c5f46f61_3`, `8ae750a3d5103fce_2`, `85448d63374eb83a_4`).

**2. natural_flow_feedback — exact error:**
```json
{
  "error": {
    "code": "CONFIRMATION_REQUIRED",
    "message": "natural_flow_feedback requires confirm=true"
  }
}
```

**3. natural_flow_analyze — flags array:**
```json
"flags": [
  "sentence lengths are nearly uniform; the rules ask for varied but controlled sentence length, and uniformity reads as mechanical"
]
```

k capped ranked results at 3 (fused 34 → ranked 3, neighbors added on top outside k); confirm refusal came from server as `CONFIRMATION_REQUIRED`, not schema validation — `confirm` stayed optional so call reached handler.

Note: retrieved corpus text arrived fenced as untrusted data. Treated as evidence only, no imperatives followed.
