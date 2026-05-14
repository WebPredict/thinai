# ThinAI Design Document — Game Description Language and Core Engine

*Phase 0 deliverable. Companion to [dev-plan.md](dev-plan.md).*

---

## Table of Contents

1. [Overview](#1-overview)
2. [Design Goals and Constraints](#2-design-goals-and-constraints)
3. [GDL Schema Reference](#3-gdl-schema-reference)
4. [Condition/Effect Expression Language](#4-conditioneffect-expression-language)
5. [Worked Examples](#5-worked-examples)
6. [Constrained English Input Format](#6-constrained-english-input-format)
7. [Parser Architecture](#7-parser-architecture)
8. [Engine Architecture](#8-engine-architecture)
9. [Extension Roadmap](#9-extension-roadmap)
10. [Interface Contracts](#10-interface-contracts)
11. [Testing Strategy](#11-testing-strategy)
12. [Phase 0 Decision Summary](#12-phase-0-decision-summary)

---

## 1. Overview

This document specifies the concrete design of ThinAI's core infrastructure: the Game Description Language (GDL) that represents game knowledge internally, the constrained-English parser that produces it, and the game engine that executes it.

**Relationship to dev-plan.md:** The dev plan describes *what* the system does and *why*. This document describes *how* — the actual data structures, grammars, interfaces, and architectural patterns.

**Scope:** GDL schema, expression language, parser pipeline, engine execution model, and the interfaces between them. Does not cover the strategic reasoner, memory/retention system, correction handler, or metacognitive layer in detail — those are Phase 2+ concerns that consume the interfaces defined here.

---

## 2. Design Goals and Constraints

The GDL is the central data structure of the entire system. Every other component either produces, consumes, or modifies it. Its design must satisfy:

**Executable.** The game engine must be able to take a GDL specification and run a complete game — generate legal moves, apply them, detect terminal states — with no external information.

**Inspectable.** A human reading the GDL JSON should be able to understand what the game is and how it works. This supports the project's interpretability principle and makes debugging tractable.

**Modifiable.** The correction handler must be able to modify individual rules, conditions, or effects without rewriting the entire specification. This means rules are discrete, addressable entries — not a monolithic program.

**Serializable.** The memory/retention system stores and loads GDL as JSON. No runtime state or closures — everything is data.

**Validatable.** A JSON Schema defines the structure. The parser validates its output before passing it to the engine. Invalid GDL is caught at parse time, not at runtime.

**Extensible.** The initial schema handles deterministic, perfect-information, two-player, alternating-turn games. Extension points exist for: hidden information (zones), randomness (random action type), simultaneous moves, multi-phase games, and n-player games. These extensions should not require schema-breaking changes.

**What the GDL deliberately does NOT express:**
- Visual rendering details (beyond display hints for pieces)
- Strategic knowledge or evaluation heuristics
- Learning history or confidence scores
- Natural-language rule text (that's the parser's input, not the GDL)

---

## 3. GDL Schema Reference

### 3.1 Top-Level Structure

A GDL document is a JSON object with these top-level keys:

```
{
  "meta":           required — game metadata
  "board":          required — spatial structure
  "pieces":         required — game object definitions
  "state_vars":     optional — non-board game state (default: [])
  "setup":          required — initial board configuration
  "rules":          required — move definitions
  "end_conditions": required — terminal state checks
  "_comments":      optional — documentation (ignored by engine)
}
```

### 3.2 `meta` — Game Metadata

```
{
  "name":        string, required — human-readable game name
  "players":     int, required — number of players (≥ 1)
  "turn_order":  enum, required — "alternating" | "conditional"
  "turn_rule":   string, optional — condition expression evaluated after each move
                   to determine next player. Required when turn_order is "conditional".
  "phases":      [string], optional — named phases for multi-phase games (extension point)
  "version":     string, optional — GDL spec version
}
```

**Turn order semantics:**
- `"alternating"`: player1, player2, player1, player2, ... Simple round-robin.
- `"conditional"`: after each move, `turn_rule` is evaluated. It should resolve to `same_player` or `next_player`. Used for games like mancala (extra turn) and reversi (forced pass).

### 3.3 `board` — Spatial Structure

```
{
  "type":     enum, required — "grid" | "track" | "graph" | "collection"
  "grid":     object, conditional — present when type is "grid"
  "track":    object, conditional — present when type is "track"
  "regions":  [object], optional — named subsets of spaces
  "zones":    [object], optional — visibility regions (extension point for hidden info)
}
```

#### Grid boards

```
"grid": {
  "rows":      int, required — number of rows (≥ 1)
  "cols":      int, required — number of columns (≥ 1)
  "topology":  enum, optional — "rect4" | "rect8" | "hex6" (default: "rect8")
}
```

Topology determines adjacency and which directions exist:
- `rect4`: 4 cardinal neighbors (N, E, S, W)
- `rect8`: 8 neighbors including diagonals (N, NE, E, SE, S, SW, W, NW)
- `hex6`: 6 hexagonal neighbors

Spaces on a grid are addressed as `space_at(row, col)` where row 0 is the top.

#### Track boards

```
"track": {
  "length":    int, required — number of spaces (≥ 1)
  "loop":      bool, optional — whether the track wraps around (default: false)
}
```

Spaces on a track are addressed by `index`. On a looping track, the space after index `length-1` is index `0`.

#### Graph boards (extension point)

For irregular topologies. Not needed for initial games. Will be specified as an adjacency list of named spaces.

#### Collection boards (extension point)

For games with hands, decks, piles without spatial structure. E.g., nim (piles of stones), card games (hands, draw pile, discard pile).

#### Regions

Named subsets of spaces, used in conditions and selectors:

```
{
  "name":    string, required — identifier used in expressions
  "spaces":  string, required — selector expression defining which spaces belong
  "owner":   string, optional — "player1", "player2", "each", or omitted for shared
}
```

When `owner` is `"each"`, the region is per-player. Expressions like `region(current_player_pits)` resolve to the appropriate player's region.

#### Zones (extension point)

For hidden information games:

```
{
  "name":        string — zone identifier
  "visibility":  enum — "all" (public) | "owner" (only owner sees) | "none" (hidden from all)
}
```

### 3.4 `pieces` — Game Objects

```
[
  {
    "name":        string, required — piece type name
    "owner":       string, required — "player1", "player2", "each", or "none"
    "properties":  object, optional — custom properties (name → {type, default})
    "display":     string, optional — visual hint for rendering
  }
]
```

`"owner": "each"` means each player has their own version of this piece type. `"owner": "none"` means the piece is unowned (e.g., mancala stones).

Custom properties allow pieces to carry state:
```
"properties": {
  "flippable":  { "type": "bool", "default": true },
  "rank":       { "type": "int", "default": 0 }
}
```

### 3.5 `state_vars` — Non-Board Game State

```
[
  {
    "name":     string, required — variable name for use in expressions
    "type":     enum, required — "int" | "bool" | "string"
    "scope":    enum, optional — "global" | "per_player" (default: "global")
    "initial":  any, required — starting value
  }
]
```

State variables track game state that doesn't live on the board. Examples: mancala's `last_pit_is_store` flag, a score counter, a phase indicator.

### 3.6 `setup` — Initial Configuration

```
[
  {
    "action":  enum, required — "place" | "set" | "fill"
    "piece":   string, conditional — piece expression (for place/fill)
    "at":      string, conditional — space selector (for place/fill)
    "count":   int, optional — number of pieces per space (for fill)
    "var":     string, conditional — variable name (for set)
    "value":   any, conditional — value to assign (for set)
  }
]
```

Actions:
- `place`: put a specific piece at a specific space. E.g., `{"action": "place", "piece": "disc(player1)", "at": "space_at(3, 3)"}`
- `fill`: place `count` pieces at every space matching the selector. E.g., `{"action": "fill", "piece": "stone", "at": "index >= 0 and index <= 5", "count": 4}`
- `set`: initialize a state variable to a value.

An empty `setup` array means the board starts empty.

### 3.7 `rules` — Move Definitions

```
[
  {
    "name":       string, required — human-readable rule name
    "action":     enum, required — "place" | "move" | "remove" | "distribute" | "set" | "swap"
    "phase":      string, optional — which phase this applies in (extension point)
    "actor":      string, optional — who performs this (default: "current_player")
    "params":     [object], required — what the player chooses
    "conditions": [string], required — legality conditions (all must be true)
    "effects":    [string], required — state changes applied in order
    "turn_after": string, optional — override for who moves next
  }
]
```

#### Parameters

Each parameter represents a choice the player makes:

```
{
  "name":    string — bound variable name for use in conditions/effects
  "select":  string — what kind of thing to choose: "empty_space", "space", "piece",
               "int_range(min, max)", "region(name)"
  "from":    string, optional — constraint on the selection pool
}
```

The engine generates legal moves by enumerating all valid parameter combinations that satisfy the conditions.

#### Conditions

An array of expression strings. All must evaluate to `true` for the move to be legal. Evaluated against the current game state with parameter bindings.

#### Effects

An array of effect strings. Applied in order when a move is executed. Can include:
- Placement: `place piece(player) at space`
- Removal: `remove piece_at(space)`
- Movement: `move piece_at(from) to to`
- Variable assignment: `set var = expr`
- Conditional: `if condition: effect`
- Iteration: `for x in selector: effect`
- Built-in operations: `flip_line(...)`, `sow(...)`, `capture_with_opposite(...)`

### 3.8 `end_conditions` — Terminal States

```
[
  {
    "type":       enum, required — "win" | "loss" | "draw"
    "player":     string, optional — who wins/loses (e.g., "current_player", "player_by_score")
    "condition":  string, required — condition expression checked after each move
    "score":      string, optional — score expression for score-based outcomes
  }
]
```

End conditions are checked after every move, in order. The first matching condition determines the game outcome.

`"player": "player_by_score"` means the winner is determined by comparing the `score` expression evaluated for each player.

---

## 4. Condition/Effect Expression Language

### 4.1 Design Rationale

The expression language is the core of the GDL. It must be:
- **Powerful enough** to express all 4 starter games cleanly
- **Simple enough** to parse with Lark without becoming a general-purpose language
- **Safe** — no unbounded recursion, no general `while` loops, no side effects in conditions
- **Extensible** — new built-in functions can be added without grammar changes

The key design choice: game-specific mechanics (sowing, flipping, gravity) are expressed as **built-in functions** rather than composed from loop primitives. This keeps the language simple and each operation bounded.

### 4.2 Formal Grammar (Lark EBNF)

```
start: expr

// Boolean
expr: or_expr
or_expr: and_expr ("or" and_expr)*
and_expr: not_expr ("and" not_expr)*
not_expr: "not" atom | atom

// Atoms
atom: comparison
    | quantified
    | func_call
    | "(" expr ")"
    | value

// Comparison
comparison: value comp_op value
comp_op: "==" | "!=" | ">" | "<" | ">=" | "<="

// Quantifiers
quantified: quantifier IDENT "in" selector ":" expr
quantifier: "all" | "any" | "no" | "count"

// Selectors
selector: "spaces" filter?
        | "directions" filter?
        | "pieces" filter?
        | "neighbors(" value ")" filter?
        | "region(" value ")"
        | "range(" value "," value ")"
filter: "[" expr "]"

// Function calls
func_call: IDENT "(" (value ("," value)*)? ")"

// Values
value: IDENT ("." IDENT)*      // property access
     | NUMBER
     | STRING
     | "true" | "false"
     | "empty"
     | "current_player"
     | "opponent"
     | "next_player"
     | "same_player"

// Terminals
IDENT: /[a-z_][a-z0-9_]*/
NUMBER: /\-?[0-9]+/
STRING: /"[^"]*"/
```

### 4.3 Type System

Four types:
- `int` — integers
- `bool` — true/false
- `string` — text values
- `space` — a board position (internally a reference)
- `piece` — a game object (internally a reference)
- `empty` — the absence of a piece (singleton)
- `player` — a player identifier
- `direction` — a direction vector (grid-specific)

Type checking is dynamic (Python). Comparisons between incompatible types evaluate to `false` rather than erroring, matching the "graceful degradation" principle.

### 4.4 Built-in Functions Reference

#### Universal functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `piece_at(space)` | space → piece \| empty | Get the piece at a board position |
| `pieces_at(space)` | space → [piece] | Get all pieces at a position (for stacking games / mancala pits) |
| `pieces_in(region)` | region → [piece] | Get all pieces in a named region |
| `owner(piece)` | piece → player | Get the owner of a piece |
| `count(selector)` | selector → int | Count items matching a selector |
| `space_at(...)` | (row, col) or (index) → space | Get a space by coordinates |
| `has_legal_move(player)` | player → bool | Whether player has any legal move in current state |

#### Grid functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `row(space)` | space → int | Row coordinate |
| `col(space)` | space → int | Column coordinate |
| `line_length(space, dir, player)` | (space, direction, player) → int | Count consecutive pieces owned by player through space in given direction (both ways) |
| `lowest_empty_row(col)` | int → int | Lowest (highest row number) empty row in a column. For gravity mechanics. |

#### Reversi functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `flanks(space, dir, player)` | (space, direction, player) → bool | True if placing at space creates a flank in direction: one or more opponent pieces followed by player's piece |
| `flip_line(space, dir, player)` | (space, direction, player) → void | **Effect only.** Walk from space in direction, flip each opponent piece until reaching player's piece |

#### Mancala functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `sow(pit, count, skip)` | (space, int, region) → int | **Effect.** Pick up count stones from pit, distribute one per space in track order, skipping spaces in skip region. Returns index of last space dropped into. |
| `capture_with_opposite(index)` | int → void | **Effect only.** Move the stone at index and all stones at the opposite pit into the current player's store |

### 4.5 Selectors and Quantifiers

Selectors produce sets of items to iterate over or count:

- `spaces` — all board spaces
- `spaces[expr]` — spaces where `expr` is true (with implicit variable `s`)
- `directions` — all direction vectors for the board's topology
- `directions[expr]` — filtered directions (with implicit variable `d`)
- `pieces` — all pieces on the board
- `pieces[expr]` — filtered pieces (with implicit variable `p`)
- `neighbors(space)` — adjacent spaces
- `region(name)` — spaces in a named region
- `range(min, max)` — integer range, inclusive

Quantifiers bind a variable and iterate:

- `any x in selector: expr` — true if expr is true for at least one x
- `all x in selector: expr` — true if expr is true for every x
- `no x in selector: expr` — true if expr is true for no x
- `count(selector)` — returns the number of items (also usable as a function)

### 4.6 Effect Syntax

Effects use the expression grammar plus imperative constructs:

```
effect: "place" piece_expr "at" value
      | "remove" value
      | "move" value "to" value
      | "set" IDENT "=" expr
      | "set" value "." IDENT "=" expr
      | "increment" IDENT ("by" value)?
      | "if" expr ":" effect
      | "for" IDENT "in" selector ":" effect
      | func_call                              // for effect-only built-ins

piece_expr: IDENT "(" value ")"               // e.g., mark(current_player)
```

Effects are executed in order. Variable bindings from earlier effects (via `set`) are available to later effects.

### 4.7 Variable Binding and Scope

- **Rule parameters** (`params[].name`) are bound when the player chooses a move and available in all conditions and effects.
- **Effect variables** (via `set _name = expr`) are bound during effect execution and available to subsequent effects and end_condition evaluation.
- **State variables** (`state_vars[].name`) persist across moves and are available everywhere.
- **Implicit variables** in selectors (`s` in `spaces[...]`, `d` in `directions[...]`, `p` in `pieces[...]`) are scoped to their selector expression.
- Convention: effect-local variables start with `_` (e.g., `_target`). State variables do not.

### 4.8 Extensibility: Adding New Built-ins

New game mechanics are added by:
1. Implementing the function in Python in the engine's built-in registry
2. Adding it to the built-in functions table in this document
3. No grammar changes needed — `func_call` already handles arbitrary function names

This is the primary extension mechanism. The grammar and schema stay stable; the set of available functions grows.

---

## 5. Worked Examples

Complete GDL specifications live in `engine/games/examples/`. This section provides annotations explaining how each game exercises the schema.

### 5.1 Tic-Tac-Toe

**File:** `engine/games/examples/tictactoe.json`

The simplest possible game. Establishes baseline patterns:
- Grid board with `rect8` topology (diagonals matter for win detection)
- Single piece type owned by `each` player
- One rule: place on any empty space
- Win by line of 3, draw when board full
- `last_placed` in end conditions refers to the space from the most recent `place` effect

**Schema features exercised:** grid board, piece placement, `line_length` built-in, `any` quantifier over directions, `count` over filtered spaces.

### 5.2 Connect Four

**File:** `engine/games/examples/connect_four.json`

Builds on tic-tac-toe with two additions:
- **Column selection:** Player chooses a column (integer), not a space. `select: "int_range(0, 6)"`
- **Gravity:** `lowest_empty_row(column)` computes where the disc lands. Effect binds `_target` before placing so end conditions can reference the actual landing space.

**Schema features exercised:** int_range parameter selection, `lowest_empty_row` built-in, effect variable binding (`set _target = ...`), legality condition on column fullness.

### 5.3 Mancala

**File:** `engine/games/examples/mancala.json`

The most complex starter game. Tests nearly every schema feature:
- **Track board** with loop, demonstrating non-grid spatial structure
- **Regions** defining each player's pits and stores
- **Unowned pieces** (stones belong to no player)
- **State variables** tracking sow results across the move boundary
- **`sow` built-in** for the distribution mechanic
- **Conditional turn order** — extra turn when last stone lands in own store
- **Conditional capture** — if last stone lands in empty pit on own side
- **Score-based win** — count stones in stores when one side is empty

**Schema features exercised:** track board, regions with ownership, fill setup, state_vars, distribute action, `sow` built-in, conditional effects, `capture_with_opposite` built-in, conditional turn_rule, player_by_score win.

### 5.4 Reversi

**File:** `engine/games/examples/reversi.json`

Tests the flank/flip pattern and pass mechanics:
- **Explicit setup** placing 4 initial discs
- **Flank condition** — placement is only legal if it flanks at least one line of opponent discs
- **Flip cascade** — all flanked lines are flipped via `for d in directions[flanks(...)]: flip_line(...)`
- **Conditional turns** — if next player has no legal move, current player goes again
- **Score-based end** — game ends when neither player can move; most discs wins

**Schema features exercised:** explicit piece placement in setup, `flanks` and `flip_line` built-ins, `for` iteration in effects, `has_legal_move` function, conditional turn order, score-based win/draw.

### 5.5 Cross-Game Feature Matrix

| Feature | TTT | C4 | Mancala | Reversi |
|---------|:---:|:--:|:-------:|:-------:|
| Grid board | x | x | | x |
| Track board | | | x | |
| Regions | | | x | |
| Piece placement | x | x | | x |
| Column select + gravity | | x | | |
| Distribute/sow | | | x | |
| Flank + flip | | | | x |
| State variables | | | x | |
| Effect variable binding | | x | | |
| Conditional effects | | | x | |
| Iteration in effects | | | | x |
| Line-based win | x | x | | |
| Score-based win | | | x | x |
| Alternating turns | x | x | | |
| Conditional turns | | | x | x |
| Explicit setup | | | x | x |
| Fill setup | | | x | |

---

## 6. Constrained English Input Format

### 6.1 Section Keywords and Structure

Constrained English input uses section keywords to structure the description:

```
GAME:     Game name
PLAYERS:  Player count and turn structure
BOARD:    Spatial structure description
PIECES:   Game object definitions
SETUP:    Initial board state
MOVES:    How players take turns (move rules)
SPECIAL:  Extra rules, exceptions, triggered effects
WIN:      Victory conditions
DRAW:     Draw conditions (optional)
```

Each section begins with its keyword followed by a colon. Multi-line content is indented under the keyword. Sections can appear in any order but the above is conventional.

### 6.2 Pattern Templates

The parser recognizes structured English patterns and maps them to GDL constructs. Key templates:

**Board patterns:**
- `{N}x{M} grid` → `board.type: "grid", grid.rows: N, grid.cols: M`
- `{N}-space track` + `loop`/`circular` → `board.type: "track", track.length: N, track.loop: true/false`
- `Spaces {range} are {player}'s {name}` → region definition

**Piece patterns:**
- `each player has a {PIECE}` → `pieces: [{name: PIECE, owner: "each"}]`
- `{PIECE}s (no owner)` / `{PIECE}s (shared)` → `owner: "none"`

**Move patterns:**
- `places {PIECE} on any empty space` → place action with `empty_space` selector
- `chooses a column` → int_range parameter
- `drops to the lowest empty row` → `lowest_empty_row` built-in
- `picks one of their {REGION} that contains {PIECE}` → space selector with region constraint
- `distribute/sow ... one per ... skipping` → `sow` built-in

**Win patterns:**
- `{N} in a row` → `line_length >= N` with direction quantifier
- `more {PIECE}s wins` → score-based win with `count(pieces[owner == player])`
- `when {REGION} is empty, count {PIECE}s` → conditional score-based win

**Turn patterns:**
- `alternating turns` → `turn_order: "alternating"`
- `takes another turn` / `extra turn` → conditional turn rule
- `passes` / `no legal move` → conditional turn with `has_legal_move` check

### 6.3 Semantic Frames

Beyond simple pattern matching, the parser uses semantic frames — structured templates for common game mechanics that combine multiple GDL elements:

**Sow frame** (triggered by: distribute, sow, one-per, counter-clockwise):
- Creates: `distribute` action, `sow()` built-in call, state vars for tracking last pit
- Expects: source selection, stone count, skip target

**Capture frame** (triggered by: capture, take, opponent, opposite):
- Creates: conditional effect moving pieces to a store/off-board
- Expects: capture condition, source, destination

**Flank frame** (triggered by: flank, sandwich, between, surround):
- Creates: `flanks()` condition, `flip_line()` effect with direction iteration
- Expects: placement trigger, direction specification

**Gravity frame** (triggered by: drops, falls, lowest, gravity):
- Creates: `lowest_empty_row()` in effect, column-based parameter
- Expects: column selection, board specification

**Line-win frame** (triggered by: in a row, in a line, consecutive):
- Creates: `line_length()` in end condition with direction quantifier
- Expects: count threshold, piece ownership

### 6.4 Worked English-to-GDL Mappings

#### Tic-Tac-Toe

```
GAME: Tic-Tac-Toe
PLAYERS: 2, alternating turns

BOARD: 3x3 grid

PIECES: each player has a mark (X or O)

SETUP: board starts empty

MOVES:
  A player places their mark on any empty space.

WIN: A player wins by getting 3 of their marks in a row
     (horizontal, vertical, or diagonal).

DRAW: The game is a draw if the board is full with no winner.
```

**Parsing trace:**
1. `GAME: Tic-Tac-Toe` → `meta.name = "Tic-Tac-Toe"`
2. `2, alternating turns` → `meta.players = 2, meta.turn_order = "alternating"`
3. `3x3 grid` → matches `{N}x{M} grid` template → grid board with `rect8` (default for "row" mentions)
4. `each player has a mark` → matches piece template → `pieces: [{name: "mark", owner: "each"}]`
5. `board starts empty` → `setup: []`
6. `places their mark on any empty space` → matches placement template → rule with `empty_space` selector
7. `3 of their marks in a row (horizontal, vertical, or diagonal)` → matches line-win frame → `line_length >= 3` with `rect8` directions
8. `board is full with no winner` → `count(spaces[empty]) == 0`

#### Connect Four

```
GAME: Connect Four
PLAYERS: 2, alternating turns

BOARD: 6x7 grid (6 rows, 7 columns)

PIECES: each player has discs

SETUP: board starts empty

MOVES:
  A player chooses a column that is not full.
  Their disc drops to the lowest empty row in that column.

WIN: A player wins by getting 4 of their discs in a row
     (horizontal, vertical, or diagonal).

DRAW: The game is a draw if the board is full with no winner.
```

**Key parsing decisions:**
- `chooses a column` → column-based parameter (`int_range`)
- `not full` → condition: top row of column is empty
- `drops to the lowest empty row` → triggers gravity frame → `lowest_empty_row` built-in
- `4 ... in a row` → same line-win frame as tic-tac-toe but with threshold 4

#### Mancala

```
GAME: Mancala (Kalah)
PLAYERS: 2, alternating turns (with extra turn rule)

BOARD: 14-space track in a loop.
  Spaces 0-5 are player 1's pits.
  Space 6 is player 1's store.
  Spaces 7-12 are player 2's pits.
  Space 13 is player 2's store.

PIECES: stones (no owner)

SETUP: Place 4 stones in each pit (not in stores).

MOVES:
  A player picks one of their own pits that contains stones.
  Take all stones from that pit.
  Distribute them one per pit counter-clockwise, skipping
    the opponent's store.

SPECIAL:
  If the last stone lands in the player's own store,
    that player takes another turn.
  If the last stone lands in an empty pit on the player's
    own side, capture that stone and all stones in the
    opposite pit. Place captured stones in the player's store.

WIN: When all pits on one side are empty, the game ends.
     Each player collects remaining stones on their side
     into their store. The player with more stones wins.

DRAW: If both players have equal stones, the game is a draw.
```

**Key parsing decisions:**
- `14-space track in a loop` → track board
- `Spaces 0-5 are player 1's pits` → region definitions (×4)
- `stones (no owner)` → piece with `owner: "none"`
- `4 stones in each pit (not in stores)` → fill setup with region filter
- `Distribute them one per pit counter-clockwise, skipping the opponent's store` → triggers sow frame → `sow()` built-in
- `last stone lands in the player's own store ... takes another turn` → state var + conditional turn rule
- `last stone lands in an empty pit on the player's own side, capture ... opposite pit` → conditional capture effect
- `more stones wins` → score-based win

#### Reversi

```
GAME: Reversi
PLAYERS: 2, alternating turns (player may pass if no legal move)

BOARD: 8x8 grid

PIECES: each player has discs (black and white, flippable)

SETUP:
  Place player 1's disc at (3,3) and (4,4).
  Place player 2's disc at (3,4) and (4,3).

MOVES:
  A player places a disc on an empty space.
  The placement must flank at least one line of the
    opponent's discs (horizontally, vertically, or diagonally).
  "Flanking" means the placed disc and another of the player's
    discs have a continuous line of opponent discs between them.

SPECIAL:
  All flanked opponent discs are flipped to the current
    player's color.
  If a player has no legal move, they pass (opponent moves again).

WIN: When neither player can move, the player with more
     discs on the board wins.

DRAW: If both players have equal discs, the game is a draw.
```

**Key parsing decisions:**
- `player may pass if no legal move` → conditional turn order
- `flippable` → piece property hint (flipping = changing owner)
- `Place player 1's disc at (3,3)` → explicit setup placements
- `must flank at least one line` → triggers flank frame → `flanks()` condition
- `"Flanking" means ...` → parser recognizes as definition/elaboration of previous concept, confirms understanding
- `All flanked opponent discs are flipped` → `for d in directions[flanks(...)]: flip_line(...)` effect
- `no legal move, they pass` → `has_legal_move` in turn rule
- `neither player can move` → end condition checking both players
- `more discs ... wins` → score-based win

### 6.5 Ambiguity Detection and Clarification Questions

The parser tracks confidence in its interpretation. When confidence is low, it generates clarification questions rather than guessing:

**Common ambiguities:**
- "in a row" — does this include diagonals? (tic-tac-toe: yes. Other games: ask.)
- "captures" — does the captured piece get removed, or moved to a store? (context-dependent)
- "opposite" — what's the opposite pit on a mancala board? (needs board geometry)
- Turn order when not explicitly stated
- Whether a game ends immediately on win condition or plays out the round

**Question format:**
```
"I understood that winning requires 3 marks in a row.
 Should diagonals count as 'in a row'? [yes/no]"

"When a stone lands in an empty pit, you said to capture
 the opposite pit's stones. On this 14-space board, is the
 opposite of pit 2 pit 10 (directly across)? [yes/no]"
```

---

## 7. Parser Architecture

### 7.1 Pipeline

```
Constrained English text
        │
        ▼
   ┌─────────┐
   │ Tokenize │  Split into sections by keywords (GAME:, BOARD:, etc.)
   └────┬─────┘  Normalize whitespace, handle continuations.
        │
        ▼
   ┌──────────────┐
   │ Pattern Match │  Match each section against template patterns.
   └────┬──────────┘  Produce candidate interpretations with confidence.
        │
        ▼
   ┌────────────┐
   │ Frame Fill  │  Combine matched patterns into semantic frames.
   └────┬────────┘  Resolve cross-references between sections.
        │          Detect ambiguities → generate clarification questions.
        │
        ▼
   ┌──────────┐
   │ GDL Emit │  Convert filled frames to GDL JSON.
   └────┬─────┘  Validate against schema.
        │
        ▼
   GDL JSON (validated)
```

### 7.2 Lark Grammar for Expression Language

The Lark grammar from Section 4.2 is used in two places:
1. **Parser output validation:** condition and effect strings in emitted GDL are parsed to verify syntactic correctness.
2. **Engine execution:** condition and effect strings are parsed and evaluated at runtime.

The grammar lives in `engine/gdl/expressions.lark`.

### 7.3 Template Registry

Templates are registered as Python objects with:
- **Pattern:** regex or keyword sequence to match
- **Confidence:** how strongly a match indicates this template (0.0–1.0)
- **Slots:** named extraction groups from the pattern
- **GDL output:** function mapping extracted slots to GDL fields
- **Conflicts:** which other templates this one is incompatible with

Initial templates (~20-30) cover the patterns listed in Section 6.2.

### 7.4 Semantic Frame Definitions

Frames are higher-level structures composed from multiple template matches:
- **Required slots:** what must be filled for the frame to activate
- **Optional slots:** additional detail that enriches the output
- **Cross-references:** how this frame relates to other frames (e.g., sow frame needs board frame's track info)
- **Ambiguity triggers:** what missing information should generate clarification questions

### 7.5 Validation Against Schema

After GDL emission, the output is validated:
1. **Structural validation:** JSON Schema check (all required fields present, correct types)
2. **Expression validation:** every condition and effect string parses successfully under the Lark grammar
3. **Reference validation:** all variables referenced in conditions/effects are defined (as params, state_vars, or built-ins)
4. **Completeness check:** at least one rule, at least one end condition

### 7.6 Error Reporting

Validation errors are reported with:
- Which section of the English input likely caused the issue
- What the parser tried to interpret and where it got stuck
- Suggested reformulation

---

## 8. Engine Architecture

### 8.1 State Representation

Game state is a Python object containing:
- **Board state:** mapping from space identifier to piece (or empty). For grids: `dict[(row, col)] → Piece | None`. For tracks: `dict[int] → [Piece]` (list for stacking).
- **State variables:** `dict[str] → value`
- **Current player:** player identifier
- **Move history:** list of (player, rule_name, params, effects_applied) for undo support
- **Turn number:** int

State is copyable (for search) and hashable (for transposition tables).

### 8.2 Legal Move Generation

```python
def legal_moves(state, gdl):
    moves = []
    for rule in gdl["rules"]:
        for param_combo in enumerate_params(rule["params"], state):
            bindings = bind_params(rule["params"], param_combo)
            if all(evaluate(cond, state, bindings) for cond in rule["conditions"]):
                moves.append(Move(rule["name"], param_combo))
    return moves
```

`enumerate_params` generates all valid parameter combinations:
- `empty_space` → all spaces where `piece_at(s) == empty`
- `space` with `from` constraint → spaces in the specified region with additional filtering
- `int_range(a, b)` → integers a through b inclusive

### 8.3 Move Application (Effect Execution)

```python
def apply_move(state, gdl, move):
    state = copy(state)
    bindings = bind_params(move.rule.params, move.params)
    for effect in move.rule.effects:
        execute_effect(effect, state, bindings)
    check_end_conditions(state, gdl, bindings)
    determine_next_player(state, gdl)
    return state
```

Effects are executed sequentially. Each effect can modify `state` and add to `bindings` (via `set`).

### 8.4 Terminal Detection

After each move, end conditions are checked in order:
1. Evaluate each `end_condition.condition` against current state
2. First matching condition determines outcome
3. For `player_by_score`, evaluate `score` expression for each player and compare

### 8.5 State Hashing

For the strategic reasoner's transposition table:
- Board state serialized as a frozen dict
- State variables included in hash
- Current player included in hash
- Hash via Python's `hash()` on the frozen tuple

### 8.6 Undo/Redo Support

Move history stores enough information to reverse any move:
- Board state delta (which spaces changed, previous contents)
- State variable delta (which vars changed, previous values)
- This avoids full state copies while supporting search backtracking

### 8.7 Performance Considerations

For the "smart kid" level of play we're targeting:
- Legal move generation must be fast (called many times during search)
- Expression evaluation should cache parsed ASTs (parse once, evaluate many times)
- State copying should be shallow where possible (copy-on-write for board)
- Profiling will identify real bottlenecks — don't optimize prematurely

---

## 9. Extension Roadmap

### 9.1 Tier I-II Additions

**Nim:** Board type `collection` — named piles with stone counts. Rules: choose a pile, remove 1 to N stones. No new built-ins needed; just `remove` action with `int_range` parameter for count. Win: last stone wins/loses (configurable via state var).

**Chutes & Ladders:** Track board (non-looping). Adds randomness via `roll_dice(min, max)` built-in that returns a random integer. Triggered movement via conditional effects: `if index(current_piece) in chutes: move current_piece to chute_end(index(current_piece))`. Chute/ladder mappings stored in a lookup region or state structure.

Neither requires schema changes — only new built-in functions.

### 9.2 Hidden Information (Tier III+)

- Board `zones` with `visibility: "owner"` for hands, face-down cards
- Engine maintains per-player views of game state
- Belief state tracking for the reasoner
- New built-ins: `draw_card()`, `reveal()`, `hide()`

### 9.3 Simultaneous Moves (Tier III+)

- New `turn_order` value: `"simultaneous"`
- Both players submit moves before resolution
- Engine collects moves then applies them with a resolution function
- Schema addition: `resolution` field in rules

### 9.4 Multi-Phase Games

- `meta.phases` array defines phase names
- Rules tagged with `phase` field
- Transition between phases via `set_phase()` effect
- Example: deckbuilding game with draft phase then combat phase

### 9.5 Scoring Systems

- `state_vars` with `scope: "per_player"` for individual scores
- `increment` effect for score updates
- More complex scoring via custom built-in functions

---

## 10. Interface Contracts

### 10.1 Parser → Engine (GDL JSON)

The parser produces a GDL JSON document validated against the schema. The engine consumes it without needing to re-parse any English text. The GDL is the complete, self-contained game specification.

```python
# Parser output
gdl: dict  # Validated GDL JSON

# Engine accepts
engine = GameEngine(gdl)
state = engine.initial_state()
moves = engine.legal_moves(state)
new_state = engine.apply_move(state, move)
result = engine.check_terminal(state)
```

### 10.2 Engine → Strategic Reasoner

```python
# Reasoner receives
state: GameState          # Current board + vars + current player
legal_moves: list[Move]   # Available moves from engine
is_terminal: bool         # Whether state is terminal
result: GameResult | None # Win/loss/draw if terminal

# Reasoner returns
chosen_move: Move         # Selected from legal_moves
reasoning: list[str]      # Explanation of decision (for commentary)
confidence: float         # 0.0-1.0 confidence in choice
```

### 10.3 Engine → Visualization (React frontend)

```python
# Viz receives (via API)
{
  "board_type": "grid" | "track" | ...,
  "board_config": { ... },          # rows/cols/length/etc.
  "spaces": { "0,1": {"piece": "X", "owner": "player1"}, ... },
  "legal_moves": [...],             # For highlighting valid moves
  "last_move": { ... },             # For animation
  "state_vars": { ... },
  "current_player": "player1",
  "game_result": null | { "type": "win", "player": "player1" }
}
```

### 10.4 Correction Handler → GDL

The correction handler modifies GDL by addressing specific entries:

```python
# Correction types
correction.modify_condition(rule_name, condition_index, new_condition)
correction.modify_effect(rule_name, effect_index, new_effect)
correction.add_rule(new_rule)
correction.remove_rule(rule_name)
correction.modify_end_condition(index, new_condition)
correction.modify_setup(index, new_setup_action)
```

Because the GDL is data (not code), each correction is a targeted edit to a specific field.

### 10.5 Memory System ↔ GDL

```python
# Save
memory.store(game_name, gdl_json, metadata)

# Load
gdl_json = memory.retrieve(game_name)

# List
games = memory.list_games()  # Returns names + metadata
```

GDL JSON is the serialization format. The memory system stores it as-is, possibly with additional metadata (learning history, confidence scores, correction log).

---

## 11. Testing Strategy

### 11.1 GDL Schema Validation Tests

- Every example file in `engine/games/examples/` must pass JSON Schema validation
- Test that invalid GDL (missing fields, wrong types) is rejected
- Test edge cases: empty rules array, empty conditions, empty effects

### 11.2 Expression Language Parser Tests

- Parse and evaluate known expressions for each built-in function
- Test boolean logic: `and`, `or`, `not`, nested combinations
- Test quantifiers: `any`, `all`, `no`, `count` with various selectors
- Test property access: `space.row`, `piece.owner`
- Test that malformed expressions produce clear error messages

### 11.3 Per-Game Correctness Tests

For each of the 4 starter games:

**Tic-Tac-Toe:**
- Legal moves from empty board = 9 spaces
- After center move, legal moves = 8
- Detect horizontal, vertical, and diagonal wins
- Detect draw on full board
- Known game sequences produce expected outcomes

**Connect Four:**
- Legal moves from empty board = 7 columns
- Gravity: piece placed in column lands at bottom
- Full column is not a legal move
- Detect 4-in-a-row in all orientations
- Draw when all 42 spaces filled

**Mancala:**
- Initial state: 4 stones in each of 12 pits, 0 in stores
- Sowing distributes correct number of stones
- Extra turn when last stone lands in own store
- Capture when last stone lands in empty own-side pit
- Game ends when one side is empty
- Final score counts all remaining stones correctly

**Reversi:**
- Initial state: 4 discs in center
- First player has exactly 4 legal moves
- Placing flips correct discs in all directions
- Pass when no legal moves
- Game ends when neither player can move
- Score counts correctly

### 11.4 Round-Trip Tests

For each game: parse the constrained English → produce GDL → load into engine → play a known game sequence → verify outcome matches expected result. This tests the full pipeline.

### 11.5 Property-Based Tests (Hypothesis)

Using the `hypothesis` library:
- **Invariant:** Any legal move applied to a valid state produces a valid state
- **Invariant:** Terminal states have no legal moves (or legal moves don't change the terminal result)
- **Invariant:** Legal move count is non-negative
- **Invariant:** State hash is deterministic (same state always produces same hash)

---

## 12. Phase 0 Decision Summary

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Rule input format | Constrained English | Keeps project aligned with research vision from day one |
| 2 | GDL schema | Data-driven declarative JSON | Best fit for parser output, correction handling, inspectability, serialization |
| 3a | Language | Pure Python | Target is basic competency, not deep search. Python is adequate. |
| 3b | Parsing | Hand-rolled + Lark | NLP-ish top level, formal grammar for expressions |
| 3c | Logic | Pure Python (no Prolog) | Data-driven GDL makes logic engine unnecessary |
| 3d | Frontend | React web demo | User knows React; existing patterns to follow |
| 4 | Initial games | TTT, Mancala, Connect Four, Reversi | Cover grid + track boards, varied mechanics, recognizable games |
| 5 | Dev infra | Monorepo, pytest + hypothesis | Simple for solo project, property-based tests for engine invariants |
| 6 | Visualization | Minimal React from Phase 1 | Visual feedback from day one without large frontend investment |
| 7 | Design document | This file + example GDL JSONs | Schema validated through worked examples |
