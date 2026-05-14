# ThinAI

A research project building an AI system that learns to play arbitrary turn-based games from natural-language rule specifications, retains learned games without catastrophic forgetting, and accepts corrections that propagate into its rule and strategy models.

Everything runs on a single laptop. No cloud APIs, no pre-trained foundation models, no LLM dependencies.

**[Read the full research manifesto](thinai.html)**

## Status

**Phase 3 — Corrections & Refinement**

| What | Status |
|------|--------|
| Games playable | 6 (Tic-Tac-Toe, Connect Four, Mancala, Reversi, Nim, Chutes & Ladders) |
| Test suite | 287 tests passing |
| Training | Learns from scratch against competent opponents |
| Retention | Per-game memory, no catastrophic forgetting |
| Corrections | Detection, diagnosis, rule revision, confidence tracking |
| Web demo | Play, train, and inspect learned weights in the browser |

## Quick Start

### Backend (Python)

```bash
# Install dependencies
pip install fastapi uvicorn lark

# Run tests
python3 -m pytest engine/tests/

# Start the API server
python3 -m uvicorn engine.api:app --port 8000
```

### Frontend (React)

```bash
cd web
npm install
npm run dev -- --port 5173
```

Open http://localhost:5173 to play games and train the AI.

### Benchmarks

```bash
# Train and evaluate all games
python3 scripts/benchmark.py

# Test retention across sequential learning
python3 scripts/retention_bench.py
```

## Project Structure

```
engine/
  engine.py          Game engine — loads GDL, generates moves, applies rules
  gdl/               Game Description Language — board, state, expression eval
  games/examples/    Game definitions (JSON): tictactoe, connect_four, mancala, etc.
  reasoner/          Minimax + alpha-beta search, learnable evaluation, features
  training/          Learning runner, opponents, weight updates
  memory/            Persistent per-game knowledge storage
  corrections/       Rule confidence, fault diagnosis, revision (Phase 3)
  parser/            Constrained-English rule parser (in progress)
  api.py             FastAPI server for the web demo

web/
  src/App.jsx        React frontend — play, train, inspect
  src/TrainingDashboard.jsx

scripts/
  benchmark.py       Train + evaluate all games, save results as JSON
  retention_bench.py Sequential training with retention verification

design.md            GDL schema spec, architecture decisions, worked examples
dev-plan.md          Full implementation roadmap (Phases 0-8)
thinai.html          Landing page / research manifesto
```

## How It Works

**Game Description Language (GDL):** Games are defined as declarative JSON specs — board structure, pieces, rules (conditions + effects), and end conditions. See `engine/games/examples/` for examples.

**Learning:** The system starts with zero strategic knowledge. It plays games against a competent minimax opponent and adjusts evaluation weights after each game — features present in winning positions are reinforced, losing positions are penalized. Over dozens of games, it discovers which board features matter.

**Retention:** Each game's learned knowledge (evaluation weights) is stored in an isolated JSON file. Learning a new game cannot interfere with previously learned games.

**Corrections (Phase 3):** Rules carry confidence scores that update through play. When something unexpected happens (illegal move, outcome surprise, user feedback), the system diagnoses which rule is at fault and proposes revisions.

## Design Documents

- **[design.md](design.md)** — GDL schema specification, expression language, architecture
- **[dev-plan.md](dev-plan.md)** — Full research plan, benchmark design, evaluation strategy, all 8 phases

## Requirements

- Python 3.9+
- Node.js 18+ (for the web frontend)
- No GPU required
- No internet required at runtime
