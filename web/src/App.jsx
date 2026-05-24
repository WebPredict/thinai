import { useState, useEffect, useCallback, useRef } from 'react'
import TrainingDashboard from './TrainingDashboard'
import GameBoardRenderer from './boards/GameBoardRenderer'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// Display order: most interesting demos first
const GAME_ORDER = ['reversi', 'connect_four', 'checkers', 'hex', 'backgammon', 'mancala', 'hearts', 'wizard', 'scrabble', 'gin_rummy', 'five_card_draw', 'uno', 'crazy_eights', 'blackjack', 'go_fish', 'war', 'tictactoe', 'nim', 'chutes_and_ladders']

const PLAYER_INDICATOR = {
  tictactoe: { label: 'X', color: '#d4a656' },
  connect_four: { label: 'Red', color: '#cc3333' },
  reversi: { label: 'Black', color: '#333' },
  mancala: { label: 'Bottom row', color: '#d4a656' },
  nim: { label: 'First player', color: '#d4a656' },
  chutes_and_ladders: { label: 'Gold token', color: '#d4a656' },
  checkers: { label: 'Red', color: '#c83030' },
  go_fish: { label: 'Player 1', color: '#d4a656' },
  crazy_eights: { label: 'Player 1', color: '#d4a656' },
  uno: { label: 'Player 1', color: '#d4a656' },
  blackjack: { label: 'Player (vs Dealer)', color: '#d4a656' },
  war: { label: 'Player 1', color: '#d4a656' },
  hex: { label: 'Red (top-bottom)', color: '#c83030' },
  backgammon: { label: 'White', color: '#e8dfd1' },
  hearts: { label: 'Player 1', color: '#d4a656' },
  wizard: { label: 'Player 1', color: '#d4a656' },
  scrabble: { label: 'Player 1', color: '#d4a656' },
  gin_rummy: { label: 'Player 1', color: '#d4a656' },
  five_card_draw: { label: 'Player 1', color: '#d4a656' },
}

const GAME_LABELS = {
  tictactoe: 'Tic-Tac-Toe',
  connect_four: 'Connect Four',
  mancala: 'Mancala',
  reversi: 'Reversi',
  nim: 'Nim',
  chutes_and_ladders: 'Chutes & Ladders',
  checkers: 'Checkers',
  crazy_eights: 'Crazy Eights',
  uno: 'Uno',
  blackjack: 'Blackjack',
  war: 'War',
  go_fish: 'Go Fish',
  hex: 'Hex',
  backgammon: 'Backgammon',
  hearts: 'Hearts',
  wizard: 'Wizard',
  scrabble: 'Scrabble',
  gin_rummy: 'Gin Rummy',
  five_card_draw: 'Five-Card Draw',
}

