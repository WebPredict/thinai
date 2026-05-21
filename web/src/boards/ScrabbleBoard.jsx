import { useState } from 'react'

const BONUS_SQUARES = {
  '0,0': 'TW', '0,8': 'TW', '8,0': 'TW', '8,8': 'TW',
  '1,1': 'DW', '1,7': 'DW', '7,1': 'DW', '7,7': 'DW',
  '2,2': 'DW', '2,6': 'DW', '6,2': 'DW', '6,6': 'DW',
  '4,4': 'DW',
  '0,3': 'DL', '0,5': 'DL', '8,3': 'DL', '8,5': 'DL',
  '3,0': 'DL', '5,0': 'DL', '3,8': 'DL', '5,8': 'DL',
  '3,3': 'TL', '3,5': 'TL', '5,3': 'TL', '5,5': 'TL',
}

const BONUS_COLORS = {
  TW: { bg: 'rgba(200,48,48,0.3)', border: '#c83030', label: 'TW' },
  DW: { bg: 'rgba(200,120,160,0.3)', border: '#c878a0', label: 'DW' },
  TL: { bg: 'rgba(48,100,200,0.3)', border: '#3064c8', label: 'TL' },
  DL: { bg: 'rgba(100,180,220,0.3)', border: '#64b4dc', label: 'DL' },
}

const LETTER_VALUES = {
  A:1,B:3,C:3,D:2,E:1,F:4,G:2,H:4,I:1,J:8,K:5,L:1,M:3,
  N:1,O:1,P:3,Q:10,R:1,S:1,T:1,U:1,V:4,W:4,X:8,Y:4,Z:10,
}

