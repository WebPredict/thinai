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

### Easiest wins (most games unblocked per effort):
1. **Gravity placement** — unblocks Connect Four as novel game
2. **Pass-when-stuck** — unblocks Reversi as novel game
3. **Specific starting positions** — improves Checkers, Reversi
4. **Mandatory capture** — improves Checkers
5. **Conditional card effects** — unblocks Uno action cards