const GAME_RULES = {
  tictactoe: {
    title: 'How to play Tic-Tac-Toe',
    intro: 'You are X. Place your mark on any empty square.',
    rules: [
      'Take turns placing marks on the 3\u00d73 grid.',
      'Get three of your marks in a row (horizontal, vertical, or diagonal) to win.',
      'If all 9 squares are filled with no winner, it\'s a draw.',
    ],
  },
  connect_four: {
    title: 'How to play Connect Four',
    intro: 'You are Red. Click a column to drop your disc.',
    rules: [
      'Take turns dropping colored discs into the 7-column grid.',
      'Discs fall to the lowest available row in that column.',
      'Get four of your discs in a row (horizontal, vertical, or diagonal) to win.',
    ],
  },
  mancala: {
    title: 'How to play Mancala',
    intro: 'You are Player 1 (bottom row). Your store is on the right.',
    rules: [
      'Click one of your pits to pick up all its stones.',
      'Stones are dropped one-per-pit counter-clockwise, skipping the opponent\u2019s store.',
      'If your last stone lands in your store, you get an extra turn.',
      'If your last stone lands in an empty pit on your side, you capture that stone and all stones in the opposite pit.',
      'The game ends when one side is empty. Remaining stones go to their owner\u2019s store. Most stones wins.',
    ],
  },
  reversi: {
    title: 'How to play Reversi',
    intro: 'You are Black. Place discs to flip the opponent\u2019s pieces.',
    rules: [
      'Place a disc on an empty square that flanks one or more opponent discs in a line.',
      'All flanked opponent discs are flipped to your color.',
      'If you have no legal moves, your turn is skipped.',
      'The game ends when neither player can move. The player with the most discs wins.',
    ],
  },
  nim: {
    title: 'How to play Nim',
    intro: 'Three piles of stones (3, 4, and 5). Take turns removing stones.',
    rules: [
      'On your turn, choose one pile and remove one or more stones from it.',
      'You can only take from a single pile per turn.',
      'The player who takes the last stone wins.',
    ],
  },
  chutes_and_ladders: {
    title: 'How to play Chutes & Ladders',
    intro: 'Race to space 25. Roll the die and hope for ladders!',
    rules: [
      'Roll the die (1\u20136) to move forward that many spaces.',
      'Land on a green ladder space to climb up to a higher square.',
      'Land on a red chute space to slide down to a lower square.',
      'First player to reach space 25 wins.',
    ],
  },
  checkers: {
    title: 'How to play Checkers',
    intro: 'Capture all of your opponent\'s pieces or block them so they can\'t move.',
    rules: [
      'Pieces move diagonally forward, one square at a time.',
      'To capture, jump over an opponent\'s piece to an empty square beyond it.',
      'If you can capture, you must. Multiple captures in one turn are allowed.',
      'When a piece reaches the far row, it becomes a King and can move diagonally in any direction.',
      'You win when your opponent has no pieces left or cannot make a move.',
    ],
  },
  crazy_eights: {
    title: 'How to play Crazy Eights',
    intro: 'Match the top card by suit or rank. First to empty your hand wins!',
    rules: [
      'Each player starts with 7 cards. One card is flipped face-up to start the discard pile.',
      'On your turn, play a card that matches the top of the discard pile by suit or rank.',
      'Eights are wild \u2014 play them on anything and choose the active suit.',
      'If you can\'t play, draw one card from the deck.',
      'First player to play all their cards wins.',
      'If the deck runs out, the player with fewer cards wins.',
    ],
  },
  uno: {
    title: 'How to play Uno',
    intro: 'Match the top card by color or number. First to empty your hand wins!',
    rules: [
      'Each player starts with 7 cards. One card is flipped to start the discard pile.',
      'Play a card matching the top of the discard by color or number.',
      'Skip cards make the opponent lose their turn.',
      'Draw Two cards force the opponent to draw 2 cards.',
      'Wild cards match anything \u2014 choose the active color.',
      'Wild Draw Four: wild + opponent draws 4 cards.',
      'If you can\'t play, draw one card from the deck.',
      'First player to play all their cards wins.',
    ],
  },
  blackjack: {
    title: 'How to play Blackjack',
    intro: 'Get as close to 21 as possible without going over. Beat the dealer!',
    rules: [
      'You get 2 cards face up. The dealer gets 1 up and 1 face down.',
      'Number cards = face value. Face cards (J, Q, K) = 10. Ace = 1 or 11.',
      'Choose "Hit" to draw another card, or "Stand" to keep your total.',
      'If your total exceeds 21, you bust and lose immediately.',
      'After you stand, the dealer reveals their hole card and hits until 17+.',
      'Closest to 21 without busting wins.',
    ],
  },
  go_fish: {
    title: 'How to play Go Fish',
    intro: 'Collect sets of 4 matching cards by asking your opponent for ranks you hold.',
    rules: [
      'Each player starts with 7 cards. The rest form the "pond" (draw pile).',
      'On your turn, ask the opponent for a rank you hold (e.g., "Do you have any 7s?").',
      'If they have any, they give ALL cards of that rank to you. You go again!',
      'If they don\'t, they say "Go Fish" \u2014 you draw from the pond.',
      'If the drawn card matches what you asked for, you get another turn.',
      'When you collect all 4 of a rank, it becomes a completed set.',
      'The game ends when all 13 sets are complete. Most sets wins.',
    ],
  },
  war: {
    title: 'How to play War',
    intro: 'A card game of luck! Each player flips their top card \u2014 higher rank wins.',
    rules: [
      'The deck is dealt evenly between two players.',
      'Each round, both players flip their top card.',
      'Higher rank wins both cards (Ace is highest).',
      'On a tie: each player places 3 cards face-down, then flips a 4th. Higher 4th card wins all.',
      'First player to collect all 52 cards wins.',
    ],
  },
  backgammon: {
    title: 'How to play Backgammon',
    intro: 'Race your 15 checkers around the board and bear them off before your opponent!',
    rules: [
      'Roll two dice each turn. Move checkers by the die values (each die is a separate move).',
      'White (you) moves from high-numbered points toward 1. Black (AI) moves toward 24.',
      'You can land on empty points, your own points, or points with a single opponent checker (hit).',
      'Hit checkers go to the bar and must re-enter before making other moves.',
      'When all your checkers are in your home area (points 1-6), you can bear them off.',
      'First player to bear off all 15 checkers wins.',
    ],
  },
  hex: {
    title: 'How to play Hex',
    intro: 'Connect your two sides of the board! Red connects top-to-bottom, Blue connects left-to-right.',
    rules: [
      'Players take turns placing one stone on any empty hex.',
      'Red (you) wins by connecting the top edge to the bottom edge.',
      'Blue (AI) wins by connecting the left edge to the right edge.',
      'Connections can follow any path through adjacent hexes (6 neighbors each).',
      'There are no draws in Hex \u2014 one player must win.',
    ],
  },
  hearts: {
    title: 'How to play Hearts',
    intro: 'Avoid taking hearts and the Queen of Spades! Lowest score wins.',
    rules: [
      'Each player gets 13 cards. The player with the 2 of clubs leads the first trick.',
      'Players must follow the lead suit if they can. If they can\u2019t, they may play any card.',
      'The highest card of the lead suit wins the trick. The winner leads the next trick.',
      'Each heart taken = 1 point. Queen of Spades = 13 points.',
      'Hearts cannot be led until a heart has been played on a previous trick ("broken").',
      'After all 13 tricks, the player with fewer points wins.',
    ],
  },
  wizard: {
    title: 'How to play Wizard',
    intro: 'Predict exactly how many tricks you\'ll win! Accuracy is rewarded, mistakes are punished.',
    rules: [
      'Each round, 5 cards are dealt and one card is flipped to set the trump suit.',
      'First, each player bids how many of the 5 tricks they think they\'ll win (0-5).',
      'Then 5 tricks are played. You must follow the lead suit if you can.',
      'Trump cards beat any non-trump card. Highest card of the lead suit wins otherwise.',
      'Scoring: if you win exactly your bid, you get 20 + 10\u00D7tricks. If you miss, you lose 10 per trick off.',
      'The game lasts 5 rounds. Highest cumulative score wins.',
    ],
  },
  scrabble: {
    title: 'How to play Scrabble',
    intro: 'Place words on the board using your letter tiles. Highest score wins!',
    rules: [
      'Each player has a rack of 5 letter tiles drawn from a bag.',
      'On your turn, place a word on the board connecting to existing tiles (first word must cross the center star).',
      'All words formed (including cross-words) must be valid English words.',
      'Score = sum of letter values. Bonus squares multiply letter or word scores.',
      'DL = Double Letter, TL = Triple Letter, DW = Double Word, TW = Triple Word.',
      'After placing, you draw tiles to refill your rack to 5.',
      'You may pass if you can\'t or don\'t want to play. Game ends when both players pass or the bag is empty and someone uses all tiles.',
    ],
  },
  gin_rummy: {
    title: 'How to play Gin Rummy',
    intro: 'Form melds (sets and runs) to reduce your deadwood. Knock when you\u2019re ready!',
    rules: [
      'Each player is dealt 10 cards. One card is turned up to start the discard pile.',
      'On your turn: draw from the deck or the discard pile, then discard one card.',
      'Form melds: sets of 3\u20134 same rank, or runs of 3+ sequential same suit.',
      'Knock when your unmelded cards (deadwood) total 10 or less. Gin = 0 deadwood.',
      'Face cards = 10 points, Ace = 1, number cards = face value.',
      'Lower deadwood wins. If the defender has less deadwood, it\u2019s an undercut!',
    ],
  },
  five_card_draw: {
    title: 'How to play Five-Card Draw',
    intro: 'Draw poker \u2014 make the best 5-card hand!',
    rules: [
      'Each player is dealt 5 cards.',
      'Select up to 3 cards to discard, then draw replacements from the deck.',
      'Click cards to select them for discard, then click "Done Discarding".',
      'After both players draw, hands are revealed. Best poker hand wins.',
      'Hand rankings: High Card < Pair < Two Pair < Three of a Kind < Straight < Flush < Full House < Four of a Kind < Straight Flush.',
    ],
  },
}

