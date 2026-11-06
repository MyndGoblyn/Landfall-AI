# Catalog distribution validation — November 5, 2026

## Promotion decision

The initial R2 release uses the already reviewed catalog version
`oracle_cards:2026-07-29T21:02:49.097+00:00` rather than silently promoting a
new Scryfall snapshot. Reconstructing that snapshot from Scryfall produced
38,416 cards, and the fresh 18-deck execution matched every reviewed V2 top-five
list exactly (zero mismatches).

## Required gates

- 209 automated tests passed.
- The 14-case V2 benchmark passed with 1.0 candidate recall, precision, recall,
  and NDCG, with zero hard rejections or reasoning failures.
- Calibration reported `ready_for_controlled_promotion: true` and no regressed
  case IDs.
- All 18 real-deck fixtures passed snapshot integrity and input expectations.
- The negative controls retained their intended behavior: the 97-Mountain joke
  deck was not optimized, and incomplete Urza and Lathril inputs remained
  blocked.
- Cloudflare Worker type checking, frontend production build, and Wrangler dry
  run passed with the R2 binding.

## Resource measurements

- Uncompressed catalog: 37,029,485 bytes.
- Compressed immutable release: 7,107,842 bytes.
- Full local catalog load: about 2.5 seconds.
- Measured peak Python allocation for the newer 39,287-card snapshot: 170.8 MiB;
  retained catalog allocation: about 110 MiB. The validated snapshot is smaller.

## Staged newer snapshot

The November 5 Scryfall snapshot contains 39,287 cards. It passed the automated
benchmark, calibration, integrity, and negative-control gates, but changed seven
reviewed top-five portfolios. Those changes were inspected and remained legal
and plan-aligned, yet the snapshot is deliberately staged until its drift report
is promoted as a separate quality decision. Catalog transport and catalog
content therefore remain independently reversible.

## Subsequent promotion — November 6, 2026

The separate V3 reviewed real-deck run promoted the November 5 snapshot after
all 18 fixtures passed, including the four negative controls, and the changed
portfolios were accepted as legal and plan-aligned. The Phase 2 Commander Atlas
release then passed 235 backend tests, the frozen commander-profile benchmark,
frontend source smoke, production build, local desktop/mobile workflow QA, and
the Cloudflare deployment dry run.

The promoted immutable R2 release is
`440459be36e614aa597f507b0d15918a53224ba2a61ea0232a4db1caeccdc6cf`.
Its public manifest reports 39,287 cards and catalog version
`oracle_cards:2026-11-05T10:02:05.865+00:00`. The earlier July release and its
versioned manifest remain available for rollback.
