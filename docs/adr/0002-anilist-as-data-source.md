# 0002. AniList as the data source

- Status: Accepted
- Date: 2026-11-16 (recorded 2026-11-21)

## Context

The project needs a free public anime API with enough records, terms that allow this use,
and documented rate limits. The first choice, Jikan (an unofficial MyAnimeList API, REST),
was unreachable on 2026-11-16, and its API was still not answering on 2026-11-19.

## Decision

Use the AniList GraphQL API (`https://graphql.anilist.co`), without an account or key.

- It is free for non-commercial use.
- Its rate limit is documented and also sent in every response (`X-RateLimit-Limit`),
  so the client follows the real limit instead of a guess.
- GraphQL lets one request per franchise ask for exactly the fields that are stored.
- It reports the MyAnimeList id (`idMal`), kept as `anime.mal_id` for compatibility.

## Consequences

- AniList's quirks must be handled: HTML inside "plain text" descriptions, a loose search
  that returns unrelated anime, `total`/`lastPage` that can't be trusted, a degraded limit
  of 30 requests per minute.
- AniList's terms forbid mass collection, so the import stays limited to a fixed list of
  franchises.
- The source sits behind the `AnimeSource` port (see 0003): another API can be added as a
  new adapter without touching the use case.