function ParserReference({ onClose }) {
  const categories = [
    { name: 'Grid Placement', desc: 'Place pieces on a grid to form lines, surround territory, or control area', examples: ['5×5 grid, 4 in a row to win', 'Place stones, surround opponent pieces to capture'], keywords: 'grid, board, row, column, diagonal, place, in a row, surround, capture' },
    { name: 'Flanking / Reversi', desc: 'Place pieces to flip opponent pieces between yours', examples: ['Flip opponent pieces by surrounding them'], keywords: 'flip, sandwich, surround, flank, convert, reversi, othello' },
    { name: 'Nim / Take-away', desc: 'Remove objects from piles; last to take wins or loses', examples: ['3 piles of 5 stones, take 1-3 per turn'], keywords: 'pile, heap, take, remove, last, stones, sticks, objects' },
    { name: 'Card — Matching / Shedding', desc: 'Match cards by suit or rank, first to empty hand wins', examples: ['Match by suit or rank, draw if you can\'t play'], keywords: 'match, suit, rank, hand, draw, discard, wild, skip, reverse' },
    { name: 'Card — Collecting', desc: 'Ask for cards, collect sets', examples: ['Ask for ranks, collect sets of 4'], keywords: 'ask, collect, set, book, pairs, fish' },
    { name: 'Card — Comparing', desc: 'Compare cards head-to-head, highest wins the round', examples: ['Each player flips a card, highest wins'], keywords: 'compare, higher, lower, flip, war, battle, score, points' },
    { name: 'Card — Trick-taking', desc: 'Play cards in tricks, follow suit, avoid or collect points', examples: ['Follow suit, avoid hearts and Queen of Spades'], keywords: 'trick, follow suit, lead, trump, hearts, spades, avoid' },
    { name: 'Dice Placement', desc: 'Roll a die, place in a constrained position based on the roll', examples: ['Roll a die, place in that row, 3 in a row wins'], keywords: 'roll, die, dice, place, row, column' },
    { name: 'Tile Placement', desc: 'Place multi-cell tiles (L-shapes, dominoes) on a grid', examples: ['Place L-shaped tiles on a 6×6 grid, fill a row to win'], keywords: 'tile, L-shape, domino, covers, tetris, block' },
    { name: 'Race / Track', desc: 'Roll dice and race to the finish line, with optional bumping', examples: ['Roll a die, race to space 20, bump opponents back to start'], keywords: 'race, track, finish line, reach the end, forward, backward, bump, roll' },
    { name: 'Movement / Capture', desc: 'Move pieces on a board, capture by jumping', examples: ['Pieces move diagonally, jump to capture'], keywords: 'move, jump, capture, diagonal, hop, slide, checkers' },
    { name: 'Sowing (Mancala)', desc: 'Pick up seeds from a pit and distribute around the board', examples: ['Pick up seeds, sow counter-clockwise, most in store wins'], keywords: 'sow, seeds, pit, store, mancala, counter-clockwise' },
  ]

  const pieceWords = [
    'stone', 'disc', 'chip', 'marker', 'token', 'counter', 'checker', 'piece', 'meeple',
    'pawn', 'knight', 'bishop', 'rook', 'queen', 'king',
    'soldier', 'warrior', 'archer', 'general', 'army', 'tank', 'ship', 'cannon',
    'wizard', 'dragon', 'ghost', 'zombie', 'phoenix', 'unicorn', 'fairy', 'goblin',
    'tree', 'flower', 'mushroom', 'seed', 'leaf', 'crystal', 'flame', 'star',
    'coin', 'gem', 'diamond', 'ruby', 'emerald', 'gold', 'treasure', 'crown',
    'robot', 'alien', 'ninja', 'pirate', 'hero', 'villain',
    'car', 'rocket', 'boat', 'plane',
  ]

  const colorWords = ['red', 'blue', 'green', 'white', 'black', 'gold', 'silver', 'purple', 'orange', 'pink', 'crimson', 'emerald', 'amber', 'ivory', 'obsidian']

  const boardStyles = ['checkerboard', 'chessboard', 'wood', 'wooden']

  return (
    <div className="rules-overlay" onClick={onClose}>
      <div className="rules-modal parser-ref-modal" onClick={e => e.stopPropagation()}>
        <div className="rules-modal-header">
          <span className="rules-modal-title">Parser Reference</span>
          <button className="rules-modal-close" onClick={onClose}>&times;</button>
        </div>
        <p style={{ fontSize: '0.9rem', color: 'var(--ink-dim)', lineHeight: 1.5, marginBottom: '1rem' }}>
          ThinAI's parser uses pattern matching (not an LLM) to translate plain English into game definitions.
          Here's what it understands.
        </p>

        <h4 style={{ color: 'var(--accent)', fontFamily: 'Georgia, serif', fontWeight: 400, fontSize: '1.05rem', marginBottom: '0.5rem' }}>Game Types</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '1.25rem' }}>
          {categories.map(cat => (
            <div key={cat.name} style={{ background: 'var(--bg-deep)', borderRadius: '6px', padding: '0.6rem 0.8rem', border: '1px solid var(--rule-dim)' }}>
              <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.85rem', color: 'var(--accent)', marginBottom: '0.2rem' }}>{cat.name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--ink-dim)', marginBottom: '0.3rem' }}>{cat.desc}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--ink-faint)' }}>
                <strong>Keywords:</strong> {cat.keywords}
              </div>
            </div>
          ))}
        </div>

        <h4 style={{ color: 'var(--accent)', fontFamily: 'Georgia, serif', fontWeight: 400, fontSize: '1.05rem', marginBottom: '0.5rem' }}>Piece Vocabulary</h4>
        <p style={{ fontSize: '0.8rem', color: 'var(--ink-dim)', marginBottom: '0.4rem' }}>
          Use any of these words to name pieces — the parser recognizes them and assigns appropriate icons:
        </p>
        <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.75rem', color: 'var(--ink)', lineHeight: 1.8, marginBottom: '1.25rem', background: 'var(--bg-deep)', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid var(--rule-dim)' }}>
          {pieceWords.join(' · ')}
        </div>

        <h4 style={{ color: 'var(--accent)', fontFamily: 'Georgia, serif', fontWeight: 400, fontSize: '1.05rem', marginBottom: '0.5rem' }}>Colors & Cosmetics</h4>
        <p style={{ fontSize: '0.8rem', color: 'var(--ink-dim)', marginBottom: '0.4rem' }}>
          Describe piece colors or board styles:
        </p>
        <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.75rem', color: 'var(--ink)', lineHeight: 1.8, marginBottom: '0.4rem', background: 'var(--bg-deep)', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid var(--rule-dim)' }}>
          <div><strong style={{ color: 'var(--accent)' }}>Colors:</strong> {colorWords.join(' · ')}</div>
          <div style={{ marginTop: '0.3rem' }}><strong style={{ color: 'var(--accent)' }}>Board:</strong> {boardStyles.join(' · ')}</div>
        </div>

        <h4 style={{ color: 'var(--accent)', fontFamily: 'Georgia, serif', fontWeight: 400, fontSize: '1.05rem', marginTop: '1rem', marginBottom: '0.5rem' }}>Tips</h4>
        <ul style={{ fontSize: '0.8rem', color: 'var(--ink-dim)', paddingLeft: '1.2rem', lineHeight: 1.7, margin: 0 }}>
          <li>Specify board size explicitly: "5×5 grid", "7×7 hexagonal board"</li>
          <li>State win conditions clearly: "4 in a row to win", "most pieces wins"</li>
          <li>Mention draw conditions: "if the board is full, it's a draw"</li>
          <li>For card games, mention hand size and deck type</li>
          <li>For race games, mention track length and any bumping rules</li>
          <li>Combine mechanics: "roll a die, then choose to move forward or backward"</li>
        </ul>
      </div>
    </div>
  )
}

