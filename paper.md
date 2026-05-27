# ThinAI: Learning Arbitrary Games from Natural Language Rules on a Single Laptop

**Jeff Sanchez** and **Claude** (Anthropic)
High Desert Apps
May 2026

---

## Abstract

We present ThinAI, a system that learns to play arbitrary turn-based games from natural-language rule descriptions using only classical AI techniques on commodity hardware. Given a plain English description of a game's rules, ThinAI parses it into a structured Game Description Language (GDL), automatically generates evaluation features, derives initial weight priors from rule structure, and learns through self-play — all without neural networks, GPUs, or cloud compute. The system achieves competent play across 21 built-in games spanning 13 categories after only 40 training games, compared to the millions required by neural approaches like AlphaZero and MuZero. We demonstrate that structured knowledge representation, automatic feature discovery, and classical search with learned evaluation can match or exceed the sample efficiency of deep learning approaches for a broad class of games, while maintaining full interpretability of the AI's decision-making process. The system handles perfect-information board games, hidden-information card games, dice-based games with stochastic elements, and novel games described by users in real time.

## 1. Introduction

The quest to build game-playing AI has produced remarkable results: Deep Blue defeated the world chess champion in 1997, AlphaGo defeated the world Go champion in 2016, and AlphaZero mastered chess, shogi, and Go from self-play alone in 2017. These systems demonstrate superhuman performance — but at extraordinary computational cost. AlphaZero required 5,000 TPUs and millions of training games per game type. MuZero extended this to learn without knowing game rules, but with similar compute requirements.

A natural question arises: *is all that compute necessary?* For the goal of competent (not superhuman) play across a wide variety of games, can classical AI techniques — search, evaluation learning, and structured representation — achieve comparable results at a fraction of the cost?

ThinAI explores this question by combining several ideas:

1. **Natural language parsing** — game rules are described in plain English and automatically converted to a formal representation, eliminating the need for manual game implementation.
2. **Automatic feature discovery** — evaluation features are generated from the game's rule structure, not hand-coded per game.
3. **Prior knowledge from rules** — initial feature weights are derived from the game's structure (e.g., "line-based win condition implies lines matter"), giving the learner a head start analogous to human intuition.
4. **Sample-efficient self-play** — the system reaches competent play in 20–40 training games using progressive depth, graduated opponents, and temporal difference learning.

The result is a system that runs on a single laptop, handles 21 games across 13 categories, and can learn novel games described by users in real time — while every decision remains fully interpretable through explicit feature weights and search traces.

## 2. Related Work

### 2.1 General Game Playing

The General Game Playing (GGP) competition, established by Genesereth et al. (2005), pioneered the idea of AI systems that play arbitrary games from formal rule descriptions. GGP systems receive rules in the Stanford Game Description Language (GDL) and must play without game-specific knowledge. Notable systems include CadiaPlayer (Björnsson and Finnsson, 2009), which combined UCT search with simulation-based evaluation, and Sancho (Draper and Rose, 2014). ThinAI differs from traditional GGP in two key ways: it accepts natural language instead of formal GDL, and it learns evaluation functions through self-play rather than relying solely on search.

### 2.2 Neural Game Learning

AlphaZero (Silver et al., 2018) demonstrated that a single architecture — deep neural network combined with Monte Carlo Tree Search (MCTS) — could master chess, shogi, and Go from self-play alone. MuZero (Schrittwieser et al., 2020) extended this to learn without knowing game rules, building an internal model of game dynamics. While these systems achieve superhuman performance, they require millions of training games, thousands of TPUs, and produce opaque neural evaluations. ThinAI trades peak performance for sample efficiency, interpretability, and accessibility.

### 2.3 Feature-Based Game Evaluation

Classical game AI relies on hand-crafted evaluation functions — weighted sums of features like material advantage, piece mobility, and board control. Temporal difference learning (Sutton, 1988) can tune these weights automatically, as demonstrated by Samuel's checkers player (1959) and TD-Gammon (Tesauro, 1995). ThinAI extends this tradition by automating feature *generation* as well as weight learning, enabling zero-knowledge play of novel games.

## 3. System Architecture

ThinAI consists of five main components: a natural language parser, a game engine, an automatic feature generator, a search-based reasoner, and a self-play training system.

### 3.1 Natural Language Parser

The parser converts plain English game descriptions into a JSON-based Game Description Language (GDL). It uses pattern matching across 13 game categories to identify:

