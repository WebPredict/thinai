# ThinAI Stretch Goals: Rulebook → Novel Game Pipeline

The ultimate goal: paste a real game's rulebook and have ThinAI parse, train, and play it correctly. This document tracks what works and what's missing for each game if treated as a novel game (parsed from English, not hand-crafted).

---

## Checkers

**What would parse correctly:**
- 8x8 board detection
- Diagonal forward movement
- Jump capture (basic)
- Win condition: capture all or no legal moves

**What's missing:**
- Dark squares only placement (currently fills all squares)
- 3 rows of pieces per player (currently does 2)
- Mandatory capture rule ("must jump if available")
- Multi-jump chains (keep jumping if another capture available)
- Kinging: piece promotion when reaching back row
- King movement: backward diagonal movement for kings only
- No piece-type system (piece vs king)

**Gap category:** Piece state/promotion, mandatory moves, multi-step turns

---

## Uno

**What would parse correctly:**
- Card game with zones (deck, hands, discard)
- Deal 7 cards, flip 1 to start discard
- Match by color or number (maps to Crazy Eights engine)
- Draw when can't play
- Win by emptying hand

**What's missing:**
- Action card effects (Skip, Reverse, Draw Two)
- Wild cards (play anytime, choose color)
- Wild Draw Four (draw 4 + choose color)
- Specific deck composition (108 cards, 4 colors, 0-9 + actions)
- Direction of play / reverse mechanic
- "Uno" call challenge rule
- Card point values for scoring variant

**Gap category:** Conditional card effects, deck composition, direction of play

---

## Connect Four

**What would parse correctly:**
- Grid board detection (6x7 or similar)
- "4 in a row" win condition
- Draw when board full
- Column-based placement (gravity/drop)

**What's missing:**
- Gravity mechanic: "drop" into lowest empty row of a column. Parser detects "drop"/"falls"/"column" keywords but the novel game engine uses generic placement, not gravity. Would need `gravity_place` effect that finds the lowest empty cell in the chosen column.
- Without gravity, pieces could be placed anywhere on the grid — fundamentally changes the game

**Gap category:** Gravity/physics constraint on placement

---

## Gin Rummy

**What would parse correctly:**
- Card game with deck, hands, discard
- Deal 10 cards each
- Draw from deck or discard pile
- Win by emptying hand / knocking

**What's missing:**
- Meld detection (3+ of same rank, or 3+ consecutive same suit)
- Deadwood calculation (cards not in melds, sum of values)
- Knock threshold (can only knock when deadwood <= 10)
- Gin bonus (knock with 0 deadwood)
- Layoff rule (opponent can add to your melds when you knock)
- Undercut rule (opponent has lower deadwood = they win)
- Round vs game scoring
- The draw/discard two-phase turn (draw one, then discard one)

**Gap category:** Complex card evaluation (melds), multi-phase turns, scoring rules

---

## Backgammon

**What would parse correctly:**
- Track/race board type
- Dice rolling
- Win by bearing off all pieces
- Basic movement along track

**What's missing:**
- 24-point board with specific starting positions (not a simple linear track)
- Two dice with independent moves (move one piece by die1 AND another by die2, or one piece by both)
- Direction: players move in opposite directions on the same board
- Hitting: landing on a single opponent piece sends it to the bar
- Bar re-entry: must re-enter from bar before moving other pieces
- Bearing off rules: all pieces must be in home quadrant first
- Doubles: rolling doubles gives 4 moves instead of 2
- Blocked points: can't land on a point with 2+ opponent pieces

**Gap category:** Complex dice mechanics, bidirectional movement, bar/re-entry, bearing off rules

---

## Reversi / Othello

**What would parse correctly:**
- 8x8 grid board
- Flanking/flipping mechanic (detected via "flip", "surround", "sandwich")
- Win: most pieces when no moves remain

**What's missing:**
- Starting position: 4 pieces in center (2 per player, diagonal) — parser would need to detect "start with 4 pieces in center"
- Must place adjacent to opponent AND flank — the flanking rule is handled by the engine but a novel parse might not connect placement + flanking correctly
- Pass when no legal moves (but opponent continues) — parser assumes alternating turns, doesn't handle pass-and-continue
- Game ends when NEITHER player can move, not just one

**Gap category:** Specific starting positions, pass-when-stuck turn logic, dual-stalemate end condition

---

## Summary: Common Infrastructure Gaps

| Gap | Games Affected | Difficulty |
|-----|---------------|------------|
| Piece promotion / state changes | Checkers, card upgrades | Hard |
| Mandatory move rules | Checkers | Medium |
| Multi-step turns | Checkers (multi-jump), Gin Rummy (draw+discard) | Medium |
| Gravity placement | Connect Four | Easy |
| Conditional card effects | Uno (Skip, Reverse, Draw 2/4) | Medium |
| Deck composition specification | Uno | Easy |
| Complex dice (two independent dice, doubles) | Backgammon | Hard |
| Bidirectional movement on shared board | Backgammon | Hard |
| Bar/re-entry mechanics | Backgammon | Hard |
| Meld detection and scoring | Gin Rummy | Hard |
| Pass-when-stuck turn logic | Reversi | Easy |
| Specific starting positions (not just "fill rows") | Reversi, Backgammon | Medium |

### Completed:
- ✅ **Gravity placement** — Connect Four works as novel game
- ✅ **Pass-when-stuck** — Reversi-like games work
- ✅ **Specific starting positions** — flanking gets center 4, movement fills rows
- ✅ **Mandatory capture** — jumps override regular moves in movement engine
- ✅ **Piece promotion** — reaches back row → king with backward movement
- ✅ **Deck composition** — Uno-style deck auto-detected
- ✅ **Card special powers** — wild/skip/reverse/draw detected and routed