function RulesModal({ gameType, onClose, customDescription }) {
  const rules = GAME_RULES[gameType]

  if (!rules && !customDescription) return null

  if (!rules && customDescription) {
    return (
      <div className="rules-overlay" onClick={onClose}>
        <div className="rules-modal" onClick={e => e.stopPropagation()}>
          <div className="rules-modal-header">
            <span className="rules-modal-title">Game Rules</span>
            <button className="rules-modal-close" onClick={onClose}>&times;</button>
          </div>
          <p className="rules-modal-intro">This game was created from the following description:</p>
          <blockquote style={{ fontStyle: 'italic', borderLeft: '3px solid var(--accent)', paddingLeft: '1rem', margin: '1rem 0', color: 'var(--ink)' }}>
            {customDescription}
          </blockquote>
        </div>
      </div>
    )
  }

  return (
    <div className="rules-overlay" onClick={onClose}>
      <div className="rules-modal" onClick={e => e.stopPropagation()}>
        <div className="rules-modal-header">
          <span className="rules-modal-title">{rules.title}</span>
          <button className="rules-modal-close" onClick={onClose}>&times;</button>
        </div>
        <p className="rules-modal-intro">{rules.intro}</p>
        <ol className="rules-modal-list">
          {rules.rules.map((r, i) => <li key={i}>{r}</li>)}
        </ol>
      </div>
    </div>
  )
}

