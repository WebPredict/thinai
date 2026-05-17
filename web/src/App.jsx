import { useState, useEffect, useCallback, useRef } from 'react'
import TrainingDashboard from './TrainingDashboard'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// Display order: most interesting demos first
const GAME_ORDER = ['reversi', 'connect_four', 'checkers', 'mancala', 'uno', 'crazy_eights', 'blackjack', 'go_fish', 'war', 'tictactoe', 'nim', 'chutes_and_ladders']

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
  const [selectedGame, setSelectedGame] = useState('reversi')
  const [mode, setMode] = useState('menu') // 'menu', 'play', or 'train'
  const [learnedGames, setLearnedGames] = useState({})
  const [aiLastMove, setAiLastMove] = useState(null) // highlight AI's last move
  const [aiThinking, setAiThinking] = useState(null) // confidence + effort info from last AI move
  const [showRulesModal, setShowRulesModal] = useState(false)
  const rulesShownRef = useRef({})
  const [showGdlModal, setShowGdlModal] = useState(false)
  const [gdlData, setGdlData] = useState(null)
  const [teachInput, setTeachInput] = useState('')
  const [parseResult, setParseResult] = useState(null)
  const [parseError, setParseError] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [parsedGameId, setParsedGameId] = useState(null)
  const [customDisplayName, setCustomDisplayName] = useState(null)

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
        refreshGames() // Add new game to the list
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
    if (showGdlModal && selectedGame) {
      fetch(`${API}/game/${selectedGame}/gdl`)
        .then(r => r.json())
        .then(setGdlData)
        .catch(() => setGdlData(null))
    }
  }, [showGdlModal, selectedGame])

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

  const refreshGames = () => {
    fetch(`${API}/games`)
      .then(r => r.json())
      .then(d => {
        const all = [...d.games, ...(d.custom_games || [])]
        const sorted = all.sort((a, b) => {
          const ai = GAME_ORDER.indexOf(a), bi = GAME_ORDER.indexOf(b)
          return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
        })
        setGames(sorted)
      })
      .catch(() => setGames(GAME_ORDER))
  }

  useEffect(() => { refreshGames() }, [])

  const startGame = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/game/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game: selectedGame,
          ai_player: 'player2',
          ai_depth: {tictactoe: 6, connect_four: 4, mancala: 3, reversi: 2, nim: 4, chutes_and_ladders: 1}[selectedGame] || 3,
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

  const gameName = GAME_LABELS[selectedGame] || customDisplayName || selectedGame
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
        <TrainingDashboard games={games} initialGame={selectedGame} onBack={() => { setMode('play'); startGame() }} />
      ) : mode === 'menu' || !sessionId ? (
        <div className="menu">
          <h2>Select a game</h2>
          <div className="game-select">
            {games.map(g => {
              const label = GAME_LABELS[g] || g
              const trained = learnedGames[label]
              return (
                <button
                  key={g}
                  className={`${selectedGame === g ? 'active' : ''} ${trained ? 'trained' : ''}`}
                  onClick={() => setSelectedGame(g)}
                >
                  {label}
                  {trained && <span className="trained-badge" title={`${trained.generation} games trained`}>&#10003;</span>}
                </button>
              )
            })}
          </div>

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
                <button className="teach-btn teach-btn-learn" onClick={() => {
                  const gid = parsedGameId || parseResult.meta?.name?.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/^_+|_+$/g, '') || 'custom_game'
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
              const pi = PLAYER_INDICATOR[selectedGame] || { label: 'Gold', color: 'var(--accent)' }
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
                  <span className="ai-thinking-effort">depth {aiThinking.effort.depth_used}</span>
                )}
              </div>
            )}
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
          ) : selectedGame === 'checkers' ? (
            <CheckersBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
            />
          ) : selectedGame === 'uno' ? (
            <CrazyEightsBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
            />
          ) : selectedGame === 'blackjack' ? (
            <BlackjackBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
            />
          ) : selectedGame === 'crazy_eights' ? (
            <CrazyEightsBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
            />
          ) : selectedGame === 'go_fish' ? (
            <GoFishBoard
              state={gameState}
              onMove={makeMove}
              disabled={loading || gameState?.game_result != null}
            />
          ) : selectedGame === 'war' ? (
            <WarBoard
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
          {!isLearned && (
            <div className="untrained-warning">
              Note: ThinAI has not trained on this game yet. Train it first for a stronger opponent!
            </div>
          )}
          <div className="game-actions">
            <button className="action-btn" onClick={() => { setSessionId(null); setGameState(null); setMode('menu') }}>
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

  if (!state) return null
  // Accept grid board_type or any state with rows/cols (custom games)
  if (state.board_type !== 'grid' && !(state.rows && state.cols)) return null

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

    // Generic stone piece for custom/unknown games
    return (
      <div className={`piece generic-stone ${piece.owner === 'player1' ? 'p1' : 'p2'}`}>
        <div className="disc-inner" />
      </div>
    )
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

function CheckersBoard({ state, onMove, disabled }) {
  const [selectedPiece, setSelectedPiece] = useState(null)

  if (!state || state.board_type !== 'grid') return null

  const { rows, cols, spaces, legal_moves } = state
  const moveOptions = legal_moves || []

  // Build lookup: which pieces can move, and where can they go
  const movesFromPiece = {}  // "r,c" -> [{move, to: "r,c"}]
  const movablePieces = new Set()
  for (const m of moveOptions) {
    if (m.from && m.to) {
      const fromKey = `${m.from.row},${m.from.col}`
      const toKey = `${m.to.row},${m.to.col}`
      movablePieces.add(fromKey)
      if (!movesFromPiece[fromKey]) movesFromPiece[fromKey] = []
      movesFromPiece[fromKey].push({ move: m, toKey })
    }
  }

  // Valid destinations for selected piece
  const validDestinations = new Set()
  if (selectedPiece && movesFromPiece[selectedPiece]) {
    for (const { toKey } of movesFromPiece[selectedPiece]) {
      validDestinations.add(toKey)
    }
  }

  const handleCellClick = (row, col) => {
    if (disabled) return
    const key = `${row},${col}`
    const piece = spaces[key]

    // Clicking a movable piece: select it
    if (movablePieces.has(key)) {
      setSelectedPiece(selectedPiece === key ? null : key)
      return
    }

    // Clicking a valid destination: make the move
    if (selectedPiece && validDestinations.has(key)) {
      const moveEntry = movesFromPiece[selectedPiece].find(m => m.toKey === key)
      if (moveEntry) {
        onMove(moveEntry.move.rule, moveEntry.move.params)
        setSelectedPiece(null)
      }
      return
    }

    // Clicking anything else: deselect
    setSelectedPiece(null)
  }

  return (
    <div className="checkers-container">
      <div className="checkers-you-label">You are <span className="checkers-red-dot" /> Red</div>
      <div className="checkers-board">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="checkers-row">
            {Array.from({ length: cols }).map((_, c) => {
              const key = `${r},${c}`
              const piece = spaces[key]
              const isDark = (r + c) % 2 === 1
              const isSelected = selectedPiece === key
              const isMovable = movablePieces.has(key) && !disabled
              const isDestination = validDestinations.has(key)

              return (
                <div
                  key={c}
                  className={[
                    'checkers-cell',
                    isDark ? 'dark' : 'light',
                    isSelected ? 'selected' : '',
                    isMovable ? 'movable' : '',
                    isDestination ? 'destination' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={() => handleCellClick(r, c)}
                >
                  {piece && (
                    <div className={`checkers-piece ${piece.owner === 'player1' ? 'red' : 'black'} ${piece.name === 'king' ? 'king' : ''}`}>
                      {piece.name === 'king' && <span className="checkers-crown">&#9813;</span>}
                    </div>
                  )}
                  {isDestination && <div className="checkers-dest-dot" />}
                </div>
              )
            })}
          </div>
        ))}
      </div>
      {!disabled && moveOptions.length > 0 && (
        <div className="checkers-hint">
          {selectedPiece ? 'Click a highlighted square to move there' : 'Click one of your red pieces to move it'}
        </div>
      )}
    </div>
  )
}

function BlackjackBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const dealerHand = zones.hand_p2?.cards || []
  const holeSize = zones.hole_card?.size || 0
  const lastAction = vars.last_action || ''
  const phase = vars.phase || 'player'
  const p1Bust = vars.p1_bust
  const p2Bust = vars.p2_bust

  const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }

  const handValue = (cards) => {
    let val = 0, aces = 0
    for (const c of cards) {
      if (['J','Q','K'].includes(c.rank)) val += 10
      else if (c.rank === 'A') { val += 11; aces++ }
      else val += parseInt(c.rank)
    }
    while (val > 21 && aces > 0) { val -= 10; aces-- }
    return val
  }

  const handleHit = () => {
    const move = state.legal_moves?.find(m => m.rule === 'hit')
    if (move) onMove(move.rule, move.params)
  }

  const handleStand = () => {
    const move = state.legal_moves?.find(m => m.rule === 'stand')
    if (move) onMove(move.rule, move.params)
  }

  const renderCard = (card) => (
    <div key={card.id} className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}
         style={{ cursor: 'default' }}>
      <span className="gofish-card-rank">{card.rank}</span>
      <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
    </div>
  )

  return (
    <div className="blackjack-board">
      <div className="blackjack-dealer">
        <div className="blackjack-label">Dealer {phase === 'done' ? `(${handValue(dealerHand)})` : ''} {p2Bust === 'True' || p2Bust === true ? 'BUST!' : ''}</div>
        <div className="gofish-cards">
          {dealerHand.map(renderCard)}
          {holeSize > 0 && <div className="gofish-card-back" style={{ width: 52, height: 74 }} />}
        </div>
      </div>

      {lastAction && <div className="blackjack-action">{lastAction}</div>}

      <div className="blackjack-player">
        <div className="blackjack-label">Your hand ({handValue(myHand)}) {p1Bust === 'True' || p1Bust === true ? 'BUST!' : ''}</div>
        <div className="gofish-cards">
          {myHand.map(renderCard)}
        </div>
      </div>

      {phase === 'player' && !disabled && (
        <div className="blackjack-buttons">
          <button className="action-btn action-btn-primary" onClick={handleHit}>Hit</button>
          <button className="action-btn" onClick={handleStand}>Stand</button>
        </div>
      )}
    </div>
  )
}

function CrazyEightsBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const deckSize = zones.deck?.size || 0
  const discardCards = zones.discard?.cards || []
  const topCard = discardCards.length > 0 ? discardCards[discardCards.length - 1] : null
  const activeSuit = vars.active_suit || ''
  const lastAction = vars.last_action || ''
  const lastPlay = vars.last_play || ''
  const isMyTurn = state.current_player === 'player1'

  const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }

  // Abbreviate long Uno action card names to fit card bounds
  const unoLabel = (rank) => {
    const labels = { 'Reverse': 'REV', 'Skip': 'SKIP', 'Draw2': '+2', 'WildDraw4': '+4', 'Wild': 'W' }
    return labels[rank] || rank
  }
  const isUnoGame = ['red','blue','green','yellow','wild'].includes(myHand[0]?.suit)

  // Find playable card IDs from legal moves
  const playableIds = new Set()
  const canDraw = state.legal_moves?.some(m => m.rule === 'draw_card')
  for (const m of (state.legal_moves || [])) {
    if (m.params.card_id != null) playableIds.add(m.params.card_id)
  }

  const handlePlay = (cardId) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.params.card_id === cardId)
    if (move) onMove(move.rule, move.params)
  }

  const handleDraw = () => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.rule === 'draw_card')
    if (move) onMove(move.rule, move.params)
  }

  return (
    <div className="crazy8-board">
      <div className="crazy8-info">
        <span>Deck: {deckSize} cards remaining</span>
        <span>AI hand: {oppHandSize} cards</span>
      </div>

      <div className="crazy8-table">
        <div className="crazy8-deck-pile">
        </div>
        {topCard && (
          <div className={`crazy8-top-card ${
            ['red','blue','green','yellow','wild'].includes(topCard.suit)
              ? `uno-${topCard.suit}`
              : topCard.suit === 'hearts' || topCard.suit === 'diamonds' ? 'red' : 'black'
          }`}>
            <span className="crazy8-card-rank">{isUnoGame ? unoLabel(topCard.rank) : topCard.rank}</span>
            <span className="crazy8-card-suit">{SUIT_SYMBOLS[topCard.suit]}</span>
          </div>
        )}
        {activeSuit && (
          <div className="crazy8-active-suit">Active suit: {SUIT_SYMBOLS[activeSuit] || activeSuit}</div>
        )}
      </div>

      {lastPlay && (
        <div className="crazy8-last-action">
          {lastAction === 'draw' ? 'Drew a card' : `Played ${lastPlay}`}
        </div>
      )}

      <div className="crazy8-my-hand">
        <div className="crazy8-hand-label">Your hand — play a matching card</div>
        <div className="gofish-cards">
          {myHand.map((card) => {
            const playable = playableIds.has(card.id)
            return (
              <button
                key={card.id}
                className={`gofish-card ${
                  ['red','blue','green','yellow','wild'].includes(card.suit)
                    ? `uno-${card.suit}`
                    : card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'
                } ${!playable ? 'disabled' : ''} ${card.rank === '8' || card.suit === 'wild' ? 'wild' : ''}`}
                onClick={() => playable && handlePlay(card.id)}
                disabled={disabled || !isMyTurn || !playable}
              >
                <span className="gofish-card-rank">{isUnoGame ? unoLabel(card.rank) : card.rank}</span>
                <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
              </button>
            )
          })}
        </div>
        {canDraw && isMyTurn && !disabled && (
          <button className="crazy8-draw-btn" onClick={handleDraw}>
            Draw from deck
          </button>
        )}
      </div>
    </div>
  )
}

function GoFishBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const pondSize = zones.pond?.size || 0
  const mySets = (zones.sets_p1?.size || 0) / 4
  const oppSets = (zones.sets_p2?.size || 0) / 4
  const mySetCards = zones.sets_p1?.cards || []
  const oppSetCards = zones.sets_p2?.cards || []
  // Group set cards by rank to show completed sets
  const groupByRank = (cards) => {
    const groups = {}
    cards.forEach(c => { groups[c.rank] = (groups[c.rank] || 0) + 1 })
    return Object.keys(groups)
  }
  const mySetRanks = groupByRank(mySetCards)
  const oppSetRanks = groupByRank(oppSetCards)
  const lastResult = vars.last_result || ''
  const lastAskRank = vars.last_ask_rank || ''
  const lastAskPlayer = vars.last_ask_player || ''
  const isMyTurn = state.current_player === 'player1'

  // Group hand by rank for display
  const rankCounts = {}
  myHand.forEach(c => {
    rankCounts[c.rank] = (rankCounts[c.rank] || 0) + 1
  })

  const handleAsk = (rank) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.params.rank === rank)
    if (move) onMove(move.rule, move.params)
  }

  const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }

  return (
    <div className="gofish-board">
      <div className="gofish-info-bar">
        <div className="gofish-score">
          <span className="gofish-score-you">
            Your sets: <strong>{Math.floor(mySets)}</strong>
            {mySetRanks.length > 0 && <span className="gofish-set-ranks"> ({mySetRanks.join(', ')})</span>}
          </span>
          <span className="gofish-score-ai">
            AI sets: <strong>{Math.floor(oppSets)}</strong>
            {oppSetRanks.length > 0 && <span className="gofish-set-ranks"> ({oppSetRanks.join(', ')})</span>}
          </span>
        </div>
        <div className="gofish-pond">Pond: {pondSize} cards</div>
      </div>

      <div className="gofish-opponent">
        <div className="gofish-opp-label">AI's hand</div>
        <div className="gofish-card-backs">
          {Array.from({ length: Math.min(oppHandSize, 10) }).map((_, i) => (
            <div key={i} className="gofish-card-back" />
          ))}
          {oppHandSize > 10 && <span className="gofish-more">+{oppHandSize - 10}</span>}
        </div>
      </div>

      {lastResult && (
        <div className={`gofish-result ${lastResult.includes('Go Fish') ? 'gofish-miss' : 'gofish-hit'}`}>
          {lastAskPlayer === 'player1' ? 'You' : 'AI'} asked for {lastAskRank}s — {lastResult}
        </div>
      )}

      <div className="gofish-my-hand">
        <div className="gofish-hand-label">Your hand — tap a rank to ask for it</div>
        <div className="gofish-cards">
          {myHand.map((card, i) => (
            <button
              key={card.id}
              className={`gofish-card ${disabled || !isMyTurn ? 'disabled' : ''} ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}
              onClick={() => handleAsk(card.rank)}
              disabled={disabled || !isMyTurn}
            >
              <span className="gofish-card-rank">{card.rank}</span>
              <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function WarBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const p1Size = zones.hand_p1?.size || 0
  const p2Size = zones.hand_p2?.size || 0
  const lastP1 = vars.last_p1_card || ''
  const lastP2 = vars.last_p2_card || ''
  const roundWinner = vars.round_winner || ''

  const handleBattle = () => {
    if (disabled) return
    const moves = state.legal_moves
    if (moves && moves.length > 0) {
      onMove(moves[0].rule, moves[0].params)
    }
  }

  return (
    <div className="war-board">
      <div className="war-players">
        <div className="war-player">
          <div className="war-deck-pile war-p1-pile">
            <span className="war-card-count">{p1Size}</span>
          </div>
          <div className="war-player-label">You</div>
        </div>

        <div className="war-center">
          {lastP1 && lastP2 ? (
            <div className="war-flipped">
              <div className="war-card war-card-p1">{lastP1}</div>
              <div className="war-vs">vs</div>
              <div className="war-card war-card-p2">{lastP2}</div>
            </div>
          ) : (
            <div className="war-prompt">Flip cards!</div>
          )}
          {roundWinner && (
            <div className={`war-round-result ${roundWinner === 'war' ? 'war-tie' : ''}`}>
              {roundWinner === 'player1' ? 'You win this round!' :
               roundWinner === 'player2' ? 'AI wins this round!' :
               roundWinner === 'war' ? 'WAR!' : ''}
            </div>
          )}
        </div>

        <div className="war-player">
          <div className="war-deck-pile war-p2-pile">
            <span className="war-card-count">{p2Size}</span>
          </div>
          <div className="war-player-label">AI</div>
        </div>
      </div>

      {!state.game_result && (
        <button className="war-flip-btn" onClick={handleBattle} disabled={disabled}>
          Flip Cards
        </button>
      )}
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

  // Compute cell center coordinates for SVG overlay
  const cellSize = 96
  const boardW = cols * cellSize
  const boardH = rows * cellSize
  const getCellCenter = (num) => {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (getSpaceNumber(r, c) === num) {
          return { x: c * cellSize + cellSize / 2, y: r * cellSize + cellSize / 2 }
        }
      }
    }
    return { x: 0, y: 0 }
  }

  // Build ladder SVG (two parallel rails + rungs)
  const renderLadder = (from, to) => {
    const a = getCellCenter(from)
    const b = getCellCenter(to)
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len = Math.sqrt(dx * dx + dy * dy)
    // Perpendicular offset for rails
    const px = (-dy / len) * 8
    const py = (dx / len) * 8
    // Rungs
    const rungCount = Math.max(2, Math.floor(len / 30))
    const rungs = []
    for (let i = 1; i <= rungCount; i++) {
      const t = i / (rungCount + 1)
      const mx = a.x + dx * t
      const my = a.y + dy * t
      rungs.push(<line key={i} x1={mx + px} y1={my + py} x2={mx - px} y2={my - py}
        stroke="#4aba5a" strokeWidth="2" strokeLinecap="round" opacity="0.7" />)
    }
    return (
      <g key={`l${from}`}>
        <line x1={a.x + px} y1={a.y + py} x2={b.x + px} y2={b.y + py}
          stroke="#4aba5a" strokeWidth="3" strokeLinecap="round" opacity="0.6" />
        <line x1={a.x - px} y1={a.y - py} x2={b.x - px} y2={b.y - py}
          stroke="#4aba5a" strokeWidth="3" strokeLinecap="round" opacity="0.6" />
        {rungs}
      </g>
    )
  }

  // Build chute SVG (wavy line)
  const renderChute = (from, to) => {
    const a = getCellCenter(from)
    const b = getCellCenter(to)
    const mx = (a.x + b.x) / 2
    const my = (a.y + b.y) / 2
    // Perpendicular offset for curve
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len = Math.sqrt(dx * dx + dy * dy)
    const px = (-dy / len) * 20
    const py = (dx / len) * 20
    return (
      <g key={`c${from}`}>
        <path
          d={`M ${a.x} ${a.y} Q ${mx + px} ${my + py} ${b.x} ${b.y}`}
          fill="none" stroke="#e04040" strokeWidth="5" strokeLinecap="round" opacity="0.5" />
        <path
          d={`M ${a.x} ${a.y} Q ${mx + px} ${my + py} ${b.x} ${b.y}`}
          fill="none" stroke="#ff6060" strokeWidth="2" strokeLinecap="round" opacity="0.4"
          strokeDasharray="4 6" />
      </g>
    )
  }

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
        <svg className="cl-svg-overlay" viewBox={`0 0 ${boardW} ${boardH}`} preserveAspectRatio="none">
          {Object.entries(ladders).map(([f, t]) => renderLadder(Number(f), Number(t)))}
          {Object.entries(chutes).map(([f, t]) => renderChute(Number(f), Number(t)))}
        </svg>
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
