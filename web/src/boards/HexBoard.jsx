import { useState } from 'react'

function HexBoard({ state, onMove, disabled, gameType, aiLastMove }) {
  if (!state) return null
  if (state.board_type !== 'grid' && !(state.rows && state.cols)) return null

  const { rows, cols, spaces, legal_moves } = state
  const HEX_W = 48
  const HEX_H = 42
  const ROW_OFFSET = HEX_W * 0.5  // each row shifts right by half a hex

  const handleCellClick = (row, col) => {
    if (disabled) return
    const move = legal_moves.find(m =>
      m.params.target?.row === row && m.params.target?.col === col
    )
    if (move) onMove(move.rule, move.params)
  }

  const isLegal = (row, col) => {
    return legal_moves.some(m =>
      m.params.target?.row === row && m.params.target?.col === col
    )
  }

  const totalWidth = cols * HEX_W + (rows - 1) * ROW_OFFSET + 40
  const totalHeight = rows * (HEX_H * 0.78) + HEX_H * 0.25 + 30

  return (
    <div style={{ textAlign: 'center' }}>
      {/* Top edge label (Red) */}
      <div style={{
        display: 'flex', justifyContent: 'center', marginBottom: '4px',
        paddingLeft: `${ROW_OFFSET * 0}px`,
      }}>
        <div style={{
          background: '#c83030', color: 'white', padding: '2px 40px',
          fontSize: '0.7rem', fontFamily: 'Menlo, monospace', borderRadius: '3px 3px 0 0',
          letterSpacing: '0.1em',
        }}>RED (you)</div>
      </div>

      <div style={{ position: 'relative', display: 'inline-block' }}>
        {/* Left edge (Blue) */}
        <div style={{
          position: 'absolute', left: '-20px', top: '10px', bottom: '10px', width: '14px',
          background: 'linear-gradient(to bottom right, #2060d0, #2060d0)',
          borderRadius: '3px', writingMode: 'vertical-lr', textAlign: 'center',
          color: 'white', fontSize: '0.6rem', fontFamily: 'Menlo, monospace',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          letterSpacing: '0.1em', transform: 'skewY(20deg)', transformOrigin: 'top left',
        }}>BLUE</div>

        {/* Right edge (Blue) */}
        <div style={{
          position: 'absolute', right: '-20px', top: '10px', bottom: '10px', width: '14px',
          background: '#2060d0',
          borderRadius: '3px', writingMode: 'vertical-lr', textAlign: 'center',
          color: 'white', fontSize: '0.6rem', fontFamily: 'Menlo, monospace',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          letterSpacing: '0.1em', transform: 'skewY(-20deg)', transformOrigin: 'top right',
        }}>BLUE</div>

        <svg width={totalWidth} height={totalHeight} style={{ display: 'block' }}>
          {Array.from({ length: rows }, (_, r) =>
            Array.from({ length: cols }, (_, c) => {
              const x = c * HEX_W + r * ROW_OFFSET + HEX_W / 2 + 10
              const y = r * (HEX_H * 0.78) + HEX_H / 2 + 5
              const key = `${r},${c}`
              const piece = spaces[key]
              const legal = !disabled && isLegal(r, c)

              // Hexagon points (flat-top)
              const hw = HEX_W / 2 - 1
              const hh = HEX_H / 2 - 1
              const points = [
                [x - hw, y],
                [x - hw/2, y - hh],
                [x + hw/2, y - hh],
                [x + hw, y],
                [x + hw/2, y + hh],
                [x - hw/2, y + hh],
              ].map(([px, py]) => `${px},${py}`).join(' ')

              return (
                <g key={key} onClick={() => legal && handleCellClick(r, c)}
                   style={{ cursor: legal ? 'pointer' : 'default' }}>
                  <polygon
                    points={points}
                    fill={legal ? 'rgba(212,166,86,0.25)' : '#d4cbb8'}
                    stroke="#888"
                    strokeWidth="1"
                  />
                  {legal && (
                    <polygon
                      points={points}
                      fill="transparent"
                      stroke="transparent"
                      strokeWidth="0"
                      onMouseEnter={e => e.target.parentElement.querySelector('polygon').setAttribute('fill', 'rgba(212,166,86,0.45)')}
                      onMouseLeave={e => e.target.parentElement.querySelector('polygon').setAttribute('fill', 'rgba(212,166,86,0.25)')}
                    />
                  )}
                  {piece && (
                    <circle
                      cx={x} cy={y}
                      r={HEX_W / 2 - 6}
                      fill={piece.owner === 'player1' ? '#c83030' : '#2060d0'}
                      stroke={piece.owner === 'player1' ? '#8a1818' : '#1545a0'}
                      strokeWidth="2"
                    />
                  )}
                </g>
              )
            })
          )}
          {/* Row numbers on left */}
          {Array.from({ length: rows }, (_, r) => {
            const y = r * (HEX_H * 0.78) + HEX_H / 2 + 5
            const x = r * ROW_OFFSET - 2
            return (
              <text key={`row-${r}`} x={x} y={y + 4} fill="#7a6e5c"
                    fontSize="10" fontFamily="Menlo, monospace" textAnchor="end">
                {r + 1}
              </text>
            )
          })}
        </svg>
      </div>

      {/* Bottom edge label (Red) */}
      <div style={{
        display: 'flex', justifyContent: 'center', marginTop: '4px',
      }}>
        <div style={{
          background: '#c83030', color: 'white', padding: '2px 40px',
          fontSize: '0.7rem', fontFamily: 'Menlo, monospace', borderRadius: '0 0 3px 3px',
          letterSpacing: '0.1em',
        }}>RED (you)</div>
      </div>
    </div>
  )
}

export default HexBoard
