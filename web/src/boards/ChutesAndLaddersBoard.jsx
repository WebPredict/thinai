import { useState } from 'react'

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

export default ChutesAndLaddersBoard