### Remaining easiest wins:
1. **Conditional card effects** — unblocks Uno action cards for novel games
2. **Multi-step turns** — unblocks draw-then-play, jump chains
3. **Piece inventory** — "each player has N pieces" support
4. **Dark square placement** — checkerboard pattern for Checkers

---

## Demo & Training Experience

### Visual training replay ("War Games" mode)
Watch the AI play training games in real-time with the actual board graphics, pieces moving, cards being played — at adjustable speed (1x to 10x). Instead of just a learning curve graph, users see the AI literally learning: early games are clumsy, later games show strategy emerging.

**Implementation approach:**
- Stream game states from training loop via SSE (Server-Sent Events)
- Frontend renders each state in the existing board components
- Speed slider controls delay between moves (50ms to 500ms)
- Show game number, current depth, win/loss overlay
- Could run alongside the learning curve graph

**Impact:** The most compelling demo feature. "Watch the AI learn Checkers in 60 seconds" is a shareable moment. War Games reference is perfect positioning.

### Learn from human play
Every game against a human is a training signal. An optional "Allow ThinAI to learn from this game" toggle that feeds the game trace into weight updates after the game ends.

**Implementation approach:**
- After game over, if toggle is on, collect the feature trace (already recorded during play)
- Call `evaluator.update_weights(trace, outcome)` with the game result
- Save updated weights to memory store
- Show "ThinAI learned from this game" message
- Generation counter increments, learning curve extends

**Impact:** Creates a flywheel — the more people play, the better the AI gets. Each human game is higher quality than self-play training. Also means the AI can improve beyond its initial 40-game training ceiling.

**Considerations:**
- Need to prevent adversarial training (intentionally losing to corrupt weights)
- Learning rate should be lower for human games (subtle adjustments, not big swings)
- Could show "confidence change" after each human game
- Works especially well for novel games where the AI starts weak

---

### Canasta Implementation Plan

Canasta is a rummy-style card game focused on melding (3+ of same rank). It requires significant new infrastructure.

**New mechanics needed:**
1. **Meld detection** — identify groups of 3+ same rank in hand
2. **Multi-card play** — lay down multiple cards as a meld in one turn
3. **Wild cards in melds** — 2s and Jokers can substitute in melds (max 1 wild per 2 naturals)
4. **Discard pile pickup** — take entire discard pile if top card matches a meld or pair in hand
5. **Frozen pile** — wild card or black 3 on discard freezes it (can only pick up with natural pair)
6. **Going out** — requires at least one canasta (7 of a kind), must ask partner in 4-player
7. **Scoring** — natural canasta: 500, mixed: 300, cards: face value, going out bonus: 100

**Implementation order:**
1. `engine/gdl/melds.py` (~150 LOC) — meld detection, validation, scoring
   - `find_melds(hand)` → list of valid meld groups
   - `is_valid_meld(cards)` → bool (3+ same rank, wild card limits)
   - `score_melds(melds)` → points
   - `is_canasta(meld)` → bool (7+ cards)

2. Multi-phase turn system (~100 LOC) — draw phase → meld phase → discard phase
   - New turn structure: `phases: ["draw", "meld", "discard"]`
   - Player draws 2 cards (or picks up discard pile)
   - Player optionally lays down melds
   - Player discards 1 card

3. `engine/games/examples/canasta.json` (~80 LOC) — GDL with:
   - Double deck (108 cards: 2×52 + 4 jokers)
   - Zones: deck, hand_p1, hand_p2, melds_p1, melds_p2, discard
   - State vars: frozen_pile, has_canasta_p1/p2, etc.

4. Canasta-specific features (~50 LOC):
   - `meld_progress` — cards close to forming melds
   - `canasta_count` — completed canastas
   - `wild_card_count` — 2s and Jokers in hand
   - `discard_pile_value` — incentive to pick up large piles

5. UI: MeldBoard component (~120 LOC) — show melds on table, hand, discard pile

**Estimated total:** ~500 LOC, 1-2 sessions
**Dependencies:** Meld system would also unblock Gin Rummy as a novel game
**Priority:** Medium — significant work but unlocks a whole game category (rummy family)

---

### Strategy hints from user ("teach the kid")
The user tells the AI what to pay attention to in plain English, like an adult teaching a kid: "Try to control the center" or "Don't leave single pieces exposed" or "Save high cards for later rounds."

**Implementation approach:**
- Text field on the training page: "Any strategy tips? (optional)"
- Parser matches hint keywords to existing feature names:
  - "center" → boost `center_control` prior
  - "high cards later" / "save" → boost `card_conservation` prior
  - "single pieces" / "exposed" / "blot" → boost `exposed_singles` or `blot_safety` prior
  - "corners" → boost `corner_presence` prior
  - "lines" / "rows" → boost `line_threats` prior
  - "pieces" / "advantage" / "capture" → boost `piece_advantage` prior
  - "block" / "opponent" → boost blocking-related features
- Matched features get their auto-prior boosted (e.g., 0.1 → 0.5+)
- AI starts training with that bias and refines through play
- Multiple hints supported: "Control center, don't leave single pieces"

**Impact:** Addresses the novel game strategy depth problem without more compute. The AI doesn't need 40 games to discover "center matters" if the user says so. Mirrors how humans actually learn games — someone explains what's important before you start playing.

**Example flow:**
1. User parses: "8x8 board. Move diagonally. Jump to capture."
2. User adds hint: "Try to keep your pieces together and control the center"
3. Parser matches: `center_control` prior → 0.5, `adjacency_count` prior → 0.3
4. AI trains with strong center + grouping bias from game 1
5. Training curve starts higher, converges faster

**Estimated effort:** ~50 LOC — keyword matching to feature names + prior boost in auto_priors.py. UI: one text input field on training page.
