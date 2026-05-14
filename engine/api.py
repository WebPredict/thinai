"""FastAPI server for ThinAI game engine.

Provides a REST API for the React frontend to interact with games,
run training sessions, and inspect learned knowledge.
"""

from __future__ import annotations
import os
import json
import threading
import random
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from engine.engine import GameEngine
from engine.gdl.state import GameState, Move, GameResult
from engine.gdl.board import GridSpace
from engine.reasoner.reasoner import Reasoner
from engine.reasoner.evaluator import LearnableEval
from engine.training.learner import LearningRunner, LearningResults
from engine.training.opponents import RandomOpponent
from engine.memory.store import MemoryStore
from engine.corrections.handler import CorrectionHandler

# --- Rate Limiting ---
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="ThinAI Game Engine API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS ---
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- State ---

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "games", "examples")
_sessions: dict[str, dict] = {}
_training_runs: dict[str, dict] = {}
_memory_store = MemoryStore()
_training_counter = 0


def _load_engine(game_name: str) -> GameEngine:
    path = os.path.join(EXAMPLES_DIR, f"{game_name}.json")
    if not os.path.exists(path):
        raise HTTPException(404, f"Game not found: {game_name}")
    return GameEngine.from_file(path)


def _state_to_dict(state: GameState, engine: GameEngine) -> dict:
    """Serialize game state for the frontend."""
    board = state.board
    board_type = "grid" if hasattr(board, "rows") else "track"

    spaces = {}
    for space_key, piece_or_list in state.pieces.items():
        key = f"{space_key.row},{space_key.col}" if hasattr(space_key, "row") else str(space_key.index)
        if isinstance(piece_or_list, list):
            spaces[key] = [{"name": p.name, "owner": p.owner} for p in piece_or_list]
        else:
            spaces[key] = {"name": piece_or_list.name, "owner": piece_or_list.owner}

    legal_moves = []
    result = engine.check_terminal(state)
    if result is None:
        for m in engine.legal_moves(state):
            move_dict = {"rule": m.rule_name, "params": {}}
            for k, v in m.params.items():
                if hasattr(v, "row"):
                    move_dict["params"][k] = {"row": v.row, "col": v.col}
                elif hasattr(v, "index"):
                    move_dict["params"][k] = {"index": v.index}
                else:
                    move_dict["params"][k] = v
            legal_moves.append(move_dict)

    game_result = None
    if result:
        game_result = {"type": result.result_type, "winner": result.winner}

    return {
        "board_type": board_type,
        "rows": getattr(board, "rows", None),
        "cols": getattr(board, "cols", None),
        "track_length": getattr(board, "length", None),
        "spaces": spaces,
        "current_player": state.current_player,
        "turn_number": state.turn_number,
        "legal_moves": legal_moves,
        "game_result": game_result,
    }


# --- API Models ---

class NewGameRequest(BaseModel):
    game: str
    ai_player: Optional[str] = "player2"
    ai_depth: int = 4
    use_learned: bool = True


class MoveRequest(BaseModel):
    rule: str
    params: dict


class TrainingRequest(BaseModel):
    game: str
    num_games: int = 50
    depth: int = 3
    fresh: bool = False


# --- Game Endpoints ---

@app.get("/api/games")
@limiter.limit("60/minute")
def list_games(request: Request):
    games = []
    for f in os.listdir(EXAMPLES_DIR):
        if f.endswith(".json"):
            games.append(f.replace(".json", ""))
    return {"games": sorted(games)}


@app.post("/api/game/new")
@limiter.limit("30/minute")
def new_game(request: Request, req: NewGameRequest):
    engine = _load_engine(req.game)
    state = engine.initial_state()
    session_id = f"{req.game}_{len(_sessions)}"

    # Try to load learned evaluator
    eval_fn = None
    if req.use_learned:
        evaluator = _memory_store.load(engine.meta["name"])
        if evaluator:
            eval_fn = evaluator

    _sessions[session_id] = {
        "engine": engine,
        "state": state,
        "ai_player": req.ai_player,
        "ai_depth": req.ai_depth,
        "game_name": req.game,
        "eval_fn": eval_fn,
        "correction_handler": CorrectionHandler(engine.gdl),
    }

    return {
        "session_id": session_id,
        "state": _state_to_dict(state, engine),
        "using_learned": eval_fn is not None,
    }


@app.post("/api/game/{session_id}/move")
@limiter.limit("120/minute")
def make_move(request: Request, session_id: str, req: MoveRequest):
    """Apply the player's move only. Returns intermediate state (before AI plays)."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    engine = session["engine"]
    state = session["state"]

    params = {}
    for k, v in req.params.items():
        if isinstance(v, dict) and "row" in v:
            params[k] = GridSpace(v["row"], v["col"])
        elif isinstance(v, dict) and "index" in v:
            from engine.gdl.board import TrackSpace
            params[k] = TrackSpace(v["index"])
        else:
            params[k] = v

    move = Move(req.rule, params)
    state = engine.apply_move(state, move)
    session["state"] = state

    handler = session.get("correction_handler")
    if handler:
        handler.on_successful_move(state, move)

    result = engine.check_terminal(state)
    if result and handler:
        handler.on_game_end(state, result)

    # Check if it's now the AI's turn
    needs_ai = (not result) and state.current_player == session["ai_player"]

    return {"state": _state_to_dict(state, engine), "needs_ai": needs_ai}


@app.post("/api/game/{session_id}/ai-move")
@limiter.limit("120/minute")
def ai_move(request: Request, session_id: str):
    """Let the AI play its turn. Called separately so the frontend can show a pause."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    engine = session["engine"]
    state = session["state"]

    # For chance games (like Chutes & Ladders), AI rolls randomly
    is_chance = any(r.get("chance") for r in engine.gdl.get("rules", []))
    if is_chance:
        ai_moves = engine.legal_moves(state)
        move = random.choice(ai_moves) if ai_moves else None
    else:
        from engine.metacognition.effort import EffortAllocator
        from engine.metacognition.confidence import DecisionConfidenceTracker
        allocator = session.get("effort_allocator") or EffortAllocator()
        conf_tracker = session.get("confidence_tracker") or DecisionConfidenceTracker()
        reasoner = Reasoner(engine, max_depth=session["ai_depth"],
                           eval_fn=session.get("eval_fn"),
                           effort_allocator=allocator,
                           confidence_tracker=conf_tracker)
        move = reasoner.choose_move(state)
        # Store for future moves in this session
        session["effort_allocator"] = allocator
        session["confidence_tracker"] = conf_tracker

    ai_move_info = None
    ai_confidence = None
    ai_effort = None
    if move:
        ai_move_info = {}
        for k, v in move.params.items():
            if hasattr(v, "row"):
                ai_move_info[k] = {"row": v.row, "col": v.col}
            elif hasattr(v, "index"):
                ai_move_info[k] = {"index": v.index}
            else:
                ai_move_info[k] = v
        state = engine.apply_move(state, move)
        session["state"] = state

        # Capture metacognition info (only for non-chance games)
        if not is_chance and 'reasoner' in dir():
            if hasattr(reasoner, 'last_confidence') and reasoner.last_confidence:
                ai_confidence = reasoner.last_confidence.to_dict()
            if hasattr(reasoner, 'last_effort_reason'):
                ai_effort = {
                    "depth_used": reasoner.last_depth_used,
                    "nodes_searched": reasoner.nodes_searched,
                    "reason": reasoner.last_effort_reason,
                }

    handler = session.get("correction_handler")
    result = engine.check_terminal(state)
    if result and handler:
        handler.on_game_end(state, result)

    return {
        "state": _state_to_dict(state, engine),
        "ai_move": ai_move_info,
        "ai_confidence": ai_confidence,
        "ai_effort": ai_effort,
    }


