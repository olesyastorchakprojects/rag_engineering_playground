# Specification-First Approach

## What this document covers

This document explains the specification-first workflow used in the repository to design and generate implementation code and tests.

The core separation is simple:

- I write the specification
- the model generates code and tests from it
- the specification, not the generated code, is treated as the source of truth

---

## Core idea

The project is designed so that the main design work happens before implementation generation.

Instead of starting from code and documenting it afterward, I first make the system explicit through:

- contracts
- types
- rules
- interfaces
- ownership boundaries
- expected artifacts
- validation behavior

Only after that does the model generate code or tests.

This keeps design intent outside the model and makes generation more constrained and reproducible.

---

## Why this approach is used here

This repository contains multiple interacting layers:

- knowledge preparation
- ingest
- retrieval
- reranking
- generation
- request capture
- offline evals
- observability
- dashboard-facing outputs

Without explicit specifications, generated code can easily:

- invent implicit behavior
- blur stage boundaries
- couple modules that should stay separate
- generate tests that merely mirror implementation
- drift across runtime, eval, and observability surfaces

The specification-first approach is used to reduce that ambiguity.

---

## What counts as a specification in this project

In this repository, a specification is not a vague feature description.

It defines the system in operational terms, including:

- input and output types
- required fields and schema rules
- invariants
- stage responsibilities
- allowed configuration variants
- artifact formats
- naming rules
- error behavior
- observability requirements
- report and dashboard output expectations

A useful spec therefore describes not only what a component is for, but also what it may accept, produce, assume, and expose.

---

## What is specified before generation

Before code generation, the project tries to make four things explicit.

### Contracts
Contracts define the boundaries between stages and modules.

Examples include page and chunk artifacts, request capture, eval result tables, reports, and observability outputs.

### Types
Types define the shapes passed between stages so that pipeline behavior does not depend on hidden shared state or informal conventions.

### Rules
Rules define behavior that should not be left to interpretation, such as validation, retries, duplicate handling, stage promotion, metric emission, or semantic payload restrictions.

### Interfaces
Interfaces define how one subsystem may interact with another so the model does not invent extra couplings that were never intended.

---

## Why the specification is the source of truth

Generated code is useful, but it is not treated as the design authority.

The specification remains the source of truth because:

- generated code can vary more easily than design intent
- different generations should still implement the same rules
- tests should validate the contract, not only the current implementation
- documentation, telemetry, and dashboards should stay aligned with the same definitions

Without that separation, the project would drift back into implementation-first behavior.

---

## What the model is expected to do

In this workflow, the model is not asked to invent system behavior.

It is asked to implement already-declared behavior.

Its role is to:

- generate code from explicit contracts
- generate tests from explicit rules and expected outputs
- preserve stage boundaries
- preserve naming and schema conventions
- avoid introducing behavior that is not grounded in the specification

The model acts here as an implementation accelerator, not as the primary designer of the system.

---

## What this improves

This approach improves four things.

### 1. Less ambiguity in generation
The more explicit the contracts and rules are, the less room there is for model improvisation.

### 2. Easier review
Review becomes simpler because the main question is: **Does this implementation satisfy the spec?**

### 3. More meaningful tests
Tests generated from explicit contracts can validate schema conformance, stage outputs, invariants, deterministic behavior, and failure paths.

### 4. Less cross-layer drift
The same specification mindset is used not only for code modules, but also for observability, eval artifacts, and dashboard-facing outputs.

---

## What this does not mean

Specification-first does not mean that the project is fixed forever or that the first spec is perfect.

It does not remove iteration, and it does not eliminate the need for code review.

It changes where iteration happens:

- refine the specification
- regenerate or adjust implementation against it

That is different from repeatedly patching generated code while keeping the contract implicit.

---

## How this shapes the repository

This approach is one reason the repository is split across several engineering surfaces:

- execution
- specification
- measurement
- evidence
- documentation

That split reflects a deliberate separation between:

- what the system is supposed to do
- how it is implemented
- how it is measured
- what evidence it produces
- how it is explained

The specification layer exists to keep those surfaces aligned.

---

## Why this matters in this project

This workflow is especially important in parts of the repository where silent drift would be costly:

- runtime stage boundaries
- request capture shape
- eval stage sequencing
- result-table structure
- report contracts
- observability spans and metrics
- Grafana-facing outputs

In these areas, implementation convenience is not a good substitute for explicit design.

---

## Summary

In this project, specification-first means that the primary design work happens in contracts, types, rules, and interfaces before code generation begins.

I write the specification.
The model generates code and tests from it.

This separation is used to make generation more explicit, less ambiguous, more reproducible, and easier to review.