- **Board structure**: grid dimensions, hex grids, track/race paths, card zones
- **Piece vocabulary**: ~350 recognized game objects (pieces, cards, dice) with 58 SVG icons
- **Win conditions**: line completion, territory control, elimination, scoring, race-to-finish
- **Movement mechanics**: orthogonal, diagonal, all-direction, forward-only, with jump capture
- **Card mechanics**: matching/shedding, trick-taking, collecting, comparing, melding
- **Turn structure**: alternating, conditional (extra turns), multi-phase (draw → meld → discard)

The parser does not use a language model — it operates through keyword detection, structural analysis, and heuristic matching. When ambiguities arise (e.g., board size unspecified, setup unclear), the system generates clarification questions for the user.

**Example**: The input *"Two players take turns placing stones on a 7×7 grid. Connect your stones from one side of the board to the other to win."* produces a GDL spec for Hex with a 7×7 grid, alternating placement, and connection-based win condition.

### 3.2 Game Engine

The engine loads any GDL specification and provides:

- **State management**: board positions, card zones (with visibility control), state variables
- **Legal move generation**: evaluates rule conditions, expands parameter selectors
- **State transitions**: applies rule effects, advances turns (including conditional and multi-phase turns)
- **Terminal detection**: checks end conditions, computes scores

The engine supports diverse board types (grid, hex, track, card zones), piece mechanics (placement, movement, capture, promotion), and card mechanics (drawing, discarding, melding, trick resolution). A single engine instance can run any game without game-specific code.

### 3.3 Automatic Feature Discovery

Feature discovery operates at two levels:

**Level 1 (Rule Structure Analysis)**: At parse time, the system analyzes the GDL to generate features:

- *Line-win games* → `longest_line`, `line_threats`, `center_control`, `open_three`
- *Capture games* → `piece_advantage`, `king_count`, `advancement`
- *Card games* → `hand_size`, `near_sets`, `wild_card_count`
- *Race games* → `position_lead`, `distance_to_finish`
- *Territory games* → `territory_count`, `connection_progress`

**Level 2 (Correlation Discovery)**: At training game 10, the system analyzes play data to discover additional features. For each candidate feature, it computes correlation with game outcomes across completed games. Features with significant positive or negative correlation are added to the evaluation function.

### 3.4 Auto-Priors

Before any training games are played, the system derives initial feature weight biases from rule structure — analogous to a human's intuition about what matters in a new game:

- Line-win games: `center_control` starts at 0.2, `longest_line` at 0.5
- Capture games: `piece_advantage` starts at 0.15
- Card conservation: escalating-stakes card games get `card_conservation` at 0.5
- User hints: plain-English advice (e.g., "control the center") is matched against ~25 keywords and boosts corresponding feature weights

These priors break the "cold start" problem — the first training game already has a reasonable evaluation, rather than playing randomly.

### 3.5 Search and Evaluation

The reasoner uses negamax search with alpha-beta pruning:

- **Depth 1–2**: All legal moves are considered
- **Depth 3+**: Selective deepening — only the top 8 moves (scored by quick evaluation) are explored, pruning the branching factor for large boards
- **Node budget**: 2,000 nodes for board games, 1,500 for card games
- **Adaptive effort**: search depth adjusts per position based on branching factor and time budget
- **Sampling-based search**: for hidden-information card games, the system samples possible opponent hands and evaluates moves across multiple possible worlds

The evaluation function is a linear combination of features:

$$V(s) = \sum_{i} w_i \cdot f_i(s)$$

where $f_i$ are the automatically generated features and $w_i$ are learned weights.

### 3.6 Self-Play Training

Training uses temporal difference (TD) learning with several innovations for stability:

**Progressive depth**: Training starts at depth 1 and increases every 5 games (up to depth 4). This mirrors human learning — develop simple intuitions first, then learn to look further ahead.

**Graduated opponents**: Games 1–10 are played against a random opponent. At game 10, the system takes a snapshot of the current weights and uses it as the opponent for games 11+. This prevents the "nosedive" problem where a learner faces an opponent that's always exactly as strong as itself.

**Learning rate decay**: The learning rate decays 8% after each loss and 5% after each win, with per-update weight changes clamped to ±0.5. This prevents the weight corruption spiral we observed when consecutive losses at higher depth caused catastrophic weight shifts.

