# ThinAI: Learning Arbitrary Games from Natural Language Rules on a Single Laptop

**Jeff Sanchez** and **Claude** (Anthropic)
High Desert Apps
May 2026

---

## Abstract

How would a person learn to play a brand new game? They would read the rules (possibly incomplete or ambiguous), ask clarifying questions, form some initial intuitions about what might matter, and then improve through a modest number of practice games — all without consulting external references or playing millions of rounds. We present ThinAI, a system designed around these same constraints: it learns to play arbitrary turn-based games from natural-language rule descriptions, asks clarification questions when information is missing, derives initial strategic intuitions from rule structure, and reaches competent play through just 20–50 self-play training games — all on a single laptop without neural networks, GPUs, or cloud compute.

While the system includes 21 well-known built-in games for validation, the primary research contribution is its ability to handle *novel* games: games the system has never seen before, described by users in plain English at runtime. We investigate how far classical AI techniques — structured knowledge representation, automatic feature discovery, and learned evaluation — can extend across the space of possible turn-based games. The system currently covers 13 structural game categories (grid placement, movement/capture, card matching, trick-taking, melding, racing, territory, and more), and we characterize both the breadth of novel games it handles well and the specific mechanical boundaries where it breaks down. Our results suggest that structured knowledge extracted from rules, combined with human-like learning constraints, produces a surprisingly general game-learning system — one that trades peak performance for breadth, sample efficiency, and full interpretability.

## 1. Introduction

Consider how a child learns a new board game. Someone explains the rules — perhaps imperfectly, skipping details they assume are obvious. The child asks questions: "What happens if I land on your piece?" "Do I have to jump if I can?" They form rough intuitions before playing a single game: "controlling the middle probably matters," "having more pieces is probably good." Then, after a handful of games — not thousands, not millions — they play reasonably well. They don't consult strategy guides or study databases of expert play. They just understand the rules, develop intuitions, and learn from experience.

Modern game-playing AI operates under fundamentally different constraints. AlphaZero required 5,000 TPUs and millions of self-play games to master chess. MuZero extended this to learn without explicit rules, but with similar computational requirements. These systems achieve superhuman performance — but they bear little resemblance to how humans actually learn games.

ThinAI asks: *what happens when we impose human-like learning constraints on a game AI system?* Specifically:

1. **Learn from rule descriptions** — the system receives plain English rules, not formal specifications or hardcoded game logic. Rules may be incomplete or ambiguous, just as when a friend explains a new game.
2. **Ask for clarification** — when critical information is missing (board size? starting setup? draw condition?), the system identifies what it doesn't know and asks, rather than guessing or failing silently.
3. **No external resources** — no internet lookups, no strategy databases, no pre-trained models. The system must derive everything from the rules and its own play experience.
4. **Limited practice** — the system must reach competent play in 20–50 training games, not millions. This matches the human scale of "learning over an afternoon."
5. **Basic intuition** — before playing, the system derives initial strategic biases from rule structure, analogous to a human's common-sense intuitions about what might matter in a new game.

These constraints are not limitations to be overcome — they are the research design. We believe they produce a more interesting and general system than one optimized for peak performance on known games.

The primary research question is not "can ThinAI beat AlphaZero at chess?" (it cannot) but rather: *how broad a space of novel games can a system handle when it learns the way a person would?* The 21 well-known built-in games serve as validation, but the core contribution is the novel game pipeline — the system's ability to accept a game description it has never seen before and, within minutes, learn to play it competently.

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

The parser does not use a language model — it operates through keyword detection, structural analysis, and heuristic matching. This is a deliberate design choice: the system demonstrates that structured pattern matching, not statistical language understanding, is sufficient for game rule parsing across a broad category space.

**Clarification system**: When the parser detects missing or ambiguous information, it generates targeted clarification questions — mimicking a human asking "wait, what happens when...?" For example:

- No board size specified → "What size should the board be? (e.g., 6×6, 8×8)"
- Movement game without setup → "How should pieces be arranged? Choose: back two rows / back row only / corners / scattered / custom"
- No draw condition → "What happens if neither player can win? (draw after N moves? play until someone wins?)"
- One color specified for both players → "What color should the second player's pieces be?"

