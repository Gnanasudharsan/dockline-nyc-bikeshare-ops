# 0001. Record architecture decisions

- Status: Accepted
- Date: 2026-11-06

## Context
Dockline spans ingestion, a warehouse, transformation, a semantic layer, three
consumption surfaces, and deployment. Choices made early (and why) are easy to forget
and hard to defend later without a written record.

## Decision
Keep lightweight ADRs in `docs/adr/`, one file per decision, numbered sequentially.
Each states context, decision, and consequences in under a page.

## Consequences
Reviewers and future sessions can see why the system looks the way it does. ADRs are
never edited after acceptance except to mark them superseded.
