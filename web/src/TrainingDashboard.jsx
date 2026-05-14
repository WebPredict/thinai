import { useState, useEffect, useCallback, useRef } from 'react'

const API = 'http://localhost:8000/api'

function TrainExplainer() {
  const [open, setOpen] = useState(true)
  return (
    <div className="train-explainer">
      <button className="train-explainer-toggle" onClick={() => setOpen(!open)}>
        <span>How training works</span>
        <span className="corrections-chevron">{open ? '\u25B2' : '\u25BC'}</span>
      </button>
      {open && (
        <div className="train-explainer-body">
          <p>
            ThinAI learns each game from scratch through <strong>self-improvement via play</strong>.
            It starts with zero strategic knowledge — just the rules — and develops its own
            understanding of what matters by playing games and observing outcomes.
          </p>
          <p>
            The opponent is a <strong>competent minimax player</strong> (not random), so wins have
            to be earned. After each game, the system adjusts its internal evaluation weights based
            on whether it won or lost. Features present in winning positions are reinforced;
            features present in losing positions are penalized.
          </p>
          <p>
            The <strong>win rate chart</strong> shows a rolling average — you should see it start
            low and climb as the system figures out which board features predict victory.
            The <strong>depth</strong> setting controls how many moves ahead the AI searches.
            Lower depth means the learned evaluation matters more; higher depth means raw search
            compensates for weak evaluation.
          </p>
        </div>
      )}
    </div>
  )
}

const GAME_LABELS = {
  tictactoe: 'Tic-Tac-Toe',
  connect_four: 'Connect Four',
  mancala: 'Mancala',
  reversi: 'Reversi',
  nim: 'Nim',
  chutes_and_ladders: 'Chutes & Ladders',
}

