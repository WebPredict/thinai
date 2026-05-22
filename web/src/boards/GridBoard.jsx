import { useState } from 'react'
import { icons } from '../icons/game-icons'

function GridBoard({ state, onMove, disabled, gameType, aiLastMove }) {
  const [hoverCol, setHoverCol] = useState(null)
  const [selectedPiece, setSelectedPiece] = useState(null)

  if (!state) return null
  // Accept grid board_type or any state with rows/cols (custom games)
  if (state.board_type !== 'grid' && !(state.rows && state.cols)) return null

  const { rows, cols, spaces, legal_moves } = state
  const isC4 = gameType === 'connect_four'
  const isTTT = gameType === 'tictactoe'
  const isReversi = gameType === 'reversi'
  const isHex = gameType === 'hex'
  const cosmetics = state.cosmetics || {}
  const p1Color = cosmetics.player1_color || '#d4a656'
  const p2Color = cosmetics.player2_color || '#8ab4d6'
  const boardColor = cosmetics.board_color || null
  const isCheckerboard = cosmetics.board_pattern === 'checkerboard'

  // Determine which cell the AI last played
  const aiRow = aiLastMove?.target?.row ?? null
  const aiCol = aiLastMove?.target?.col ?? aiLastMove?.column ?? null

  const isColumnBased = legal_moves.length > 0 && 'column' in (legal_moves[0]?.params || {})
  // Movement games: moves have from/to data
  const isMovementGame = legal_moves.length > 0 && legal_moves[0]?.from != null

  // Build movement lookup for click-to-move
  const movesFromPiece = {}
  const movablePieces = new Set()
  if (isMovementGame) {
    for (const m of legal_moves) {
      if (m.from && m.to) {
        const fromKey = `${m.from.row},${m.from.col}`
        const toKey = `${m.to.row},${m.to.col}`
        movablePieces.add(fromKey)
        if (!movesFromPiece[fromKey]) movesFromPiece[fromKey] = []
        movesFromPiece[fromKey].push({ move: m, toKey })
      }
    }
  }

  const validDestinations = new Set()
  if (selectedPiece && movesFromPiece[selectedPiece]) {
    for (const { toKey } of movesFromPiece[selectedPiece]) {
      validDestinations.add(toKey)
    }
  }

  const handleCellClick = (row, col) => {
    if (disabled) return
    const key = `${row},${col}`

    if (isMovementGame) {
      // Click-to-move: select piece, then click destination
      if (movablePieces.has(key)) {
        setSelectedPiece(selectedPiece === key ? null : key)
        return
      }
      if (selectedPiece && validDestinations.has(key)) {
        const moveEntry = movesFromPiece[selectedPiece].find(m => m.toKey === key)
        if (moveEntry) {
          onMove(moveEntry.move.rule, moveEntry.move.params)
          setSelectedPiece(null)
        }
        return
      }
      setSelectedPiece(null)
      return
    }

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
    if (isMovementGame) return false  // handled by movable/destination highlighting
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

    // Generic piece for custom/unknown games — try icon first, fall back to stone
    const color = piece.owner === 'player1' ? p1Color : p2Color
    const iconName = piece.name?.toLowerCase()
    const iconFn = icons[iconName]
    if (iconFn) {
      return (
        <div className="piece" style={{ width: 36, height: 36, filter: 'drop-shadow(0 0 1.5px rgba(0,0,0,0.6))' }}
             dangerouslySetInnerHTML={{ __html:
               `<svg viewBox="0 0 24 24" width="36" height="36">${iconFn(color)}</svg>`
             }} />
      )
    }
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
    isHex ? 'hex-board' : '',
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

      // Checkerboard pattern for custom games
      const cellBg = isCheckerboard && (r + c) % 2 === 1
        ? 'rgba(255,255,255,0.08)'
        : boardColor && !isC4 && !isTTT && !isReversi
          ? undefined : undefined

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
            isMovementGame && movablePieces.has(key) ? 'movable' : '',
            isMovementGame && selectedPiece === key ? 'selected' : '',
            isMovementGame && validDestinations.has(key) ? 'destination' : '',
          ].filter(Boolean).join(' ')}
          style={isCheckerboard ? { background: (r + c) % 2 === 0 ? '#d4c8a0' : '#8a7a5a' } : boardColor && !isC4 && !isTTT && !isReversi ? { background: boardColor } : undefined}
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

  return <div className={boardClass}>
    {grid}
    {isMovementGame && !disabled && legal_moves.length > 0 && (
      <div style={{ textAlign: 'center', fontFamily: 'Menlo, monospace', fontSize: '0.8rem', color: 'var(--ink)', marginTop: '0.5rem' }}>
        {selectedPiece ? 'Click a highlighted square to move' : 'Click one of your pieces to move it'}
      </div>
    )}
  </div>
}

export default GridBoard
