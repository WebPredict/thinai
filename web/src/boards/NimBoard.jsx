import { useState } from 'react'

function NimBoard({ state, onMove, disabled }) {
  const [selectedPile, setSelectedPile] = useState(null)

  if (!state) return null

  const { spaces, legal_moves } = state

  const getCount = (idx) => {
    const val = spaces[String(idx)]
    if (!val) return 0
    if (Array.isArray(val)) return val.length
    return 1
  }

  const piles = [0, 1, 2]
  const pileCounts = piles.map(getCount)

  const getAmounts = (pileIdx) => {
    return legal_moves
      .filter(m => m.params.pile?.index === pileIdx)
      .map(m => m.params.amount)
      .sort((a, b) => a - b)
  }

  const handleTake = (pileIdx, amount) => {
    if (disabled) return
    const move = legal_moves.find(
      m => m.params.pile?.index === pileIdx && m.params.amount === amount
    )
    if (move) {
      onMove(move.rule, move.params)
      setSelectedPile(null)
    }
  }

  return (
    <div className="nim-board">
      <div className="nim-piles">
        {piles.map(idx => {
          const count = pileCounts[idx]
          const amounts = getAmounts(idx)
          const isSelected = selectedPile === idx
          const hasStones = count > 0

          return (
            <div key={idx} className="nim-pile-col">
              <div className="nim-pile-label">Pile {idx + 1}</div>
              <div
                className={[
                  'nim-pile',
                  isSelected ? 'selected' : '',
                  hasStones && !disabled ? 'clickable' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => hasStones && !disabled && setSelectedPile(isSelected ? null : idx)}
              >
                {Array.from({ length: count }).map((_, i) => (
                  <div key={i} className="nim-stone" />
                ))}
                {count === 0 && <div className="nim-empty">empty</div>}
              </div>
              {isSelected && amounts.length > 0 && (
                <div className="nim-take-buttons">
                  {amounts.map(amt => (
                    <button
                      key={amt}
                      className="nim-take-btn"
                      onClick={() => handleTake(idx, amt)}
                    >
                      Take {amt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <div className="nim-hint">Click a pile, then choose how many to take</div>
    </div>
  )
}

export default NimBoard