export default function TrainingDashboard({ games }) {
  // Smart defaults per game: low depth so the system starts weak
  // and the learned evaluation actually drives improvement
  const DEFAULTS = {
    tictactoe:    { games: 40, depth: 1 },
    connect_four: { games: 40, depth: 1 },
    mancala:      { games: 40, depth: 1 },
    reversi:      { games: 30, depth: 1 },
  }

  const [selectedGame, setSelectedGame] = useState('tictactoe')
  const [trainingId, setTrainingId] = useState(null)
  const [status, setStatus] = useState(null)
  const [numGames, setNumGames] = useState(DEFAULTS.tictactoe.games)
  const [depth, setDepth] = useState(DEFAULTS.tictactoe.depth)
  const [fresh, setFresh] = useState(true)
  const [memories, setMemories] = useState([])
  const pollRef = useRef(null)

  useEffect(() => {
    fetch(`${API}/memory/games`)
      .then(r => r.json())
      .then(d => setMemories(d.games || []))
      .catch(() => {})
  }, [trainingId, status?.status])

  useEffect(() => {
    if (!trainingId) return
    const poll = () => {
      fetch(`${API}/training/${trainingId}/status`)
        .then(r => r.json())
        .then(d => {
          setStatus(d)
          if (d.status === 'complete') {
            clearInterval(pollRef.current)
          }
        })
        .catch(() => {})
    }
    poll()
    pollRef.current = setInterval(poll, 1500)
    return () => clearInterval(pollRef.current)
  }, [trainingId])

  const startTraining = async () => {
    const res = await fetch(`${API}/training/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game: selectedGame, num_games: numGames, depth, fresh }),
    })
    const data = await res.json()
    setTrainingId(data.training_id)
    setStatus(null)
  }

  const resetMemory = async (gameName) => {
    await fetch(`${API}/memory/${gameName}/reset`, { method: 'POST' })
    setMemories(memories.filter(m => m.game_name !== gameName))
  }

  return (
    <div className="training-dashboard">
      <h2>Train the AI</h2>

      <TrainExplainer />

      <div className="train-config">
        <div className="game-select">
          {(games || []).map(g => (
            <button
              key={g}
              className={selectedGame === g ? 'active' : ''}
              onClick={() => {
                setSelectedGame(g)
                setTrainingId(null)
                setStatus(null)
                const d = DEFAULTS[g] || { games: 40, depth: 1 }
                setNumGames(d.games)
                setDepth(d.depth)
              }}
            >
              {GAME_LABELS[g] || g}
            </button>
          ))}
        </div>
        <div className="train-params">
          <label>
            Games: <input type="number" value={numGames} onChange={e => setNumGames(+e.target.value)} min={5} max={200} />
          </label>
          <label title="Moves ahead to search. In a future phase, the system will learn to manage this itself.">
            Depth: <input type="number" value={depth} onChange={e => setDepth(+e.target.value)} min={1} max={6} />
            <span className="train-param-note">moves ahead</span>
          </label>
        </div>
        <label className="train-fresh-toggle">
          <input type="checkbox" checked={fresh} onChange={e => setFresh(e.target.checked)} />
          <span>Start from scratch</span>
          <span className="train-fresh-hint">
            {fresh
              ? '(zero knowledge — watch it learn)'
              : '(continue from previously learned weights)'}
          </span>
        </label>
        <button
          className="start-btn"
          onClick={startTraining}
          disabled={trainingId && status?.status === 'running'}
        >
          {status?.status === 'running' ? `Training... ${status.games_played}/${status.total_games}` : 'Start Training'}
        </button>
        {status?.status === 'running' && status.snapshots?.length > 0 && (
          <div className="train-progress-info">
            {(() => {
              const totalMs = status.snapshots.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
              const avgMs = totalMs / status.snapshots.length
              const remaining = (status.total_games - status.games_played) * avgMs
              const remainSec = Math.ceil(remaining / 1000)
              return remainSec > 5
                ? `~${remainSec < 60 ? remainSec + 's' : Math.ceil(remainSec / 60) + 'min'} remaining`
                : 'Almost done...'
            })()}
          </div>
        )}
      </div>

      {status && (
        <div className="train-results">
          <LearningCurve snapshots={status.snapshots} totalGames={status.total_games} />
          <WeightInspector weights={status.weights} generation={status.generation} />
        </div>
      )}

      {memories.length > 0 && (
        <div className="memory-panel">
          <h3>Learned Games</h3>
          <div className="memory-list">
            {memories.map(m => (
              <div key={m.game_name} className="memory-card">
                <div className="memory-info">
                  <span className="memory-name">{m.game_name}</span>
                  <span className="memory-gen">{m.generation} games trained</span>
                </div>
                <button className="memory-reset" onClick={() => resetMemory(m.game_name)}>Reset</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function LearningCurve({ snapshots, totalGames }) {
  if (!snapshots || snapshots.length === 0) return null

  const width = 480
  const height = 200
  const pad = { top: 20, right: 20, bottom: 30, left: 45 }
  const chartW = width - pad.left - pad.right
  const chartH = height - pad.top - pad.bottom

  const maxGames = Math.max(totalGames, snapshots.length)
  const xScale = (i) => pad.left + (i / maxGames) * chartW
  const yScale = (v) => pad.top + (1 - v) * chartH

  // Build rolling win rate path
  const points = snapshots.map((s, i) => `${xScale(i + 1)},${yScale(s.rolling_win_rate)}`)
  const pathD = points.length > 1
    ? `M ${points[0]} ` + points.slice(1).map(p => `L ${p}`).join(' ')
    : null

  // Individual outcomes as dots
  const dots = snapshots.map((s, i) => ({
    x: xScale(i + 1),
    y: yScale(s.rolling_win_rate),
    outcome: s.outcome,
  }))

  return (
    <div className="learning-curve">
      <h3>Win Rate</h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="curve-svg">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(v => (
          <g key={v}>
            <line x1={pad.left} y1={yScale(v)} x2={width - pad.right} y2={yScale(v)}
              stroke="var(--rule)" strokeWidth="0.5" />
            <text x={pad.left - 8} y={yScale(v) + 4} textAnchor="end"
              fill="var(--ink-faint)" fontSize="10" fontFamily="monospace">
              {Math.round(v * 100)}%
            </text>
          </g>
        ))}

        {/* 50% reference line */}
        <line x1={pad.left} y1={yScale(0.5)} x2={width - pad.right} y2={yScale(0.5)}
          stroke="var(--ink-faint)" strokeWidth="0.5" strokeDasharray="4 4" />

        {/* Win rate curve */}
        {pathD && (
          <path d={pathD} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
        )}

        {/* Outcome dots */}
        {dots.map((d, i) => (
          <circle key={i} cx={d.x} cy={d.y} r="3"
            fill={d.outcome > 0 ? 'var(--accent)' : d.outcome < 0 ? 'var(--p2-color)' : 'var(--ink-faint)'}
            opacity="0.7" />
        ))}

        {/* X axis tick labels */}
        {(() => {
          const ticks = []
          const step = maxGames <= 20 ? 5 : maxGames <= 50 ? 10 : 20
          for (let t = step; t <= maxGames; t += step) {
            ticks.push(t)
          }
          if (ticks[ticks.length - 1] !== maxGames) ticks.push(maxGames)
          return ticks.map(t => (
            <text key={t} x={xScale(t)} y={height - 4} textAnchor="middle"
              fill="var(--ink-faint)" fontSize="9" fontFamily="monospace">
              {t}
            </text>
          ))
        })()}
      </svg>
    </div>
  )
}

function WeightInspector({ weights, generation }) {
  if (!weights || weights.length === 0) return null

  const maxAbs = Math.max(...weights.map(w => Math.abs(w.weight)), 0.1)
  const sorted = [...weights].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))

  return (
    <div className="weight-inspector">
      <h3>What it learned <span className="gen-badge">{generation} games played</span></h3>

      <div className="weight-explainer">
        <p>
          These weights were discovered during the training session above. The system started
          at zero and adjusted each weight after every game — reinforcing features present in
          wins, penalizing features present in losses. The result is the AI's learned understanding
          of what matters in this game.
        </p>
        <p>
          <strong>Higher weight</strong> = the AI prioritizes that feature when choosing moves.
          For example, in Reversi, the system typically learns that corner control matters far
          more than raw disc count — matching what experienced human players know.
        </p>
      </div>

      <div className="weight-bars">
        {sorted.map(w => {
          const pct = (Math.abs(w.weight) / maxAbs) * 100
          const isPositive = w.weight >= 0
          return (
            <div key={w.feature} className="weight-row">
              <span className="weight-name">{w.feature}</span>
              <div className="weight-detail">{w.description}</div>
              <div className="weight-bar-track">
                <div
                  className={`weight-bar ${isPositive ? 'positive' : 'negative'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className={`weight-value ${isPositive ? 'positive' : 'negative'}`}>
                {w.weight >= 0 ? '+' : ''}{w.weight.toFixed(3)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