function ScrabbleBoard({ state, onMove, disabled }) {
  if (!state) return null

  const [selectedRackIdx, setSelectedRackIdx] = useState(null)
  const [pendingTiles, setPendingTiles] = useState({}) // "r,c" -> {letter, rackIdx}
  const [error, setError] = useState('')

  const vars = state.state_vars || {}
  const myRack = vars.rack_p1 || []
  const oppRackSize = (vars.rack_p2 || []).length
  const p1Score = vars.p1_score || 0
  const p2Score = vars.p2_score || 0
  const bagSize = (vars.bag || []).length
  const lastPlay = vars.last_play || ''
  const isMyTurn = state.current_player === 'player1'

  // Board tiles from state
  const boardTiles = {}
  const spaces = state.spaces || {}
  for (const [key, piece] of Object.entries(spaces)) {
    if (piece && piece.name && piece.name.length === 1) {
      boardTiles[key] = piece
    }
  }

  // Legal moves
  const wordMoves = (state.legal_moves || []).filter(m => m.rule === 'place_word')
  const canPass = (state.legal_moves || []).some(m => m.rule === 'pass_turn')

  // Which rack indices are placed on board
  const usedRackIndices = new Set(Object.values(pendingTiles).map(t => t.rackIdx))

  const handleRackClick = (idx) => {
    if (disabled || !isMyTurn || usedRackIndices.has(idx)) return
    setSelectedRackIdx(selectedRackIdx === idx ? null : idx)
    setError('')
  }

  const handleCellClick = (r, c) => {
    if (disabled || !isMyTurn) return
    const key = `${r},${c}`

    // If clicking a pending tile, remove it
    if (pendingTiles[key]) {
      const newPending = { ...pendingTiles }
      delete newPending[key]
      setPendingTiles(newPending)
      setError('')
      return
    }

    // If a rack tile is selected and cell is empty, place it
    if (selectedRackIdx !== null && !boardTiles[key]) {
      setPendingTiles({
        ...pendingTiles,
        [key]: { letter: myRack[selectedRackIdx].letter, rackIdx: selectedRackIdx }
      })
      setSelectedRackIdx(null)
      setError('')
    }
  }

  const handleClear = () => {
    setPendingTiles({})
    setSelectedRackIdx(null)
    setError('')
  }

  const handleSubmit = () => {
    if (Object.keys(pendingTiles).length === 0) return

    // Find the matching legal move
    const placedLetters = Object.entries(pendingTiles).map(([key, t]) => {
      const [r, c] = key.split(',').map(Number)
      return { letter: t.letter, row: r, col: c }
    })

    // Check: all tiles must be in same row or same column
    const rows = new Set(placedLetters.map(t => t.row))
    const cols = new Set(placedLetters.map(t => t.col))
    if (rows.size > 1 && cols.size > 1) {
      setError('Tiles must be in a straight line')
      return
    }

    // Build the word — try both directions for single tile, pick one that connects
    const tryDirection = (horiz) => {
      const dir = horiz ? 'H' : 'V'
      const fixedAxis = horiz ? [...rows][0] : [...cols][0]
      const positions = horiz
        ? placedLetters.map(t => t.col).sort((a, b) => a - b)
        : placedLetters.map(t => t.row).sort((a, b) => a - b)

      let minPos = positions[0]
      let maxPos = positions[positions.length - 1]

      // Extend backward through adjacent existing tiles
      while (minPos > 0) {
        const key = horiz ? `${fixedAxis},${minPos - 1}` : `${minPos - 1},${fixedAxis}`
        if (boardTiles[key]) minPos--
        else break
      }
      // Extend forward
      while (maxPos < 8) {
        const key = horiz ? `${fixedAxis},${maxPos + 1}` : `${maxPos + 1},${fixedAxis}`
        if (boardTiles[key]) maxPos++
        else break
      }

      // Build word
      let word = ''
      for (let pos = minPos; pos <= maxPos; pos++) {
        const key = horiz ? `${fixedAxis},${pos}` : `${pos},${fixedAxis}`
        if (pendingTiles[key]) word += pendingTiles[key].letter
        else if (boardTiles[key]) word += boardTiles[key].name
        else return null // gap
      }
      return { word, dir }
    }

    let result = null
    if (rows.size === 1 && cols.size === 1) {
      // Single tile: try both directions, pick the longer word
      const h = tryDirection(true)
      const v = tryDirection(false)
      if (h && v) result = (h.word.length >= v.word.length) ? h : v
      else result = h || v
    } else {
      result = tryDirection(rows.size === 1)
    }

    if (!result) {
      setError('Gap in word — tiles must be connected')
      return
    }
    const { word, dir } = result
    // Re-derive min position for matching
    const isHorizontal = dir === 'H'
    const fixedAxis = isHorizontal ? [...rows][0] : [...cols][0]

    if (word.length < 2) {
      setError('Word must be at least 2 letters')
      return
    }

    // Find matching move from legal moves
    const match = wordMoves.find(m =>
      m.params._word === word &&
      m.params._dir === dir
    )

    if (match) {
      onMove(match.rule, match.params)
      setPendingTiles({})
      setSelectedRackIdx(null)
      setError('')
    } else {
      // Try to find by word only (direction might not match)
      const wordMatch = wordMoves.find(m => m.params._word === word)
      if (wordMatch) {
        onMove(wordMatch.rule, wordMatch.params)
        setPendingTiles({})
        setSelectedRackIdx(null)
        setError('')
      } else {
        setError(`"${word}" is not a valid play here`)
      }
    }
  }

  const handlePass = () => {
    const move = (state.legal_moves || []).find(m => m.rule === 'pass_turn')
    if (move) {
      onMove(move.rule, move.params)
      setPendingTiles({})
      setSelectedRackIdx(null)
    }
  }

  // Also let user pick from suggestions as fallback
  const handleSuggestion = (wordId) => {
    const move = wordMoves.find(m => m.params.word_id === wordId)
    if (move) {
      onMove(move.rule, move.params)
      setPendingTiles({})
      setSelectedRackIdx(null)
      setError('')
    }
  }

  const CW = 52
  const hasPending = Object.keys(pendingTiles).length > 0

  return (
    <div style={{ textAlign: 'center', width: '100%' }}>
      {/* Scores */}
      <div className="crazy8-info" style={{ gap: '1.5rem' }}>
        <span>You: {p1Score} pts</span>
        <span>AI: {p2Score} pts</span>
        <span>Bag: {bagSize}</span>
        <span>AI rack: {oppRackSize}</span>
      </div>

      {lastPlay && <div className="crazy8-last-action">{lastPlay}</div>}

      {/* Board */}
      <div style={{ display: 'inline-block', margin: '0.5rem auto' }}>
        {Array.from({ length: 9 }, (_, r) => (
          <div key={r} style={{ display: 'flex' }}>
            {Array.from({ length: 9 }, (_, c) => {
              const key = `${r},${c}`
              const piece = boardTiles[key]
              const pending = pendingTiles[key]
              const bonus = BONUS_SQUARES[key]
              const bonusStyle = bonus ? BONUS_COLORS[bonus] : null
              const isCenter = r === 4 && c === 4
              const canClick = isMyTurn && !piece && !disabled

              return (
                <div key={c} onClick={() => canClick && handleCellClick(r, c)} style={{
                  width: `${CW}px`, height: `${CW}px`,
                  cursor: canClick && selectedRackIdx !== null ? 'pointer' : 'default',
                  background: pending ? '#b8943e' : piece ? 'var(--accent)' :
                    bonusStyle ? bonusStyle.bg : 'var(--bg-raised)',
                  border: `1.5px solid ${pending ? '#e8c44e' : piece ? '#8a6d36' :
                    bonusStyle ? bonusStyle.border : 'var(--rule-bright)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  position: 'relative', borderRadius: '3px', margin: '1px',
                  flexDirection: 'column',
                  opacity: canClick && selectedRackIdx !== null && !piece && !pending ? 0.9 : 1,
                }}>
                  {(piece || pending) ? (
                    <>
                      <span style={{
                        fontFamily: 'Menlo, monospace', fontSize: '1.3rem',
                        fontWeight: 'bold', color: pending ? '#fff' : '#1a1a1a',
                      }}>
                        {pending ? pending.letter : piece.name}
                      </span>
                      <span style={{
                        fontSize: '0.65rem', color: pending ? '#ddd' : '#4a3a1a',
                        position: 'absolute', bottom: '2px', right: '3px',
                        fontFamily: 'Menlo, monospace',
                      }}>
                        {LETTER_VALUES[pending ? pending.letter : piece.name] || 0}
                      </span>
                    </>
                  ) : bonusStyle ? (
                    <span style={{
                      fontFamily: 'Menlo, monospace', fontSize: '0.65rem',
                      fontWeight: 'bold', color: bonusStyle.border, opacity: 0.9,
                    }}>
                      {bonusStyle.label}
                    </span>
                  ) : isCenter ? (
                    <span style={{ fontSize: '0.8rem', color: 'var(--ink-faint)' }}>★</span>
                  ) : null}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Rack */}
      {isMyTurn && (
        <div style={{ margin: '0.75rem 0' }}>
          <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.7rem', color: 'var(--ink-faint)', marginBottom: '0.3rem' }}>
            {selectedRackIdx !== null ? 'Click a cell on the board to place tile' : 'Click a tile, then click the board'}
          </div>
          <div style={{ display: 'flex', gap: '4px', justifyContent: 'center' }}>
            {myRack.map((tile, i) => {
              const isUsed = usedRackIndices.has(i)
              const isSelected = selectedRackIdx === i
              return (
                <div key={i} onClick={() => handleRackClick(i)} style={{
                  width: '48px', height: '48px',
                  background: isUsed ? 'var(--bg-deep)' : isSelected ? '#e8c44e' : 'var(--accent)',
                  borderRadius: '4px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  position: 'relative',
                  border: isSelected ? '3px solid #fff' : '2px solid #8a6d36',
                  cursor: isUsed ? 'default' : 'pointer',
                  opacity: isUsed ? 0.3 : 1,
                }}>
                  <span style={{
                    fontFamily: 'Menlo, monospace', fontSize: '1.4rem',
                    fontWeight: 'bold', color: '#1a1a1a',
                  }}>
                    {tile.letter}
                  </span>
                  <span style={{
                    fontSize: '0.6rem', color: '#4a3a1a',
                    position: 'absolute', bottom: '2px', right: '3px',
                    fontFamily: 'Menlo, monospace',
                  }}>
                    {tile.value}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Action buttons */}
      {isMyTurn && (
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', margin: '0.5rem 0', flexWrap: 'wrap' }}>
          {hasPending && (
            <button className="crazy8-draw-btn" onClick={handleSubmit}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1.2rem' }}>
              Play Word
            </button>
          )}
          {hasPending && (
            <button className="crazy8-draw-btn" onClick={handleClear}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1.2rem' }}>
              Clear
            </button>
          )}
          {canPass && !hasPending && (
            <button className="crazy8-draw-btn" onClick={handlePass}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1.2rem' }}>
              Pass
            </button>
          )}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div style={{
          fontFamily: 'Menlo, monospace', fontSize: '0.8rem',
          color: '#c83030', margin: '0.3rem 0',
        }}>
          {error}
        </div>
      )}

      {/* Suggestions as fallback */}
      {isMyTurn && !hasPending && wordMoves.length > 0 && (
        <div style={{ margin: '0.5rem 0' }}>
          <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.65rem', color: 'var(--ink-faint)', marginBottom: '0.2rem' }}>
            or pick a suggestion
          </div>
          <div style={{ display: 'flex', gap: '4px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {wordMoves.slice(0, 5).map((m, i) => (
              <button key={i} className="crazy8-draw-btn"
                onClick={() => handleSuggestion(m.params.word_id)}
                disabled={disabled}
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
              >
                {m.params._word || '?'} ({m.params._score || '?'})
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ScrabbleBoard
