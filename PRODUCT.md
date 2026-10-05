# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, held equally:
1. SME process/operations managers using the dashboard as a real analysis tool for their own event logs.
2. The academic jury and internship supervisor (stage de fin d'annee, EMSI) evaluating the platform as the centerpiece of a rapport de stage.

The dashboard must read as a credible business tool first — the presentation context raises the craft bar, it does not turn this into a marketing page.

## Product Purpose

A process-mining platform for SMEs. From a raw event log it: discovers the real process (Inductive Miner), checks how well real cases follow that model (fitness/precision, token-based replay), measures performance (bottlenecks, wait times between activities, rework rate, resource load), translates those measures into business KPIs and recommendations, predicts per-case delay risk and remaining time to close (two XGBoost models), and synthesizes all of it into one Process Health Score (0-100) readable without process-mining expertise.

## Positioning

The analysis core (`src/process_metrics.py`) reasons in generic terms — "case", "activity", "timestamp" — never in a dataset's literal column names. A YAML config maps those concepts to a given log's real columns. This is what a competing one-off script over a single dataset could not truthfully claim: point it at a different event log with a new config file and the same pipeline runs.

## Evidence on Hand

Validated experimentally on BPI Challenge 2019 (van Dongen, 4TU.ResearchData, CC BY 4.0): a Purchase-to-Pay process (request -> order -> receipt -> invoice -> payment) from a paint/coatings multinational, ~249,000 cases, ~1.46M events after cleaning. Used to demonstrate and validate the platform — not presented as data from a real SME.

Real computed results, safe to display as-is:
- Classifier (delay risk): ROC AUC 0.878, accuracy 83.6%, recall on late cases 71.8%.
- Regressor (remaining time): MAE 17.4 days, 37.9% better than a naive median-based prediction.
- Conformance, performance, and rework figures are computed per-run from the log, not fixed numbers — the UI must keep presenting them as live computed output, never hardcode the current run's values as permanent copy.

No user testimonials, customer logos, or case studies exist. Do not fabricate any.

## Capabilities and Constraints

Five dashboard views: Overview, Process, Conformance & Performance, Prediction, Recommendations.

- Single-container deployment: FastAPI serves the built React app and the JSON API (`/api/*`) from the same process — no CORS, no separate frontend host.
- Models (`process_model.pnml`, `xgboost_classifier.pkl`, `xgboost_regressor.pkl`) are trained offline and mounted as volumes; the container only loads and serves them.
- pm4py is AGPL v3 (since 2024): a closed-source commercial use of this platform would need a paid license. Noted, not a UI concern.
- Prediction view searches server-side over ~60k case IDs (no client-side full list).

## Brand Commitments

Product name "Process Mining PME" is kept. Company logo "NeoMorIT" (`frontend/src/assets/neomorit-logo.jpg` — navy-to-blue gradient shield monogram, "M/T" mark) must appear in the dashboard (header/footer credit), and its blue identity (navy #14205c to bright blue #3da9fc range) is a binding constraint: whichever visual world is chosen must incorporate or harmonize with this blue as an accent, not fight it. Typography and the rest of the visual system are otherwise open.

## Product Principles

1. Reads as a real operating tool for a process/ops manager, not a portfolio piece wearing a dashboard costume.
2. Every number on screen traces to a real computation on the log in use — no invented metrics, testimonials, or customer evidence.
3. The Process Health Score is the one artifact a non-expert must understand at a glance; the other four views can reward closer reading.
4. Messaging and visuals must not imply BPI2019 is a real SME's private data — it is the public validation dataset.
5. The single-container, offline-trained-models architecture is a deliberate simplicity choice to preserve, not a gap to design around.
