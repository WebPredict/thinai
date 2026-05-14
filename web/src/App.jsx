import { useState, useEffect, useCallback } from 'react'
import TrainingDashboard from './TrainingDashboard'
import './App.css'

const API = 'http://localhost:8000/api'

const GAME_LABELS = {
  tictactoe: 'Tic-Tac-Toe',
  connect_four: 'Connect Four',
  mancala: 'Mancala',
  reversi: 'Reversi',
  nim: 'Nim',
  chutes_and_ladders: 'Chutes & Ladders',
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
}

function RulesModal({ gameType, onClose }) {
  const rules = GAME_RULES[gameType]
  if (!rules) return null

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
  const [selectedGame, setSelectedGame] = useState('tictactoe')
  const [mode, setMode] = useState('play') // 'play' or 'train'
  const [aiLastMove, setAiLastMove] = useState(null) // highlight AI's last move
  const [showRulesModal, setShowRulesModal] = useState(true) // show rules on game start

  useEffect(() => {
    fetch(`${API}/games`)
      .then(r => r.json())
      .then(d => setGames(d.games))
      .catch(() => setGames(['tictactoe', 'connect_four']))
  }, [])

  const startGame = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/game/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game: selectedGame,
          ai_player: 'player2',
          ai_depth: selectedGame === 'tictactoe' ? 9 : selectedGame === 'reversi' ? 3 : 4,
        }),
      })
      const data = await res.json()
      setSessionId(data.session_id)
      setGameState(data.state)
      setShowRulesModal(true)
    } catch (e) {
      console.error('Failed to start game:', e)
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
        // Step 2: Pause so the player sees their move + any flips/captures
        await new Promise(r => setTimeout(r, 500))

        // Step 3: Ask the AI to play
        const aiRes = await fetch(`${API}/game/${sessionId}/ai-move`, { method: 'POST' })
        const aiData = await aiRes.json()
        setGameState(aiData.state)
        if (aiData.ai_move) {
          setAiLastMove(aiData.ai_move)
          setTimeout(() => setAiLastMove(null), 2500)
        }
      }
    } catch (e) {
      console.error('Failed to make move:', e)
    }
    setLoading(false)
  }, [sessionId, loading])

  const gameName = GAME_LABELS[selectedGame] || selectedGame
  const isC4 = selectedGame === 'connect_four'
  const isTTT = selectedGame === 'tictactoe'

  return (
    <div className="app">
      <header>
        <div className="header-top">
          <h1><span className="app-logo"><svg viewBox="0 0 14 14" width="18" height="18"><circle cx="7" cy="7" r="6.5" fill="#d4a656"/><rect x="4" y="4" width="6" height="6" rx="0.5" fill="none" stroke="#0e0c0a" strokeWidth="0.7" transform="rotate(45 7 7)"/><circle cx="7" cy="7" r="1.5" fill="#0e0c0a" opacity="0.3"/></svg></span>Thin<em>ai</em></h1>
          <a href="/landing.html" className="about-link">About the research</a>
        </div>
        <div className="mode-toggle">
          <button className={mode === 'play' ? 'active' : ''} onClick={() => setMode('play')}>Play</button>
          <button className={mode === 'train' ? 'active' : ''} onClick={() => setMode('train')}>Train</button>
        </div>
      </header>

      {mode === 'train' ? (
        <TrainingDashboard games={games} />
      ) : !sessionId ? (
        <div className="menu">
          <h2>Select a game</h2>
          <div className="game-select">
            {games.map(g => (
              <button
                key={g}
                className={selectedGame === g ? 'active' : ''}
                onClick={() => setSelectedGame(g)}
              >
                {GAME_LABELS[g] || g}
              </button>
            ))}
          </div>
          <button className="start-btn" onClick={startGame} disabled={loading}>
            {loading ? 'Starting...' : 'Play vs AI'}
          </button>

          <div className="teach-teaser">
            <div className="teach-teaser-divider">
              <span>or</span>
            </div>
            <h3>Teach it a new game</h3>
            <p>
              The goal of ThinAI is to learn <em>any</em> game from a natural-language
              description of the rules. Describe your game below and the system will
              parse the rules, build an internal model, and learn to play through practice.
            </p>
            <div className="teach-teaser-example">
              <div className="teach-teaser-label">Example input</div>
              <div className="teach-teaser-text">
                "Two players take turns placing stones on a 5x5 grid. A player wins by
                getting 4 in a row horizontally, vertically, or diagonally. If the board
                is full with no winner, it's a draw."
              </div>
            </div>
            <textarea
              className="teach-input"
              placeholder="Describe your game's rules in plain English..."
              rows={4}
              disabled
            />
            <button className="teach-btn" disabled>
              Add Game <span className="coming-soon-badge">Coming Soon</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="game-container">
          <div className="game-header">
            <div className="game-title-row">
              <span className="game-title">{gameName}</span>
              <button className="rules-btn" onClick={() => setShowRulesModal(true)}>?</button>
            </div>
            <GameInfo state={gameState} aiLastMove={aiLastMove} loading={loading} />
          </div>
          {showRulesModal && (
            <RulesModal gameType={selectedGame} onClose={() => setShowRulesModal(false)} />
          )}
          {selectedGame === 'mancala' ? (
            <MancalaBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
              aiLastMove={aiLastMove}
            />
          ) : selectedGame === 'nim' ? (
            <NimBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
            />
          ) : selectedGame === 'chutes_and_ladders' ? (
            <ChutesAndLaddersBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
              aiLastMove={aiLastMove}
            />
          ) : (
            <GridBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
              gameType={selectedGame}
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
          <div className="game-actions">
            <button className="action-btn" onClick={() => { setSessionId(null); setGameState(null) }}>
              &larr; Back to Games
            </button>
            <button className="action-btn action-btn-primary" onClick={startGame}>
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

function GridBoard({ state, onMove, disabled, gameType, aiLastMove }) {
  const [hoverCol, setHoverCol] = useState(null)

  if (!state || state.board_type !== 'grid') return null

  const { rows, cols, spaces, legal_moves } = state
  const isC4 = gameType === 'connect_four'
  const isTTT = gameType === 'tictactoe'
  const isReversi = gameType === 'reversi'

  // Determine which cell the AI last played
  const aiRow = aiLastMove?.target?.row ?? null
  const aiCol = aiLastMove?.target?.col ?? aiLastMove?.column ?? null

  const isColumnBased = legal_moves.length > 0 && 'column' in (legal_moves[0]?.params || {})

  const handleCellClick = (row, col) => {
    if (disabled) return
    if (isColumnBased) {
      const move = legal_moves.find(m => m.params.column === col)
      if (move) onMove(move.rule, move.params)
    } else {
      const move = legal_moves.find(m =>
        m.params.target?.row === row && m.params.target?.col === col
      )
      if (move) onMove(move.rule, move.params)
    }
  }

  const isLegal = (row, col) => {
    if (isColumnBased) return legal_moves.some(m => m.params.column === col)
    return legal_moves.some(m =>
      m.params.target?.row === row && m.params.target?.col === col
    )
  }

  const renderPiece = (piece, row) => {
    if (!piece) return null

    if (isTTT) {
      return (
        <div className={`piece ttt-piece ${piece.owner === 'player1' ? 'p1' : 'p2'}`}>
          {piece.owner === 'player1' ? (
            <svg viewBox="0 0 40 40" className="piece-svg">
              <line x1="8" y1="8" x2="32" y2="32" strokeWidth="4" strokeLinecap="round" />
              <line x1="32" y1="8" x2="8" y2="32" strokeWidth="4" strokeLinecap="round" />
            </svg>
          ) : (
            <svg viewBox="0 0 40 40" className="piece-svg">
              <circle cx="20" cy="20" r="13" fill="none" strokeWidth="4" />
            </svg>
          )}
        </div>
      )
    }

    if (isC4) {
      return (
        <div className={`piece c4-disc ${piece.owner === 'player1' ? 'p1' : 'p2'} drop-in`}
             style={{ '--drop-rows': row }}>
          <div className="disc-inner" />
        </div>
      )
    }

    if (isReversi) {
      return (
        <div className={`piece reversi-disc ${piece.owner === 'player1' ? 'p1' : 'p2'}`}>
          <div className="disc-inner" />
        </div>
      )
    }

    return <div className="piece">{piece.owner === 'player1' ? 'P1' : 'P2'}</div>
  }

  const boardClass = [
    'board',
    isC4 ? 'c4-board' : '',
    isTTT ? 'ttt-board' : '',
    isReversi ? 'reversi-board' : '',
  ].filter(Boolean).join(' ')

  const grid = []
  for (let r = 0; r < rows; r++) {
    const rowCells = []
    for (let c = 0; c < cols; c++) {
      const key = `${r},${c}`
      const piece = spaces[key]
      const legal = !disabled && isLegal(r, c)
      const isHoverCol = isC4 && hoverCol === c && legal
      const isAiMove = aiLastMove && (
        (aiRow === r && aiCol === c) ||
        (isC4 && aiCol === c && piece?.owner === 'player2')
      )

      rowCells.push(
        <div
          key={key}
          className={[
            'cell',
            piece ? 'occupied' : '',
            legal ? 'legal' : '',
            isHoverCol ? 'hover-col' : '',
            isAiMove ? 'ai-last-move' : '',
            piece?.owner === 'player1' ? 'p1' : piece?.owner === 'player2' ? 'p2' : '',
          ].filter(Boolean).join(' ')}
          onClick={() => handleCellClick(r, c)}
          onMouseEnter={() => isC4 && setHoverCol(c)}
          onMouseLeave={() => isC4 && setHoverCol(null)}
        >
          {isC4 && <div className="c4-hole" />}
          {renderPiece(piece, r)}
        </div>
      )
    }
    grid.push(<div key={r} className="board-row">{rowCells}</div>)
  }

  return <div className={boardClass}>{grid}</div>
}

function MancalaBoard({ state, onMove, disabled }) {
  if (!state) return null

  const { spaces, legal_moves } = state

  // Mancala layout: 14 spaces in a track
  // Top row (P2 pits, right to left): 12, 11, 10, 9, 8, 7
  // Bottom row (P1 pits, left to right): 0, 1, 2, 3, 4, 5
  // Left store (P2): 13
  // Right store (P1): 6

  const getCount = (idx) => {
    const val = spaces[String(idx)]
    if (!val) return 0
    if (Array.isArray(val)) return val.length
    return 1
  }

  const isLegal = (idx) => {
    return legal_moves.some(m => m.params.pit?.index === idx)
  }

  const handleClick = (idx) => {
    if (disabled) return
    const move = legal_moves.find(m => m.params.pit?.index === idx)
    if (move) onMove(move.rule, move.params)
  }

  const p1Pits = [0, 1, 2, 3, 4, 5]
  const p2Pits = [12, 11, 10, 9, 8, 7]

  const renderStones = (count, max) => {
    const shown = Math.min(count, max)
    return (
      <div className="mancala-stones">
        {Array.from({ length: shown }).map((_, i) => (
          <div key={i} className="mancala-stone" />
        ))}
      </div>
    )
  }

  const renderPit = (idx) => {
    const count = getCount(idx)
    return (
      <div key={idx} className={`mancala-pit ${isLegal(idx) && !disabled ? 'legal' : ''}`}
           onClick={() => handleClick(idx)}>
        {renderStones(count, 8)}
        <span className="stone-count">{count}</span>
      </div>
    )
  }

  return (
    <div className="mancala-board">
      <div className="mancala-store p2-store">
        {renderStones(getCount(13), 12)}
        <div className="store-count">{getCount(13)}</div>
        <div className="store-label">AI</div>
      </div>

      <div className="mancala-center">
        <div className="mancala-row p2-row">
          {p2Pits.map(renderPit)}
        </div>
        <div className="mancala-row p1-row">
          {p1Pits.map(renderPit)}
        </div>
      </div>

      <div className="mancala-store p1-store">
        {renderStones(getCount(6), 12)}
        <div className="store-count">{getCount(6)}</div>
        <div className="store-label">You</div>
      </div>
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

function NimBoard({ state, onMove, disabled }) {
  const [selectedPile, setSelectedPile] = useState(null)

  if (!state) return null

  const { spaces, legal_moves } = state

  const getCount = (idx) => {
    const val = spaces[String(idx)]
    if (!val) return 0
    if (Array.isArray(val)) return val.length
    return 1
  }

  const piles = [0, 1, 2]
  const pileCounts = piles.map(getCount)

  const getAmounts = (pileIdx) => {
    return legal_moves
      .filter(m => m.params.pile?.index === pileIdx)
      .map(m => m.params.amount)
      .sort((a, b) => a - b)
  }

  const handleTake = (pileIdx, amount) => {
    if (disabled) return
    const move = legal_moves.find(
      m => m.params.pile?.index === pileIdx && m.params.amount === amount
    )
    if (move) {
      onMove(move.rule, move.params)
      setSelectedPile(null)
    }
  }

  return (
    <div className="nim-board">
      <div className="nim-piles">
        {piles.map(idx => {
          const count = pileCounts[idx]
          const amounts = getAmounts(idx)
          const isSelected = selectedPile === idx
          const hasStones = count > 0

          return (
            <div key={idx} className="nim-pile-col">
              <div className="nim-pile-label">Pile {idx + 1}</div>
              <div
                className={[
                  'nim-pile',
                  isSelected ? 'selected' : '',
                  hasStones && !disabled ? 'clickable' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => hasStones && !disabled && setSelectedPile(isSelected ? null : idx)}
              >
                {Array.from({ length: count }).map((_, i) => (
                  <div key={i} className="nim-stone" />
                ))}
                {count === 0 && <div className="nim-empty">empty</div>}
              </div>
              {isSelected && amounts.length > 0 && (
                <div className="nim-take-buttons">
                  {amounts.map(amt => (
                    <button
                      key={amt}
                      className="nim-take-btn"
                      onClick={() => handleTake(idx, amt)}
                    >
                      Take {amt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <div className="nim-hint">Click a pile, then choose how many to take</div>
    </div>
  )
}

function ChutesAndLaddersBoard({ state, onMove, disabled, aiLastMove }) {
  const [lastRoll, setLastRoll] = useState(null)
  const [rolling, setRolling] = useState(false)

  if (!state) return null

  const { spaces, legal_moves } = state
  const rows = 5
  const cols = 5

  const getSpaceNumber = (row, col) => {
    const baseRow = (rows - 1 - row)
    const rowStart = baseRow * cols + 1
    return baseRow % 2 === 0 ? rowStart + col : rowStart + (cols - 1 - col)
  }

  const findPlayer = (player) => {
    for (const [key, val] of Object.entries(spaces)) {
      const pieces = Array.isArray(val) ? val : [val]
      if (pieces.some(p => p.owner === player)) return parseInt(key)
    }
    return 0
  }

  const p1Pos = findPlayer('player1')
  const p2Pos = findPlayer('player2')

  const ladders = { 2: 10, 6: 16, 8: 12, 15: 23 }
  const chutes = { 14: 3, 19: 7, 22: 11, 24: 18 }

  // Alternating warm/cool squares like a real game board
  const getSquareColor = (num) => {
    if (num in ladders) return '#1e5a2e' // dark green for ladder starts
    if (num in chutes) return '#5a1e1e'  // dark red for chute starts
    // Checkerboard pattern
    const row = Math.floor((num - 1) / 5)
    const col = (num - 1) % 5
    return (row + col) % 2 === 0 ? '#2a2520' : '#332e28'
  }

  const handleRoll = async () => {
    if (disabled || rolling) return
    setRolling(true)
    const roll = Math.floor(Math.random() * 6) + 1
    setLastRoll(roll)
    const move = legal_moves.find(m => m.params.roll === roll)
    if (move) {
      await new Promise(r => setTimeout(r, 600))
      await onMove(move.rule, move.params)
    }
    setRolling(false)
  }

  const aiRollVal = aiLastMove?.roll
  const isYourTurn = state.current_player === 'player1' && !state.game_result

  return (
    <div className="cl-board-container">
      <div className="cl-board-wrapper">
        <div className="cl-board">
          {Array.from({ length: rows }).map((_, r) => (
            <div key={r} className="cl-row">
              {Array.from({ length: cols }).map((_, c) => {
                const num = getSpaceNumber(r, c)
                const isLadder = num in ladders
                const isChute = num in chutes
                const hasP1 = p1Pos === num
                const hasP2 = p2Pos === num
                const isFinish = num === 25

                return (
                  <div key={c} className={[
                    'cl-cell',
                    isLadder ? 'cl-ladder' : '',
                    isChute ? 'cl-chute' : '',
                    isFinish ? 'cl-finish' : '',
                  ].filter(Boolean).join(' ')} style={{ background: getSquareColor(num) }}>
                    <span className="cl-number">{num}</span>
                    {isLadder && (
                      <div className="cl-badge cl-ladder-badge">
                        LADDER &uarr; {ladders[num]}
                      </div>
                    )}
                    {isChute && (
                      <div className="cl-badge cl-chute-badge">
                        CHUTE &darr; {chutes[num]}
                      </div>
                    )}
                    {isFinish && !hasP1 && !hasP2 && (
                      <div className="cl-finish-star">&#9733;</div>
                    )}
                    <div className="cl-tokens">
                      {hasP1 && <div className="cl-token cl-p1">You</div>}
                      {hasP2 && <div className="cl-token cl-p2">AI</div>}
                    </div>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="cl-controls">
        <div className="cl-roll-area">
          {lastRoll && (
            <div className="cl-die">
              <span className="cl-die-face">{lastRoll}</span>
            </div>
          )}
          {aiRollVal && (
            <div className="cl-die cl-die-ai">
              <span className="cl-die-face">{aiRollVal}</span>
              <span className="cl-die-label">AI</span>
            </div>
          )}
        </div>
        {isYourTurn && (
          <button className="cl-roll-btn" onClick={handleRoll} disabled={disabled || rolling}>
            {rolling ? 'Rolling...' : 'Roll Die'}
          </button>
        )}
      </div>
    </div>
  )
}

export default App
