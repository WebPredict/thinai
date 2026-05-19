import { useState } from 'react'

/**
 * Generic track/race board for novel games.
 * Renders a winding path of numbered spaces with pieces on them.
 */
function TrackBoard({ state, onMove, disabled }) {
  if (!state) return null
  if (state.board_type !== 'track') return null

  const trackLength = state.track_length || 20
  const spaces = state.spaces || {}
  const legalMoves = state.legal_moves || []
  const isMyTurn = state.current_player === 'player1'

  // Parse pieces at each space
  const getCheckers = (idx) => {
    const key = String(idx)
    const pieces = spaces[key]
    if (!pieces) return []
    if (Array.isArray(pieces)) return pieces
    if (pieces?.owner) return [pieces]
    return []
  }

  // Legal move targets
  const canRoll = legalMoves.some(m => m.rule === 'roll_and_move' || m.params?.chance)
  const moveTargets = new Set()
  for (const m of legalMoves) {
    if (m.params?.target?.index != null) moveTargets.add(m.params.target.index)
    if (m.params?.space?.index != null) moveTargets.add(m.params.space.index)
  }

  const handleMove = (idx) => {
    if (disabled || !isMyTurn) return
    const move = legalMoves.find(m =>
      m.params?.target?.index === idx || m.params?.space?.index === idx
    )
    if (move) onMove(move.rule, move.params)
  }

  const handleRoll = () => {
    if (disabled) return
    const move = legalMoves.find(m => m.rule === 'roll_and_move' || m.params?.chance)
    if (move) onMove(move.rule, move.params)
  }

  // Layout: 5 columns, winding path
  const COLS = Math.min(5, trackLength)
  const rows = []
  let idx = 0
  let rowNum = 0
  while (idx < trackLength) {
    const row = []
    for (let c = 0; c < COLS && idx < trackLength; c++) {
      row.push(idx)
      idx++
    }
    // Reverse every other row for snake pattern
    if (rowNum % 2 === 1) row.reverse()
    rows.push(row)
    rowNum++
  }

  const lastPlay = state.state_vars?.last_play || ''

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ display: 'inline-block', background: 'var(--bg-raised)', borderRadius: '8px', padding: '12px', border: '1px solid var(--rule-bright)' }}>
        {rows.map((row, ri) => (
          <div key={ri} style={{ display: 'flex', gap: '3px', marginBottom: '3px' }}>
            {row.map(spaceIdx => {
              const checkers = getCheckers(spaceIdx)
              const isTarget = moveTargets.has(spaceIdx)
              const isStart = spaceIdx === 0
              const isEnd = spaceIdx === trackLength - 1
              return (
                <div key={spaceIdx}
                  onClick={() => isTarget && handleMove(spaceIdx)}
                  style={{
                    width: '52px', height: '52px',
                    background: isEnd ? 'rgba(60,160,80,0.2)' : isStart ? 'rgba(212,166,86,0.15)' : 'var(--bg)',
                    border: `1px solid ${isTarget ? 'var(--accent)' : 'var(--rule-bright)'}`,
                    borderRadius: '6px',
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    cursor: isTarget ? 'pointer' : 'default',
                    position: 'relative',
                  }}>
                  <span style={{ fontSize: '0.6rem', color: 'var(--ink-faint)', position: 'absolute', top: '2px', left: '4px' }}>
                    {spaceIdx + 1}
                  </span>
                  {checkers.map((p, i) => (
                    <div key={i} style={{
                      width: '16px', height: '16px', borderRadius: '50%',
                      background: p.owner === 'player1' ? 'var(--accent)' : 'var(--p2-color)',
                      border: `1.5px solid ${p.owner === 'player1' ? '#8a6d36' : '#5a7a9a'}`,
                    }} />
                  ))}
                  {isEnd && checkers.length === 0 && (
                    <span style={{ fontSize: '0.7rem', color: '#5cba6e' }}>END</span>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {lastPlay && (
        <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.85rem', color: 'var(--ink-dim)', marginTop: '0.5rem' }}>
          {lastPlay}
        </div>
      )}

      {canRoll && isMyTurn && (
        <button className="crazy8-draw-btn" onClick={handleRoll} style={{ display: 'block', margin: '0.5rem auto' }}>
          Roll dice
        </button>
      )}
    </div>
  )
}

export default TrackBoard
