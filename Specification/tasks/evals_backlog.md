# Evals Backlog

This document tracks follow-up work for the eval subsystem that is intentionally out of scope for the current implementation wave.

## Planned Follow-Up

- The eval engine should write selected derived eval aggregates and metrics back into Phoenix traces so that trace inspection can show not only runtime spans, but also downstream eval outcomes and summary metrics for the same request or run.
