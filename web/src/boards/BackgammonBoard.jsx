import { useState } from 'react'

function BackgammonBoard({ state, onMove, disabled }) {
  const [selectedPt, setSelectedPt] = useState(null)

  if (!state) return null

  const vars = state.state_vars || {}
  const phase = vars.phase || 'roll'
  const die1 = vars.die1 || 0
  const die2 = vars.die2 || 0
  const remaining = vars.moves_remaining || ''
  const lastPlay = vars.last_play || ''
  const isMyTurn = state.current_player === 'player1'

  const spaces = state.spaces || {}
  const getCheckers = (idx) => {
    const pieces = spaces[String(idx)] || spaces[idx] || []
    if (Array.isArray(pieces)) return pieces
    if (pieces?.owner) return [pieces]
    return []
  }

  const p1Bar = getCheckers(24).filter(p => p.owner === 'player1').length
  const p2Bar = getCheckers(25).filter(p => p.owner === 'player2').length
  const p1Off = getCheckers(26).filter(p => p.owner === 'player1').length
  const p2Off = getCheckers(27).filter(p => p.owner === 'player2').length

  const canRoll = state.legal_moves?.some(m => m.rule === 'roll_dice')

  // Parse all legal moves: {from_point, die_value, move_id, dest}
  const moveOptions = []
  for (const m of (state.legal_moves || [])) {
    if (m.params.move_id != null) {
      const id = m.params.move_id
      if (id === 0) { moveOptions.push({ id: 0, from: -1, die: 0, dest: -1 }); continue }
      const from = Math.floor(id / 100)
      const die = id % 100
      const dest = from === 24 ? (25 - die) : from - die // P1 moves down
      moveOptions.push({ id, from, die, dest })
    }
  }

  // Group moves by source point
  const movesByFrom = {}
  for (const m of moveOptions) {
    if (!movesByFrom[m.from]) movesByFrom[m.from] = []
    movesByFrom[m.from].push(m)
  }

  const movablePoints = new Set(Object.keys(movesByFrom).map(Number))
  const isPassOnly = moveOptions.length === 1 && moveOptions[0].id === 0

  // Destinations from selected point
  const destMoves = selectedPt != null ? (movesByFrom[selectedPt] || []) : []
  const destPoints = new Set(destMoves.map(m => m.dest))

  const handleRoll = () => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.rule === 'roll_dice')
    if (move) onMove(move.rule, move.params)
  }

  const handleClickPoint = (idx) => {
    if (disabled || !isMyTurn || phase !== 'move') return

    // If clicking a destination
    if (selectedPt != null && destPoints.has(idx)) {
      const m = destMoves.find(mv => mv.dest === idx)
      if (m) {
        const move = state.legal_moves?.find(lm => lm.params.move_id === m.id)
        if (move) {
          onMove(move.rule, move.params)
          setSelectedPt(null)
        }
      }
      return
    }

    // If clicking bear-off area (dest < 0)
    if (selectedPt != null && idx === -1 && destMoves.some(m => m.dest < 0)) {
      const m = destMoves.find(mv => mv.dest < 0)
      if (m) {
        const move = state.legal_moves?.find(lm => lm.params.move_id === m.id)
        if (move) {
          onMove(move.rule, move.params)
          setSelectedPt(null)
        }
      }
      return
    }

    // If clicking a movable source
    if (movablePoints.has(idx)) {
      setSelectedPt(idx === selectedPt ? null : idx)
      return
    }

    setSelectedPt(null)
  }

  const handlePass = () => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.params.move_id === 0)
    if (move) onMove(move.rule, move.params)
  }

  // Board dimensions
  const W = 720, H = 460
  const BAR_W = 30
  const HALF = (W - BAR_W) / 2
  const PW = HALF / 6
  const PH = H * 0.42
  const CR = PW * 0.33

  const ptColor = (i) => i % 2 === 0 ? '#c85a20' : '#d4c8a0'

  const px = (idx) => {
    if (idx >= 12) {
      const col = idx - 12
      return col < 6 ? col * PW + PW / 2 : col * PW + BAR_W + PW / 2
    } else {
      const col = 11 - idx
      return col < 6 ? col * PW + PW / 2 : col * PW + BAR_W + PW / 2
    }
  }

  const tri = (idx, top) => {
    const x = px(idx), hw = PW / 2 - 1
    const base = top ? 0 : H, tip = top ? PH : H - PH
    const isSelected = selectedPt === idx
    const isDest = destPoints.has(idx)
    const isMovable = movablePoints.has(idx) && !isSelected
    return (
      <g key={`t${idx}`} onClick={() => handleClickPoint(idx)} style={{ cursor: (isMovable || isDest) ? 'pointer' : 'default' }}>
        <polygon points={`${x-hw},${base} ${x},${tip} ${x+hw},${base}`}
                 fill={isSelected ? '#d4a656' : isDest ? '#5cba6e' : ptColor(idx)}
                 stroke={isSelected ? '#e0c070' : isDest ? '#3a8a4e' : '#111'}
                 strokeWidth={isSelected || isDest ? '2' : '0.5'} />
        {isDest && (
          <circle cx={x} cy={top ? PH - 12 : H - PH + 12} r={6}
                  fill="#5cba6e" opacity="0.8" />
        )}
      </g>
    )
  }

  const renderCheckers = (idx, top) => {
    const list = getCheckers(idx)
    if (!list.length) return null
    const x = px(idx)
    const isMovable = movablePoints.has(idx)
    const n = Math.min(list.length, 5)
    return list.slice(0, n).map((p, i) => {
      const y = top ? CR + 3 + i * (CR * 2 + 1) : H - CR - 3 - i * (CR * 2 + 1)
      const isP1 = p.owner === 'player1'
      return (
        <circle key={`c${idx}-${i}`} cx={x} cy={y} r={CR}
                fill={isP1 ? '#f0e8d8' : '#1a1a1a'}
                stroke={isMovable && isP1 ? '#d4a656' : isP1 ? '#b0a080' : '#444'}
                strokeWidth={isMovable && isP1 ? '2.5' : '1.5'}
                style={{ cursor: isMovable && isP1 ? 'pointer' : 'default' }}
                onClick={(e) => { e.stopPropagation(); if (isMovable) handleClickPoint(idx) }}
        />
      )
    }).concat(list.length > 5 ? [
      <text key={`n${idx}`} x={x} y={(top ? CR * 3 + 8 : H - CR * 3 - 4)} textAnchor="middle"
            fill={list[0].owner === 'player1' ? '#333' : '#ddd'} fontSize="10" fontWeight="bold">
        {list.length}
      </text>
    ] : [])
  }

  // Hint text
  let hint = lastPlay
  if (isMyTurn && phase === 'move' && !isPassOnly) {
    if (selectedPt == null) hint = 'Click a highlighted checker to select it'
    else hint = 'Click a green destination to move, or click another checker'
  }

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.85rem', color: 'var(--ink-dim)', margin: '0.4rem 0', display: 'flex', justifyContent: 'center', gap: '1.5rem' }}>
        <span>You: {p1Off}/15 off</span>
        <span>AI: {p2Off}/15 off</span>
        {p1Bar > 0 && <span style={{ color: '#d05040' }}>Bar: {p1Bar}</span>}
        {p2Bar > 0 && <span>AI bar: {p2Bar}</span>}
      </div>

      {die1 > 0 && (
        <div style={{ margin: '0.3rem 0', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px' }}>
          {[die1, die2].map((d, i) => (
            <svg key={i} width="38" height="38" viewBox="0 0 40 40">
              <rect x="1" y="1" width="38" height="38" rx="6" fill="#f5f0e0" stroke="#b0a080" strokeWidth="1" />
              {[1,3,5].includes(d) && <circle cx="20" cy="20" r="3.5" fill="#222" />}
              {d >= 2 && <circle cx="30" cy="10" r="3.5" fill="#222" />}
              {d >= 2 && <circle cx="10" cy="30" r="3.5" fill="#222" />}
              {d >= 4 && <circle cx="10" cy="10" r="3.5" fill="#222" />}
              {d >= 4 && <circle cx="30" cy="30" r="3.5" fill="#222" />}
              {d === 6 && <circle cx="10" cy="20" r="3.5" fill="#222" />}
              {d === 6 && <circle cx="30" cy="20" r="3.5" fill="#222" />}
            </svg>
          ))}
        </div>
      )}

      <svg width={W} height={H} style={{ display: 'block', margin: '0.4rem auto', borderRadius: '8px' }}>
        <rect width={W} height={H} fill="#1a6030" rx="6" />
        <rect x="0" y="0" width={W} height={H} fill="none" stroke="#5a3a18" strokeWidth="6" rx="6" />
        <rect x={HALF} y="0" width={BAR_W} height={H} fill="#3a2a18" />

        {Array.from({length: 12}, (_, i) => tri(12 + i, true))}
        {Array.from({length: 12}, (_, i) => tri(11 - i, false))}

        {Array.from({length: 12}, (_, i) => renderCheckers(12 + i, true))}
        {Array.from({length: 12}, (_, i) => renderCheckers(11 - i, false))}

        {/* Bar checkers — clickable if on bar */}
        {p1Bar > 0 && (
          <g onClick={() => handleClickPoint(24)} style={{ cursor: movablePoints.has(24) ? 'pointer' : 'default' }}>
            <circle cx={HALF + BAR_W/2} cy={H/2 + 25} r={CR}
                    fill="#f0e8d8" stroke={movablePoints.has(24) ? '#d4a656' : '#b0a080'}
                    strokeWidth={movablePoints.has(24) ? '2.5' : '1.5'} />
            {p1Bar > 1 && <text x={HALF + BAR_W/2} y={H/2 + 29} textAnchor="middle" fill="#333" fontSize="9" fontWeight="bold">{p1Bar}</text>}
          </g>
        )}
        {p2Bar > 0 && (
          <g>
            <circle cx={HALF + BAR_W/2} cy={H/2 - 25} r={CR} fill="#1a1a1a" stroke="#444" strokeWidth="1.5" />
            {p2Bar > 1 && <text x={HALF + BAR_W/2} y={H/2 - 21} textAnchor="middle" fill="#ddd" fontSize="9" fontWeight="bold">{p2Bar}</text>}
          </g>
        )}

        {/* Point numbers */}
        {Array.from({length: 12}, (_, i) => (
          <text key={`tn${i}`} x={px(12+i)} y={H - 3} textAnchor="middle"
                fill="rgba(255,255,255,0.35)" fontSize="8" fontFamily="Menlo, monospace">{13+i}</text>
        ))}
        {Array.from({length: 12}, (_, i) => (
          <text key={`bn${i}`} x={px(11-i)} y={10} textAnchor="middle"
                fill="rgba(255,255,255,0.35)" fontSize="8" fontFamily="Menlo, monospace">{12-i}</text>
        ))}
      </svg>

      <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.85rem', color: 'var(--ink-dim)', minHeight: '1.4rem', margin: '0.25rem 0' }}>
        {hint}
      </div>

      {canRoll && isMyTurn && (
        <button className="crazy8-draw-btn" onClick={handleRoll} style={{ display: 'block', margin: '0.5rem auto' }}>
          Roll dice
        </button>
      )}

      {isPassOnly && isMyTurn && phase === 'move' && (
        <button className="crazy8-draw-btn" onClick={handlePass} style={{ display: 'block', margin: '0.5rem auto' }}>
          No legal moves — pass
        </button>
      )}

      {/* Bear-off click target when selected checker can bear off */}
      {selectedPt != null && destMoves.some(m => m.dest < 0) && (
        <button className="crazy8-draw-btn" onClick={() => handleClickPoint(-1)}
                style={{ display: 'block', margin: '0.5rem auto', background: '#5cba6e', borderColor: '#3a8a4e', color: 'white' }}>
          Bear off
        </button>
      )}
    </div>
  )
}

export default BackgammonBoard