This mirrors the natural process of learning a game from an imperfect explanation — the system identifies what it doesn't know and asks, rather than guessing or failing.

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

### 3.4 Auto-Priors: Artificial Intuition

A human sitting down to a new game doesn't start from zero. Before playing a single round, they have intuitions: "having more pieces is probably good," "the center of the board is probably important," "I probably shouldn't waste my best cards early." These intuitions aren't learned from *this* game — they're transferred from a lifetime of experience with similar games.

ThinAI simulates this with auto-priors: initial feature weight biases derived from rule structure analysis:

- Line-win games: `center_control` starts at 0.2, `longest_line` at 0.5 — because the system recognizes that line completion is the win condition
- Capture games: `piece_advantage` starts at 0.15 — because having more pieces is almost always good in capture games
- Card conservation: escalating-stakes card games get `card_conservation` at 0.5 — because hoarding strong cards for later is a common card game heuristic
- User hints: the system also accepts plain-English strategy advice (e.g., "control the center," "save high cards for later"), matched against ~25 keywords to boost corresponding feature weights — analogous to a friend offering a tip before the first game

These priors break the "cold start" problem — the very first training game already has directional evaluation, rather than playing randomly. They are deliberately weak (easily overridden by training data) but strong enough to give the learner traction from game one.

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

### 4.3 Novel Games: Breadth and Boundaries

The novel game pipeline is the system's primary contribution. Users describe a game in English and the system handles the full lifecycle:

1. **Parse**: English → GDL via pattern matching across 13 game categories
2. **Clarify**: System detects missing information and asks targeted questions (board size, starting setup, draw conditions, piece movement rules)
3. **Generate features**: L1 rule-structure analysis produces candidate evaluation features with initial weight priors
4. **Train**: 20–50 games of self-play with progressive depth and graduated opponents
5. **Play**: User plays against the trained AI with an automatically generated game UI

#### 4.3.1 Successfully Handled Novel Game Types

The following categories of novel games work end-to-end, from English description to competent play:

**Grid placement games** — "Two players alternate placing marks on a 5×5 grid. Get 4 in a row to win." The system detects grid dimensions, line-win conditions, and generates appropriate features (center_control, longest_line, line_threats). Tested with 3-in-a-row on 4×4, 4-in-a-row on 5×5 and 6×6, and custom grid sizes.

**Gravity/column-drop games** — "Drop pieces into a 6×7 grid. They fall to the lowest open space. Connect 4 in a row." Detects "fall"/"drop"/"gravity" keywords and applies column-drop placement. Auto-features include center_control and line_threats.

**Movement and capture games** — "Each player has 8 pieces on a grid. Pieces move diagonally one space. Jump over an opponent's piece to capture it." The generic movement engine handles orthogonal, diagonal, and all-direction movement with jump capture, mandatory capture enforcement, and piece promotion (reaching the back row).

**Flanking/flipping games** — "Place a piece to flip opponent pieces between yours. Player with more pieces wins when the board is full." Detects flanking/surrounding mechanics and generates territory-count features. Pass-when-stuck logic handles positions where one player has no legal moves.

**Card matching/shedding games** — "Each player gets 7 cards. Match the top card by color or number. First to empty their hand wins." Supports custom deck compositions, wild cards, and action cards (Skip, Reverse, Draw Two) when described.

**Dice race games** — "Roll a die and move forward. Land on an opponent to bump them back. First to the end wins." Generates track boards with bumping mechanics and position_lead features.

**Territory/connection games** — "Place stones on a hex grid. Connect your stones from one side to the opposite side to win." Hex-style connection detection with territory and bridge features.

#### 4.3.2 Partially Handled Categories

Some game types work with limitations:

**Card collecting with custom rules** — Basic "ask for cards, collect sets" works, but custom scoring (e.g., "pairs of matching suits score double") requires built-in scoring functions rather than being parseable from descriptions.

**Multi-phase card games** — The generic multi-phase turn system exists (draw → meld → discard) but the parser does not yet auto-detect phase structure from novel descriptions like "draw a card, then optionally play one, then discard."

**Capture games with complex movement** — Simple movement (diagonal, orthogonal) with jump capture works well. But games requiring different movement patterns for different piece types (like chess with distinct knight/bishop/rook movement) exceed the current movement engine.

