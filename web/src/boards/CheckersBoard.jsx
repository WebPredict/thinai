import { useState } from 'react'

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

export default CheckersBoard