function App() {
  const [games, setGames] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [gameState, setGameState] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedGame, setSelectedGame] = useState('reversi')
  const [mode, setMode] = useState('menu') // 'menu', 'play', or 'train'
  const [learnedGames, setLearnedGames] = useState({})
  const [aiLastMove, setAiLastMove] = useState(null) // highlight AI's last move
  const [aiThinking, setAiThinking] = useState(null) // confidence + effort info from last AI move
  const [showRulesModal, setShowRulesModal] = useState(false)
  const rulesShownRef = useRef({})
  const [showGdlModal, setShowGdlModal] = useState(false)
  const [showParserRef, setShowParserRef] = useState(false)
  const [gdlData, setGdlData] = useState(null)
  const [teachInput, setTeachInput] = useState('')
  const [parseResult, setParseResult] = useState(null)
  const [parseError, setParseError] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [parsedGameId, setParsedGameId] = useState(null)
  const [customDisplayName, setCustomDisplayName] = useState(null)
  const [customGameName, setCustomGameName] = useState('')
  const [clarifications, setClarifications] = useState([])
  const [clarAnswers, setClarAnswers] = useState({})

  const handleParse = async () => {
    if (!teachInput.trim()) return
    setParsing(true)
    setParseResult(null)
    setParseError(null)
    setParsedGameId(null)
    try {
      const res = await fetch(`${API}/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: teachInput }),
      })
      const data = await res.json()
      if (data.gdl) {
        setParseResult(data.gdl)
      }
      if (data.game_id) {
        setParsedGameId(data.game_id)
        refreshGames()
      }
      if (data.clarifications?.length > 0) {
        setClarifications(data.clarifications)
        setClarAnswers({})
      } else {
        setClarifications([])
      }
      if (data.error) {
        setParseError(data.error)
      }
    } catch (e) {
      setParseError('Failed to connect to the parser. Is the backend running?')
    }
    setParsing(false)
  }

  useEffect(() => {
    if ((showGdlModal || showRulesModal) && selectedGame) {
      fetch(`${API}/game/${selectedGame}/gdl`)
        .then(r => r.json())
        .then(setGdlData)
        .catch(() => setGdlData(null))
    }
  }, [showGdlModal, showRulesModal, selectedGame])

  // Fetch which games have been trained
  const refreshLearned = () => {
    fetch(`${API}/memory/games`)
      .then(r => r.json())
      .then(d => {
        const map = {}
        for (const m of (d.games || [])) {
          map[m.game_name] = m
          // Also index by slug so custom games match
          const slug = m.game_name.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/^_+|_+$/g, '')
          map[slug] = m
        }
        setLearnedGames(map)
      })
      .catch(() => {})
  }

  useEffect(() => { refreshLearned() }, [mode])

  const [customGameNames, setCustomGameNames] = useState({})

  const refreshGames = () => {
    fetch(`${API}/games`)
      .then(r => r.json())
      .then(d => {
        // Custom games have {id, name} — extract IDs and store display names
        const customIds = (d.custom_games || []).map(c => typeof c === 'string' ? c : c.id)
        const nameMap = {}
        for (const c of (d.custom_games || [])) {
          if (typeof c === 'object') nameMap[c.id] = c.name
        }
        setCustomGameNames(prev => ({ ...prev, ...nameMap }))

        const all = [...d.games, ...customIds]
        const sorted = all.sort((a, b) => {
          const ai = GAME_ORDER.indexOf(a), bi = GAME_ORDER.indexOf(b)
          return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
        })
        setGames(sorted)
      })
      .catch(() => setGames(GAME_ORDER))
  }

  useEffect(() => { refreshGames() }, [])

  const startGame = useCallback(async (gameOverride) => {
    const game = gameOverride || selectedGame
    console.log('startGame called with:', game, 'selectedGame:', selectedGame)
    setLoading(true)
    try {
      const res = await fetch(`${API}/game/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game,
          ai_player: 'player2',
          ai_depth: {tictactoe: 6, connect_four: 4, mancala: 3, reversi: 2, nim: 4, chutes_and_ladders: 1}[game] || 3,
        }),
      })
      const data = await res.json()
      setSessionId(data.session_id)
      setGameState(data.state)
      if (data.display_name) setCustomDisplayName(data.display_name)
      // Show rules only the first time for each game
      if (!rulesShownRef.current[selectedGame]) {
        setShowRulesModal(true)
        rulesShownRef.current[selectedGame] = true
      }
    } catch (e) {
      console.error('Failed to start game:', e)
      setSessionId(null)
    }
    setLoading(false)
  }, [selectedGame])

  const makeMove = useCallback(async (rule, params) => {
    if (!sessionId || loading) return
    setLoading(true)
    setAiLastMove(null)
    try {
      // Step 1: Apply player's move — show the result immediately
      const res = await fetch(`${API}/game/${sessionId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rule, params }),
      })
      const data = await res.json()
      setGameState(data.state)

      if (data.needs_ai) {
        // AI may get multiple turns (e.g., extra turns in Go Fish)
        let keepGoing = true
        while (keepGoing) {
          await new Promise(r => setTimeout(r, 400))

          const aiStart = Date.now()
          const aiRes = await fetch(`${API}/game/${sessionId}/ai-move`, { method: 'POST' })
          const elapsed = Date.now() - aiStart
          if (elapsed < 400) await new Promise(r => setTimeout(r, 400 - elapsed))
          const aiData = await aiRes.json()
          setGameState(aiData.state)
          if (aiData.ai_move) {
            setAiLastMove(aiData.ai_move)
            setAiThinking({
              confidence: aiData.ai_confidence,
              effort: aiData.ai_effort,
              commentary: aiData.ai_commentary,
            })
            setTimeout(() => setAiLastMove(null), 2500)
          }

          // Check if AI gets another turn
          const nextState = aiData.state
          keepGoing = nextState && !nextState.game_result &&
            nextState.current_player !== 'player1'

          // Safety: max 10 consecutive AI turns
          if (keepGoing) {
            const maxAiTurns = 10
            if (!window._aiTurnCount) window._aiTurnCount = 0
            window._aiTurnCount++
            if (window._aiTurnCount >= maxAiTurns) { keepGoing = false }
          } else {
            window._aiTurnCount = 0
          }
        }
      }
    } catch (e) {
      console.error('Failed to make move:', e)
    }
    setLoading(false)
  }, [sessionId, loading])

  const gameName = GAME_LABELS[selectedGame] || customDisplayName || customGameNames[selectedGame] || selectedGame
  const isC4 = selectedGame === 'connect_four'
  const isTTT = selectedGame === 'tictactoe'

  const selectedLabel = GAME_LABELS[selectedGame] || selectedGame
  const isLearned = learnedGames[selectedLabel]

  return (
    <div className="app">
      <header>
        <div className="header-top">
          <h1><span className="app-logo"><svg viewBox="0 0 14 14" width="18" height="18"><circle cx="7" cy="7" r="6.5" fill="#d4a656"/><rect x="4" y="4" width="6" height="6" rx="0.5" fill="none" stroke="#0e0c0a" strokeWidth="0.7" transform="rotate(45 7 7)"/><circle cx="7" cy="7" r="1.5" fill="#0e0c0a" opacity="0.3"/></svg></span>Thin<em>ai</em></h1>
          <a href="/" className="about-link">About the research</a>
        </div>
      </header>

      {mode === 'train' ? (
        <TrainingDashboard games={games} initialGame={selectedGame} customGameNames={customGameNames} onBack={() => { setMode('menu') }} onPlay={(game) => { setSelectedGame(game); setMode('play'); startGame(game) }} />
      ) : mode === 'menu' || !sessionId ? (
        <div className="menu">
          <h2>Select a game</h2>
          {(() => {
            const trainedGames = games.filter(g => {
              const label = GAME_LABELS[g] || customGameNames[g] || g
              return learnedGames[label]
            })
            const untrainedGames = games.filter(g => {
              const label = GAME_LABELS[g] || customGameNames[g] || g
              return !learnedGames[label]
            })
            const GameButton = ({ g }) => {
              const label = GAME_LABELS[g] || customGameNames[g] || g
              const trained = learnedGames[label]
              return (
                <button
                  key={g}
                  className={`${selectedGame === g ? 'active' : ''} ${trained ? 'trained' : ''}`}
                  onClick={() => setSelectedGame(g)}
                >
                  {label}
                </button>
              )
            }
            return <>
              {trainedGames.length > 0 && (
                <>
                  <div className="game-group-label">Trained</div>
                  <div className="game-select">
                    {trainedGames.map(g => <GameButton key={g} g={g} />)}
                  </div>
                </>
              )}
              {untrainedGames.length > 0 && (
                <>
                  <div className="game-group-label">{trainedGames.length > 0 ? 'Not yet trained' : ''}</div>
                  <div className="game-select">
                    {untrainedGames.map(g => <GameButton key={g} g={g} />)}
                  </div>
                </>
              )}
            </>
          })()}

          <div className="menu-actions">
            <button className="action-btn action-btn-primary" onClick={() => { setMode('train') }}>
              {isLearned ? 'Train ThinAI More' : 'Train ThinAI'}
            </button>
            <button className="action-btn" onClick={() => { setMode('play'); startGame() }} disabled={loading}>
              {loading ? 'Starting...' : 'Play vs ThinAI'}
            </button>
          </div>

          {isLearned && (
            <div className="learned-status">
              {selectedLabel}: trained on {isLearned.generation} games
            </div>
          )}

          <div className="menu-links">
            <button className="view-gdl-btn" onClick={() => setShowGdlModal(true)}>View game rules (GDL)</button>
          </div>

          {showGdlModal && gdlData && (
            <div className="rules-overlay" onClick={() => setShowGdlModal(false)}>
              <div className="rules-modal gdl-modal" onClick={e => e.stopPropagation()}>
                <div className="rules-modal-header">
                  <span className="rules-modal-title">{gdlData.game_name} — Game Definition</span>
                  <button className="rules-modal-close" onClick={() => setShowGdlModal(false)}>&times;</button>
                </div>
                <p className="gdl-modal-intro">
                  This is the structured rule specification the AI learns from. It defines the board,
                  pieces, legal moves, and win conditions — everything the system needs to play.
                </p>
                <pre className="gdl-code">{JSON.stringify(gdlData.gdl, null, 2)}</pre>
              </div>
            </div>
          )}

          <div className="teach-teaser">
            <div className="teach-teaser-divider">
              <span>or</span>
            </div>
            <h3>Teach it a new game <span style={{ fontFamily: 'Menlo, monospace', fontSize: '0.7rem', color: 'var(--accent)', border: '1px solid var(--accent-dim)', padding: '0.15rem 0.5rem', borderRadius: '3px', marginLeft: '0.5rem', verticalAlign: 'middle' }}>In Progress</span></h3>
            <p>
              ThinAI can learn simple games from a plain English description.
              Describe a game with a board and rules, and the system will parse it,
              generate evaluation features, train through self-play, and let you play against it.
            </p>
            <div style={{
              fontSize: '0.85rem', color: 'var(--ink)', background: 'rgba(212,166,86,0.08)',
              border: '1px solid rgba(212,166,86,0.25)', borderRadius: '6px',
              padding: '0.7rem 1rem', margin: '0.75rem 0', fontFamily: 'Menlo, monospace',
              lineHeight: '1.6'
            }}>
              <strong style={{ color: 'var(--accent)' }}>Current limitations:</strong> Works with grid placement games (N-in-a-row, territory) and simple card games. Complex movement rules (chess-like) are not yet supported for novel games. <em>Note: this is not an LLM — it uses pattern matching, so its vocabulary is limited to common game terms.</em>
              <div style={{ marginTop: '0.5rem' }}>
                <button onClick={() => setShowParserRef(true)} style={{
                  background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer',
                  fontFamily: 'Menlo, monospace', fontSize: '0.85rem', padding: 0, textDecoration: 'underline',
                  textUnderlineOffset: '3px',
                }}>
                  View full parser reference →
                </button>
              </div>
            </div>
            {showParserRef && <ParserReference onClose={() => setShowParserRef(false)} />}
            <div className="teach-teaser-example">
              <div className="teach-teaser-label">Example inputs — try any of these</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                <li className="teach-teaser-text" style={{ paddingLeft: '1rem', marginBottom: '0.8rem', paddingBottom: '0.8rem', borderBottom: '1px solid var(--ink-faint)' }}>
                  "Two players take turns placing stones on a 5x5 grid. A player wins by
                  getting 4 in a row horizontally, vertically, or diagonally. If the board
                  is full with no winner, it's a draw."
                </li>
                <li className="teach-teaser-text" style={{ paddingLeft: '1rem', marginBottom: '0.8rem', paddingBottom: '0.8rem', borderBottom: '1px solid var(--ink-faint)' }}>
                  "Two players are each dealt 5 cards. Players take turns playing one card.
                  The higher rank wins the round. Each round is worth more points than the
                  last (1, 2, 3, 4, 5). After all cards are played, the most points wins."
                </li>
                <li className="teach-teaser-text" style={{ paddingLeft: '1rem', marginBottom: '0.8rem', paddingBottom: '0.8rem', borderBottom: '1px solid var(--ink-faint)' }}>
                  "Two players take turns rolling a die and placing a piece on a 5x5 grid.
                  The number rolled determines which row you must place in. If that row is
                  full, you lose your turn. First to get 3 in a row in any direction wins."
                </li>
                <li className="teach-teaser-text" style={{ paddingLeft: '1rem' }}>
                  "Two players take turns placing L-shaped tiles on a 6x6 grid. Each tile
                  covers 3 squares in an L shape. A player wins by completely filling a row
                  or column. If no more tiles can be placed, the player who placed more
                  tiles wins."
                </li>
              </ul>
            </div>
            <div className="teach-workspace">
              <div className="teach-input-col">
                <textarea
                  className="teach-input"
                  placeholder="Describe your game's rules in plain English. For example: Two players take turns placing marks on a 3x3 grid. Get 3 in a row to win. If all squares are filled, it's a draw."
                  rows={8}
                  value={teachInput}
                  onChange={e => setTeachInput(e.target.value)}
                />
                <button
                  className="teach-btn"
                  onClick={handleParse}
                  disabled={!teachInput.trim() || parsing}
                >
                  {parsing ? 'Translating...' : 'Translate to Game Description'}
                </button>
              </div>

              <div className="teach-result-col">
                {parseResult && (
                  <div className="parse-result">
                    <div className="parse-result-header">Generated Game Definition</div>
                    <div className="parse-result-summary">
                      <span><strong>Name:</strong> {parseResult.meta?.name}</span>
                      <span><strong>Board:</strong> {parseResult.board?.type === 'grid'
                        ? `${parseResult.board.grid.rows}×${parseResult.board.grid.cols} grid`
                        : parseResult.board?.type === 'track'
                          ? `${parseResult.board.track.length}-space track`
                          : 'unknown'}</span>
                      <span><strong>Rules:</strong> {parseResult.rules?.length || 0} move type{parseResult.rules?.length !== 1 ? 's' : ''}</span>
                      <span><strong>Win conditions:</strong> {parseResult.end_conditions?.filter(c => c.type === 'win').length || 0}</span>
                    </div>
                    {parseResult._parse_info && (
                      <div className="parse-info">
                        {parseResult._parse_info.understood?.length > 0 && (
                          <div className="parse-understood">
                            <strong>Understood:</strong> {parseResult._parse_info.understood.join(', ')}
                          </div>
                        )}
                        {parseResult._parse_info.not_understood?.length > 0 && (
                          <div className="parse-not-understood">
                            <strong>Not understood:</strong> {parseResult._parse_info.not_understood.join(', ')}
                          </div>
                        )}
                      </div>
                    )}
                    <details className="parse-result-details">
                      <summary>View full GDL</summary>
                      <pre>{JSON.stringify(parseResult, null, 2)}</pre>
                    </details>
                  </div>
                )}
                {parseError && (
                  <div className="parse-error">
                    <strong>Could not parse:</strong> {parseError}
                  </div>
                )}
                {!parseResult && !parseError && (
                  <div className="parse-placeholder">
                    Describe your game on the left and click "Translate" to see the generated game definition here.
                  </div>
                )}
              </div>
            </div>
            {parseResult && !parseError && (
              <div className="parse-success-banner">
                <div className="parse-success-icon">&#10003;</div>
                <div className="parse-success-text">
                  <strong>Ready to learn!</strong> ThinAI understood your game rules — {parseResult.rules?.length || 0} move type{parseResult.rules?.length !== 1 ? 's' : ''}, {parseResult.end_conditions?.length || 0} end condition{parseResult.end_conditions?.length !== 1 ? 's' : ''}, on a {parseResult.board?.type === 'grid' ? `${parseResult.board.grid.rows}×${parseResult.board.grid.cols} grid` : parseResult.board?.type || 'board'}.
                </div>
                {clarifications.length > 0 && (
                  <div style={{ margin: '0.75rem 0', padding: '0.75rem', background: 'rgba(212,166,86,0.06)', border: '1px solid rgba(212,166,86,0.2)', borderRadius: '6px' }}>
                    <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.8rem', color: 'var(--accent)', marginBottom: '0.5rem', fontWeight: 600 }}>
                      A few questions (optional — defaults are fine):
                    </div>
                    {clarifications.map(c => (
                      <div key={c.id} style={{ marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                        <div style={{ color: 'var(--ink)', marginBottom: '0.25rem' }}>{c.question}</div>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {(c.options || []).map(opt => (
                            <button key={opt}
                              className="crazy8-draw-btn"
                              style={{
                                fontSize: '0.75rem', padding: '0.2rem 0.5rem',
                                background: (clarAnswers[c.id] || c.default) === opt ? 'var(--accent)' : 'var(--bg)',
                                color: (clarAnswers[c.id] || c.default) === opt ? 'var(--bg)' : 'var(--ink-dim)',
                              }}
                              onClick={() => {
                                setClarAnswers(prev => ({ ...prev, [c.id]: opt }))
                                if (parsedGameId) {
                                  fetch(`${API}/parse/clarify`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ game_id: parsedGameId, clarification_id: c.id, answer: opt }),
                                  }).then(r => r.json()).then(d => {
                                    if (d.gdl) {
                                      setParseResult(d.gdl)
                                      // Refresh game list to pick up changes
                                      refreshGames()
                                    }
                                  }).catch(() => {})
                                }
                              }}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0.5rem 0' }}>
                  <label style={{ fontFamily: 'Menlo, monospace', fontSize: '0.85rem', color: 'var(--ink-dim)', whiteSpace: 'nowrap' }}>Name your game:</label>
                  <input
                    type="text"
                    value={customGameName || parseResult.meta?.name || ''}
                    onChange={e => setCustomGameName(e.target.value)}
                    style={{
                      flex: 1, padding: '0.4rem 0.6rem', background: 'var(--bg)',
                      border: '1px solid var(--rule-bright)', borderRadius: '4px',
                      color: 'var(--ink)', fontFamily: 'Menlo, monospace', fontSize: '0.85rem',
                    }}
                    placeholder="e.g. Wizard Battle"
                  />
                </div>
                <button className="teach-btn teach-btn-learn" onClick={async () => {
                  const name = customGameName || parseResult.meta?.name || 'custom_game'
                  let gid = parsedGameId || name.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/^_+|_+$/g, '') || 'custom_game'
                  if (customGameName && customGameName !== parseResult.meta?.name) {
                    // Rename: re-parse with new name, then re-apply clarifications
                    try {
                      const res = await fetch(`${API}/parse`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: teachInput, name: customGameName }),
                      })
                      const data = await res.json()
                      if (data.game_id) gid = data.game_id
                      // Re-apply clarification answers to the renamed file
                      for (const [cid, ans] of Object.entries(clarAnswers)) {
                        await fetch(`${API}/parse/clarify`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ game_id: gid, clarification_id: cid, answer: ans }),
                        })
                      }
                      refreshGames()
                    } catch (e) {}
                  } else if (Object.keys(clarAnswers).length > 0 && parsedGameId) {
                    // No rename but has clarifications — ensure they're applied
                    for (const [cid, ans] of Object.entries(clarAnswers)) {
                      await fetch(`${API}/parse/clarify`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ game_id: parsedGameId, clarification_id: cid, answer: ans }),
                      })
                    }
                  }
                  setSelectedGame(gid)
                  setMode('train')
                }}>
                  Train ThinAI on This Game
                </button>
              </div>
            )}
            {parseError && (
              <div className="parse-fail-banner">
                <div className="parse-fail-icon">!</div>
                <div className="parse-fail-text">
                  <strong>Not enough to learn from.</strong> {parseError}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="game-container">
          <div className="game-header">
            <div className="game-title-row">
              <span className="game-title">{gameName}</span>
              <button className="rules-btn" onClick={() => setShowRulesModal(true)}>?</button>
            </div>
            {(() => {
              const cos = gameState?.cosmetics || {}
              const customColor = cos.player1_color
              const colorNames = {'#c83030':'Red','#2060d0':'Blue','#20a040':'Green','#d4a020':'Yellow','#d08020':'Orange','#8040c0':'Purple','#d060a0':'Pink','#222222':'Black','#f0e8d8':'White','#d4a656':'Gold','#a0a0a8':'Silver','#8B4513':'Brown'}
              const pi = PLAYER_INDICATOR[selectedGame] || { label: customColor ? (colorNames[customColor] || 'Player 1') : 'Gold', color: customColor || 'var(--accent)' }
              return (
                <div className="player-indicator">
                  You are playing as <span className="player-indicator-label" style={{ color: pi.color }}>
                    {pi.label}
                  </span>
                </div>
              )
            })()}
            <GameInfo state={gameState} aiLastMove={aiLastMove} loading={loading} />
            {aiThinking?.confidence && (
              <div className="ai-thinking-bar">
                <span className="ai-thinking-label">AI confidence:</span>
                <div className="ai-confidence-meter">
                  <div className="ai-confidence-fill" style={{ width: `${aiThinking.confidence.calibrated * 100}%` }} />
                </div>
                <span className="ai-thinking-level">{aiThinking.confidence.level}</span>
                {aiThinking.effort && (
                  <span className="ai-thinking-effort">depth {aiThinking.effort.depth_used} · {aiThinking.effort.nodes_searched} positions</span>
                )}
              </div>
            )}
            {aiThinking?.commentary && (
              <div className="ai-commentary">
                💭 {aiThinking.commentary}
              </div>
            )}
          </div>
          {showRulesModal && (
            <RulesModal gameType={selectedGame} onClose={() => setShowRulesModal(false)}
              customDescription={teachInput || gdlData?.gdl?._original_description} />
          )}
          {(
            <GameBoardRenderer
              gameType={selectedGame}
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
              aiLastMove={aiLastMove}
            />
          )}
          {gameState?.game_result && (
            <div className="result">
              <span className="result-text">
                {gameState.game_result.type === 'draw'
                  ? 'Draw!'
                  : gameState.game_result.winner === 'player1'
                    ? 'You win!'
                    : 'AI wins!'}
              </span>
            </div>
          )}
          {!isLearned && (
            <div className="untrained-warning">
              Note: ThinAI has not trained on this game yet. Train it first for a stronger opponent!
            </div>
          )}
          <div className="game-actions">
            <button className="action-btn" onClick={() => { setSessionId(null); setGameState(null); setMode('menu') }}>
              &larr; Back to Games
            </button>
            <button className="action-btn action-btn-primary" onClick={() => { setGameState(null); setAiThinking(null); setAiLastMove(null); startGame() }}>
              New Game
            </button>
          </div>
          <CorrectionsPanel sessionId={sessionId} gameResult={gameState?.game_result} />
        </div>
      )}
    </div>
  )
}

function GameInfo({ state, aiLastMove, loading }) {
  if (!state) return null
  const isYourTurn = state.current_player === 'player1' && !state.game_result
  const statusText = state.game_result
    ? 'Game Over'
    : loading
      ? 'AI thinking...'
      : aiLastMove
        ? 'AI played — your turn'
        : isYourTurn
          ? 'Your turn'
          : 'AI thinking...'
  return (
    <div className="game-info">
      <span className={`turn-indicator ${isYourTurn && !loading ? 'your-turn' : ''}`}>
        {statusText}
      </span>
      <span className="turn-number">Move {state.turn_number}</span>
    </div>
  )
}

function CorrectionsPanel({ sessionId, gameResult }) {
  const [data, setData] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Fetch correction data when game result changes or panel is expanded
  useEffect(() => {
    if (!sessionId) return
    fetch(`${API}/game/${sessionId}/corrections`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
  }, [sessionId, gameResult, expanded])

  if (!sessionId || !data) return null

  const confidence = data.confidence_summary || []
  const corrections = data.total_corrections || 0
  const revisions = data.revisions_applied || 0

  const submitFeedback = async () => {
    if (!feedback.trim() || submitting) return
    setSubmitting(true)
    try {
      await fetch(`${API}/game/${sessionId}/correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      })
      setFeedback('')
      // Refresh data
      const res = await fetch(`${API}/game/${sessionId}/corrections`)
      setData(await res.json())
    } catch (e) {
      console.error('Failed to submit correction:', e)
    }
    setSubmitting(false)
  }

  return (
    <div className="corrections-panel">
      <button
        className="corrections-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="corrections-toggle-label">
          Rule Confidence
          {corrections > 0 && (
            <span className="corrections-badge">{corrections} correction{corrections !== 1 ? 's' : ''}</span>
          )}
        </span>
        <span className="corrections-chevron">{expanded ? '\u25B2' : '\u25BC'}</span>
      </button>

      {expanded && (
        <div className="corrections-body">
          <div className="confidence-bars">
            {confidence.map(rc => (
              <div key={rc.rule_name} className="confidence-row">
                <span className="confidence-name">{rc.rule_name}</span>
                <div className="confidence-bar-track">
                  <div
                    className={`confidence-bar ${rc.score >= 0.5 ? 'high' : rc.score >= 0.3 ? 'medium' : 'low'}`}
                    style={{ width: `${rc.score * 100}%` }}
                  />
                </div>
                <span className="confidence-value">{(rc.score * 100).toFixed(0)}%</span>
                <span className="confidence-prov">{rc.provenance}</span>
              </div>
            ))}
          </div>

          {revisions > 0 && (
            <div className="corrections-stat">
              {revisions} revision{revisions !== 1 ? 's' : ''} applied
            </div>
          )}

          <div className="corrections-feedback">
            <input
              type="text"
              placeholder="Tell the system about a rule it got wrong..."
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submitFeedback()}
            />
            <button onClick={submitFeedback} disabled={!feedback.trim() || submitting}>
              {submitting ? '...' : 'Correct'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