**Games with conditional effects** — "If you roll doubles, take another turn" works. But arbitrary conditional effects like "when you land on a red space, draw a card and add it to your opponent's hand" cannot be expressed generically.

#### 4.3.3 Current Boundaries

The following game mechanics are beyond the system's current scope for novel games:

- **Partnership/team dynamics** — games where two players cooperate against two others (Bridge, Tichu) require a multi-agent cooperation model
- **Complex multi-die mechanics** — two independent dice where you must allocate each die to a different piece (Backgammon-style) are not parseable for novel games
- **Negotiation and trading** — games involving player-to-player resource exchange (Catan, Monopoly)
- **Real-time elements** — any mechanic requiring simultaneous play or time pressure
- **Deeply compositional rules** — games where rules interact in complex ways ("if you have a red piece adjacent to a blue piece on a corner, your green pieces gain an extra movement point")
- **Spatial reasoning beyond adjacency** — territory influence, area control scoring, or line-of-sight mechanics

#### 4.3.4 Coverage Estimate

Of the structural categories that describe the ~50 most commonly played tabletop and card games, ThinAI's novel game pipeline currently covers approximately:

| Coverage Level | Categories | Examples |
|---------------|------------|----------|
| **Full** (~40%) | Grid placement, column drop, take-away, card matching/shedding, card comparing, dice racing | Tic-Tac-Toe variants, Uno variants, War variants, simple race games |
| **Substantial** (~30%) | Movement/capture, flanking, trick-taking, collecting | Checkers variants, Reversi variants, simple trick games, Go Fish variants |
| **Partial** (~15%) | Territory, melding/rummy, word/tile, bidding | Hex variants, rummy variants (with limitations) |
| **Not covered** (~15%) | Partnership, negotiation, real-time, complex multi-piece movement | Bridge, Catan, Chess, simultaneous-play games |

The key insight is that a relatively small number of composable building blocks — grid placement, card zone management, movement with capture, turn phase sequencing, meld detection, trick resolution — covers a surprisingly large fraction of the design space. Most "new" games are novel combinations of familiar mechanics, and the system's generic building blocks compose well for these cases.

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

ThinAI demonstrates that imposing human-like learning constraints on a game AI system — natural language input, clarification of ambiguities, no external resources, limited practice, and initial intuitions — produces a surprisingly general game-learning system. Rather than pursuing superhuman performance on individual games, the system prioritizes *breadth*: handling novel games across 13 structural categories from English descriptions alone.

The central finding is that a relatively small set of composable building blocks — grid placement, card zone management, movement with capture, turn phase sequencing, meld detection, trick resolution — covers approximately 85% of common tabletop game mechanics. When combined with automatic feature discovery and rule-derived priors, these building blocks enable competent play on novel games after just 20–50 training games, compared to the millions required by neural approaches.

The system's limitations are instructive: it struggles precisely where a human newcomer would also struggle — with games requiring deep positional intuition that takes years to develop, with complex multi-piece interactions that resist simple feature decomposition, and with social mechanics (negotiation, partnership) that depend on modeling other players' intentions rather than board state alone.

We believe the "learn like a kid" framing points toward an underexplored region of the game AI design space. The field has invested heavily in the question "how strong can we make a game AI?" ThinAI asks a complementary question: "how many different games can a single system learn to play reasonably well, starting from nothing but a description of the rules?" The answer — at least for classical turn-based games — appears to be: quite a few.

---

## References

- Björnsson, Y., & Finnsson, H. (2009). CadiaPlayer: A simulation-based general game player. *IEEE Transactions on Computational Intelligence and AI in Games*.
- Genesereth, M., Love, N., & Pell, B. (2005). General game playing: Overview of the AAAI competition. *AI Magazine*.
- Samuel, A. L. (1959). Some studies in machine learning using the game of checkers. *IBM Journal of Research and Development*.
- Schrittwieser, J., et al. (2020). Mastering Atari, Go, chess and shogi by planning with a learned model. *Nature*.
- Silver, D., et al. (2018). A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play. *Science*.
- Sutton, R. S. (1988). Learning to predict by the methods of temporal differences. *Machine Learning*.
- Tesauro, G. (1995). Temporal difference learning and TD-Gammon. *Communications of the ACM*.
