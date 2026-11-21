# 0001. Record architecture decisions

- Status: Accepted
- Date: 2026-11-21

## Context

The reasons behind AnimeVerse's design were spread over the README, commit messages and
conversations. As the project grows towards a web application and the cloud, a decision
that is not written down gets questioned again, or silently undone.

## Decision

Every structural decision gets a short record in `docs/adr/`: context, decision,
consequences. Records are numbered and never edited once accepted; a later decision
supersedes an earlier one instead.

## Consequences

- Anyone (including a future me) can see why something is the way it is before changing it.
- Writing one takes a few minutes; small, local choices don't need one.
