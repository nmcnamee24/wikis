# Step 02 Seed Graph Usage

## Purpose

This step turns generated card JSON files into a local graph that the iOS prototype can load.

Input:

```text
data/cards/*.json
```

Output:

```text
data/graph/seed_graph.json
```

## Run

```bash
python3 scripts/build_seed_graph.py
```

## Validate

```bash
python3 scripts/validate_seed_graph.py
```

## Graph Shape

The graph contains:

- `topics`: approved prototype topic cards
- `edges`: typed graph connections
- `gestureIndex`: direct down/right/left candidates by topic
- `starterPool`: topics suitable for first app sessions
- `candidateQueue`: unmapped Wikipedia topics discovered from lead-section links
- `stats`: validation and coverage summary

## Gesture Mapping

```text
down  -> deeper / prerequisite
right -> neighbor / contrast / person / place
left  -> teleport
```

## Current Scope

This is a seed graph built from 100 prototype-pass generated cards. The Step 02 target is 100 to 300 topics before the app is production-ready, so the current graph is usable for the next prototype step.

The important proof here is that every topic can produce a valid gesture path without depending on live generation.