**Luck detection**: Pure-luck games are identified through two checks — L0 analyzes the GDL for absence of meaningful player decisions, L1 checks post-training for flat weights and ~50% win rate. Detected games are flagged rather than making false mastery claims.

## 4. Games and Results

### 4.1 Game Coverage

ThinAI supports 21 built-in games across 13 structural categories:

| Category | Games | Key Mechanics |
|----------|-------|---------------|
| Placement | Tic-Tac-Toe, Connect Four | Grid, gravity, line detection |
| Flanking | Reversi | Capture by surrounding |
| Movement/Capture | Checkers | Jump capture, promotion, mandatory capture |
| Sowing | Mancala | Seed distribution, extra turns |
| Take-away | Nim | Pile removal, strategic balance |
| Matching/Shedding | Crazy Eights, Uno | Color/rank matching, action cards |
| Collecting/Melding | Go Fish, Canasta | Set detection, meld system, wild cards |
| Comparing | Blackjack, Five-Card Draw, War | Hand ranking, hit/stand |
| Trick-taking | Hearts, Wizard, Spades | Trump suits, bidding, follow-suit |
| Race | Chutes & Ladders, Backgammon | Dice, track movement, bearing off |
| Territory | Hex | Connection, side-to-side |
| Word/Tile | Scrabble | Word placement, bonus squares |
| Rummy | Gin Rummy | Deadwood, knocking, melds |

### 4.2 Training Efficiency

The system reaches competent play in 20–40 training games for board games and 30–50 for card games. Total training time ranges from 30 seconds (Tic-Tac-Toe) to 5 minutes (Scrabble).

| Game | Training Games | Training Time | Late Win Rate vs Opponent |
|------|---------------|---------------|--------------------------|
| Reversi | 40 | ~2 min | 65–75% vs self-snapshot |
| Connect Four | 40 | ~90 sec | 60–70% vs self-snapshot |
| Mancala | 30 | ~60 sec | 70–80% vs self-snapshot |
| Checkers | 40 | ~3 min | 55–65% vs self-snapshot |
| Go Fish | 30 | ~45 sec | 70%+ vs random |
| Blackjack | 20 | ~30 sec | Learns basic strategy |
| Hex | 40 | ~2 min | 55–65% vs self-snapshot |

For comparison, AlphaZero requires approximately 700,000 training games for chess and 5 million for Go.

### 4.3 Novel Game Pipeline

Users can describe new games in English and the system handles them end-to-end:

1. **Parse**: English → GDL (pattern matching across 13 categories)
2. **Clarify**: System asks about ambiguities (board size, setup, draw conditions)
3. **Generate features**: L1 rule analysis → candidate features with priors
4. **Train**: 40 games of self-play with progressive depth
5. **Play**: User plays against the trained AI with full UI

Successfully tested novel game types include: custom N-in-a-row variants (3-in-a-row on 4×4, 5×5), custom grid sizes (4-in-a-row on 5×5, 6×6), movement/capture games with custom rules, card matching games with custom decks, and dice race games with custom track layouts.

### 4.4 Interpretability

Every AI decision is traceable:

- **Feature weights**: The learned evaluation function is a weighted sum of named features (e.g., `center_control: 0.34, piece_advantage: 0.62`)
- **Move commentary**: After each move, the system explains why (e.g., "Blocked opponent's 3-in-a-row threat")
- **Confidence reporting**: The AI reports its confidence level (certain/confident/uncertain/guessing) based on score margins and move alternatives
- **Training replay**: Users can watch visual replays of training games, seeing the AI's progression from clumsy to competent play

## 5. Key Innovations

### 5.1 From Rules to Features to Priors

The pipeline from natural language → GDL → features → priors is, to our knowledge, novel. Traditional GGP systems receive formal rules and use search without learned evaluation. Neural systems learn evaluation but require millions of games. ThinAI bridges the gap: it extracts structural knowledge from the rules to bootstrap the evaluation function, then refines it through a small number of training games.

### 5.2 Progressive Depth with Graduated Opponents

The combination of progressive depth (start shallow, deepen over time) with graduated opponents (random → self-snapshot) solves a practical problem in self-play training: the "nosedive" where deeper search against a matched opponent leads to weight corruption. By separating depth progression from opponent difficulty, the system learns stable evaluation functions across all 21 games.

### 5.3 Generic Game Mechanics