@app.get("/api/game/{session_id}/corrections")
def get_corrections(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    handler = session.get("correction_handler")
    if not handler:
        return {"corrections": None}
    return handler.summary()


class CorrectionRequest(BaseModel):
    feedback: str


@app.post("/api/game/{session_id}/correct")
def submit_correction(session_id: str, req: CorrectionRequest):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    handler = session.get("correction_handler")
    if not handler:
        raise HTTPException(400, "No correction handler")
    diagnosis = handler.on_explicit_correction(session["state"], req.feedback)
    return {
        "correction_applied": handler.corrections_applied > 0,
        "diagnosis": diagnosis.to_dict() if diagnosis else None,
        "summary": handler.summary(),
    }


@app.get("/api/game/{session_id}")
def get_state(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"state": _state_to_dict(session["state"], session["engine"])}


# --- Training Endpoints ---

@app.post("/api/training/start")
@limiter.limit("5/minute")
def start_training(request: Request, req: TrainingRequest):
    global _training_counter
    _training_counter += 1
    training_id = f"train_{_training_counter}"

    engine = _load_engine(req.game)
    game_name = engine.meta["name"]

    # Load existing weights or start fresh
    evaluator = None
    if not req.fresh:
        evaluator = _memory_store.load(game_name)
    if evaluator is None:
        evaluator = LearnableEval(game_name)

    run_state = {
        "status": "running",
        "game": req.game,
        "game_name": game_name,
        "num_games": req.num_games,
        "depth": req.depth,
        "games_played": 0,
        "results": None,
        "snapshots": [],
        "evaluator": evaluator,
    }
    _training_runs[training_id] = run_state

    # Metacognition components for training
    # No effort allocator — training uses fixed depth for predictable speed
    from engine.metacognition.confidence import DecisionConfidenceTracker
    from engine.metacognition.self_assessment import SelfAssessor
    conf_tracker = DecisionConfidenceTracker()
    self_assessor = SelfAssessor()
    run_state["confidence_tracker"] = conf_tracker
    run_state["self_assessor"] = self_assessor

    def _run_training():
        runner = LearningRunner(
            engine, evaluator, max_depth=req.depth,
            confidence_tracker=conf_tracker,
            self_assessor=self_assessor,
        )

        def on_progress(snapshot, results):
            run_state["games_played"] = snapshot.game_number
            run_state["snapshots"].append({
                "game": snapshot.game_number,
                "outcome": snapshot.outcome,
                "rolling_win_rate": snapshot.rolling_win_rate,
                "duration_ms": snapshot.duration_ms,
            })

        results = runner.train(req.num_games, progress_callback=on_progress)
        run_state["status"] = "complete"
        run_state["results"] = results.to_dict()

        # Auto-save to memory
        _memory_store.save(evaluator)

    thread = threading.Thread(target=_run_training, daemon=True)
    thread.start()

    return {"training_id": training_id}


@app.get("/api/training/{training_id}/status")
def training_status(training_id: str):
    run = _training_runs.get(training_id)
    if not run:
        raise HTTPException(404, "Training run not found")

    evaluator = run["evaluator"]
    assessor = run.get("self_assessor")
    conf_tracker = run.get("confidence_tracker")
    effort_alloc = run.get("effort_allocator")

    response = {
        "status": run["status"],
        "game": run["game"],
        "game_name": run["game_name"],
        "games_played": run["games_played"],
        "total_games": run["num_games"],
        "snapshots": run["snapshots"],
        "weights": [
            {"feature": f.name, "weight": round(w, 4), "description": f.description}
            for f, w in zip(evaluator.features, evaluator.weights)
        ],
        "generation": evaluator.generation,
        "results": run["results"],
    }

    # Add metacognition data
    if assessor:
        profile = assessor.assess(run["game_name"])
        response["self_assessment"] = profile.to_dict()
    if conf_tracker:
        response["confidence_stats"] = conf_tracker.stats()
    if effort_alloc:
        response["effort_stats"] = effort_alloc.stats()

    return response


# --- Memory Endpoints ---

@app.get("/api/memory/games")
def list_memories():
    return {"games": _memory_store.list_games()}


@app.get("/api/memory/{game_name}/weights")
def get_weights(game_name: str):
    evaluator = _memory_store.load(game_name)
    if evaluator is None:
        raise HTTPException(404, f"No learned weights for: {game_name}")
    return {
        "game_name": evaluator.game_name,
        "generation": evaluator.generation,
        "weights": evaluator.weight_summary(),
    }


@app.post("/api/memory/{game_name}/reset")
def reset_memory(game_name: str):
    deleted = _memory_store.delete(game_name)
    return {"deleted": deleted}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
