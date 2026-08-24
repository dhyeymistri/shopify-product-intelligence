# Shopify Product Intelligence

Audits ecommerce product data and reports — **with evidence** — whether that data is complete, consistent, structured, and useful enough for a human or an automated agent to understand, compare, and decide on the product.

**Core principle: never invent product facts.** If the data does not state something, the report says `UNKNOWN`, never "no".

**Status:** V0 specification. No implementation yet.

V0 is a local AI skill that reads a local catalog file and writes local reports. It is not a Shopify app, and it makes no network calls.

## Read this first

- [`AGENTS.md`](AGENTS.md) — operating contract, non-negotiables, phase gates
- [`product/PRD.md`](product/PRD.md) — customer, problem, use case, schemas, acceptance criteria
- [`product/rubric.md`](product/rubric.md) — the explainable 100-point scoring system
- [`product/taxonomy.md`](product/taxonomy.md) — the five categories and their attributes
- [`product/decisions.md`](product/decisions.md) — what was decided, why, and what was rejected

## What we do not claim

We do not claim this tool guarantees or predicts ranking, visibility, or citation in ChatGPT, Gemini, Google AI, or any other AI system. We evaluate the merchant's own product data — something we can inspect and prove.
