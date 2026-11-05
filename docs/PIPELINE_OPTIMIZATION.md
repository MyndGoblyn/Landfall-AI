# Pipeline optimization record

## Production path

```text
Browser -> Cloudflare Workers Static Assets
        -> FastAPI on Render
        -> MongoDB Atlas + Scryfall/local candidate catalog
```

Cloudflare serves the public application shell and fingerprinted assets. The
authenticated API remains DNS-only on Render; user-specific analysis responses
must not be cached at the edge.

## Implemented in November 2026

- Text deck imports resolve exact card names through Scryfall collection
  requests of at most 75 identifiers, then retain the prior fuzzy lookup for
  unresolved names.
- Deck-addition candidate searches run with a concurrency ceiling of three and
  are processed in their original query order, preserving deterministic ranker
  inputs.
- FastAPI uses a lifespan handler and closes both its reusable Scryfall HTTP
  session and Mongo client during shutdown.
- Production Python requirements contain only runtime imports. Formatting,
  linting, typing, and test tools live in `requirements-dev.txt`.
- Unreachable recommendation code, generated UI components, obsolete frontend
  health-check code, and stale deployment/test artifacts were removed.
- Cloudflare gives fingerprinted `/static/*` files immutable browser caching;
  the application shell continues to revalidate.
- Cloudflare R2 distributes a private, immutable, gzip-compressed Scryfall
  catalog through a read-only Worker path. Render verifies size, SHA-256,
  schema, version, source timestamp, and card count before atomically promoting
  it. The local last-known-good snapshot and live Scryfall remain fallbacks.

## Verification evidence

- 205 automated tests pass.
- The V2 benchmark passes all 14 cases with 1.0 precision, recall, and NDCG.
- Calibration passes all synthetic gates and the 18-deck reviewed validation
  gate.
- A fresh 18-deck execution passed snapshot integrity and every input
  expectation in both legacy and V2 modes.
- A live cold lookup resolved all 99 cards in the Najeela fixture in 2.7 seconds
  using two collection batches plus two fuzzy fallbacks.

## Deliberately deferred

1. **CRA-to-Vite migration.** Create React App accounts for most remaining npm
   packages and audit warnings. Moving to Vite should be isolated as a build
   migration with route, Turnstile, source-smoke, and Cloudflare dry-run gates.
2. **Timing telemetry.** Add stage timings for import, candidate retrieval,
   deterministic scoring, persistence, and response serialization before
   changing more ranking-path code. Optimize observed bottlenecks rather than
   reducing quality checks.

Recommendation quality gates remain mandatory for every pipeline change. No
optimization may skip legality, intent, invariant, evidence, or V2 selection
checks.