Rather than implementing each game independently, ThinAI provides composable building blocks:

- **Generic meld system**: configurable sets/runs with wild cards, minimum sizes, and scoring bonuses — used by Canasta, Gin Rummy, and available for novel games
- **Generic movement engine**: orthogonal/diagonal/all-direction movement with jump capture, mandatory capture, and piece promotion
- **Multi-phase turns**: configurable phase sequences (draw → meld → discard) with automatic phase advancement
- **Sampling-based search**: handles any hidden-information game by sampling possible hidden states

These building blocks compose: a novel game might combine grid movement with multi-phase turns, or card matching with meld detection. The parser identifies which building blocks a game needs and wires them together.

### 5.4 Luck Detection

Automatically identifying pure-luck games prevents the system from making false claims about learning or mastery. The two-level check (rule analysis + post-training signal) correctly identifies War and Chutes & Ladders as luck-based while avoiding false positives on games with significant luck components but meaningful strategy (Backgammon, card games).

## 6. Limitations

**Playing strength**: ThinAI aims for competent play, not superhuman performance. Against expert human players in games like Checkers or Connect Four, the AI can be beaten by someone who understands deep tactical patterns. The linear evaluation function cannot capture complex positional concepts that neural networks learn.

**Parser coverage**: The natural language parser handles ~85% of the 50 most popular tabletop games. It struggles with: partnership dynamics (Bridge, Tichu), complex conditional effects ("when you land on a red space, draw a card"), multi-die mechanics (Backgammon's two independent dice with doubles), and negotiation-based games.

**Novel game depth**: While novel games work end-to-end, the auto-generated features are often shallower than hand-crafted ones. Games requiring deep strategic concepts (territory influence in Go, tempo in chess) are beyond the current feature vocabulary.

**Card game variance**: Hidden-information card games have inherently high variance. The sampling-based search helps but cannot eliminate the uncertainty from unknown opponent hands, leading to inconsistent play quality.

**Evaluation linearity**: The linear feature combination cannot represent feature interactions (e.g., "center control is more valuable when you also have piece advantage"). A polynomial or neural evaluation would be more expressive but harder to interpret.

## 7. Future Work

- **Deeper parser**: Auto-detect meld keywords, multi-phase turns, and complex card effects in novel game descriptions
- **Partnership games**: Multi-agent cooperation model for team games (Bridge, Euchre)
- **Learn from human play**: Adjust feature weights based on human move choices during gameplay
- **Feature interactions**: Explore polynomial evaluation functions or shallow networks while maintaining interpretability
- **Deployment with pre-trained weights**: Ship trained models for all 21 built-in games so users experience strong play immediately

## 8. Conclusion

ThinAI demonstrates that classical AI techniques — search, learned evaluation, and structured knowledge representation — remain viable and competitive for general game playing when the goal is competent play across diverse games rather than superhuman performance on a single game. The system's ability to parse natural language rules, automatically generate evaluation features, and learn from just 40 games of self-play represents a fundamentally different tradeoff than neural approaches: less raw strength, but vastly more sample-efficient, interpretable, and accessible.

The key insight is that *structured knowledge about games* — extracted from rules rather than learned from millions of examples — dramatically reduces the data and compute required. A system that understands "this is a line-win game, so lines probably matter" starts from a much stronger position than one that must discover this from scratch through play alone.

We believe this approach has practical applications beyond game AI: any domain where rules are known, features can be derived from structure, and interpretability matters — from scheduling to resource allocation to protocol verification — could benefit from similar techniques.

---

## References

- Björnsson, Y., & Finnsson, H. (2009). CadiaPlayer: A simulation-based general game player. *IEEE Transactions on Computational Intelligence and AI in Games*.
- Genesereth, M., Love, N., & Pell, B. (2005). General game playing: Overview of the AAAI competition. *AI Magazine*.
- Samuel, A. L. (1959). Some studies in machine learning using the game of checkers. *IBM Journal of Research and Development*.
- Schrittwieser, J., et al. (2020). Mastering Atari, Go, chess and shogi by planning with a learned model. *Nature*.
- Silver, D., et al. (2018). A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play. *Science*.
- Sutton, R. S. (1988). Learning to predict by the methods of temporal differences. *Machine Learning*.
- Tesauro, G. (1995). Temporal difference learning and TD-Gammon. *Communications of the ACM*.
