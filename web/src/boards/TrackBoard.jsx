import { useState } from 'react'

/**
 * Generic track/race board for novel games.
 * Renders a horizontal winding track with arrows showing direction.
 */
function TrackBoard({ state, onMove, disabled }) {
  if (!state) return null
  if (state.board_type !== 'track') return null

  const trackLength = state.track_length || 20
  const spaces = state.spaces || {}
  const legalMoves = state.legal_moves || []
  const isMyTurn = state.current_player === 'player1'
  const lastPlay = state.state_vars?.last_play || ''

  const getCheckers = (idx) => {
    const key = String(idx)
    const pieces = spaces[key]
    if (!pieces) return []
    if (Array.isArray(pieces)) return pieces
    if (pieces?.owner) return [pieces]
    return []
  }

  const handleRoll = () => {
    if (disabled) return
    const rollMoves = legalMoves.filter(m => m.rule === 'roll_and_move' || m.rule === 'roll_dice')
    if (rollMoves.length > 0) {
      const move = rollMoves[Math.floor(Math.random() * rollMoves.length)]
      onMove(move.rule, move.params)
    }
  }

  const canRoll = legalMoves.some(m => m.rule === 'roll_and_move' || m.rule === 'roll_dice')

  // Layout: rows of 10, snaking
  const COLS = 10
  const rows = []
  let idx = 0
  let rowNum = 0
  while (idx < trackLength) {
    const row = []
    for (let c = 0; c < COLS && idx < trackLength; c++) {
      row.push(idx)
      idx++
    }
    if (rowNum % 2 === 1) row.reverse()
    rows.push(row)
    rowNum++
  }

  const CW = 56, CH = 56

  return (
    <div style={{ textAlign: 'center', width: '100%', overflowX: 'auto' }}>
      <div style={{ display: 'inline-block', padding: '8px' }}>
        {rows.map((row, ri) => (
          <div key={ri}>
            <div style={{ display: 'flex', gap: '0px', alignItems: 'center' }}>
              {row.map((spaceIdx, ci) => {
                const checkers = getCheckers(spaceIdx)
                const isStart = spaceIdx === 0
                const isEnd = spaceIdx === trackLength - 1
                const isLastInRow = ci === row.length - 1
                const goesRight = ri % 2 === 0

                return (
                  <div key={spaceIdx} style={{ display: 'flex', alignItems: 'center' }}>
                    <div style={{
                      width: `${CW}px`, height: `${CH}px`,
                      background: isEnd ? 'rgba(60,160,80,0.3)' : isStart ? 'rgba(212,166,86,0.2)' : 'var(--bg-raised)',
                      border: `2px solid ${isEnd ? '#5cba6e' : isStart ? 'var(--accent-dim)' : 'var(--rule-bright)'}`,
                      borderRadius: '8px',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      gap: '3px', position: 'relative',
                    }}>
                      {isStart && checkers.length === 0 && (
                        <span style={{ fontSize: '0.6rem', color: 'var(--accent)', fontFamily: 'Menlo, monospace' }}>START</span>
                      )}
                      {isEnd && checkers.length === 0 && (
                        <span style={{ fontSize: '0.6rem', color: '#5cba6e', fontFamily: 'Menlo, monospace', fontWeight: 'bold' }}>FINISH</span>
                      )}
                      {checkers.map((p, i) => (
                        <div key={i} style={{
                          width: '22px', height: '22px', borderRadius: '50%',
                          background: p.owner === 'player1' ? 'var(--accent)' : 'var(--p2-color)',
                          border: `2px solid ${p.owner === 'player1' ? '#8a6d36' : '#5a7a9a'}`,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                        }} />
                      ))}
                    </div>
                    {/* Arrow between cells in same row */}
                    {!isLastInRow && (
                      <span style={{ color: 'var(--ink-faint)', fontSize: '1.6rem', margin: '0 2px', userSelect: 'none' }}>
                        {goesRight ? '→' : '←'}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
            {/* Down arrow between rows */}
            {ri < rows.length - 1 && (
              <div style={{
                textAlign: ri % 2 === 0 ? 'right' : 'left',
                padding: ri % 2 === 0 ? '0 20px 0 0' : '0 0 0 20px',
                color: 'var(--ink-faint)', fontSize: '1.8rem', lineHeight: '1',
                userSelect: 'none',
              }}>
                ↓
              </div>
            )}
          </div>
        ))}
      </div>

      {lastPlay && (
        <div style={{
          fontFamily: 'Menlo, monospace', fontSize: '0.9rem',
          color: 'var(--ink)', marginTop: '0.5rem',
        }}>
          {lastPlay}
        </div>
      )}

      {canRoll && isMyTurn && (
        <button className="crazy8-draw-btn" onClick={handleRoll}
          style={{ display: 'block', margin: '0.75rem auto', fontSize: '1rem', padding: '0.5rem 2rem' }}>
          🎲 Roll dice
        </button>
      )}

      {isMyTurn && legalMoves.some(m => m.rule === 'move_forward') && (
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', margin: '0.5rem 0' }}>
          <button className="crazy8-draw-btn" onClick={() => {
            const m = legalMoves.find(mv => mv.rule === 'move_forward')
            if (m) onMove(m.rule, m.params)
          }} style={{ fontSize: '1rem', padding: '0.5rem 1.5rem' }}>
            ⬆ Move Forward
          </button>
          <button className="crazy8-draw-btn" onClick={() => {
            const m = legalMoves.find(mv => mv.rule === 'move_backward')
            if (m) onMove(m.rule, m.params)
          }} style={{ fontSize: '1rem', padding: '0.5rem 1.5rem' }}>
            ⬇ Move Backward
          </button>
        </div>
      )}
    </div>
  )
}

export default TrackBoard
