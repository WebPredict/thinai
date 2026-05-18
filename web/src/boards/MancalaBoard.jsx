import { useState } from 'react'

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

export default MancalaBoard
