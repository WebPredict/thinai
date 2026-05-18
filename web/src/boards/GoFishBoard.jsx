import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }

function GoFishBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const pondSize = zones.pond?.size || 0
  const mySets = (zones.sets_p1?.size || 0) / 4
  const oppSets = (zones.sets_p2?.size || 0) / 4
  const mySetCards = zones.sets_p1?.cards || []
  const oppSetCards = zones.sets_p2?.cards || []
  // Group set cards by rank to show completed sets
  const groupByRank = (cards) => {
    const groups = {}
    cards.forEach(c => { groups[c.rank] = (groups[c.rank] || 0) + 1 })
    return Object.keys(groups)
  }
  const mySetRanks = groupByRank(mySetCards)
  const oppSetRanks = groupByRank(oppSetCards)
  const lastResult = vars.last_result || ''
  const lastAskRank = vars.last_ask_rank || ''
  const lastAskPlayer = vars.last_ask_player || ''
  const isMyTurn = state.current_player === 'player1'

  // Group hand by rank for display
  const rankCounts = {}
  myHand.forEach(c => {
    rankCounts[c.rank] = (rankCounts[c.rank] || 0) + 1
  })

  const handleAsk = (rank) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.params.rank === rank)
    if (move) onMove(move.rule, move.params)
  }

  return (
    <div className="gofish-board">
      <div className="gofish-info-bar">
        <div className="gofish-score">
          <span className="gofish-score-you">
            Your sets: <strong>{Math.floor(mySets)}</strong>
            {mySetRanks.length > 0 && <span className="gofish-set-ranks"> ({mySetRanks.join(', ')})</span>}
          </span>
          <span className="gofish-score-ai">
            AI sets: <strong>{Math.floor(oppSets)}</strong>
            {oppSetRanks.length > 0 && <span className="gofish-set-ranks"> ({oppSetRanks.join(', ')})</span>}
          </span>
        </div>
        <div className="gofish-pond">Pond: {pondSize} cards</div>
      </div>

      <div className="gofish-opponent">
        <div className="gofish-opp-label">AI's hand</div>
        <div className="gofish-card-backs">
          {Array.from({ length: Math.min(oppHandSize, 10) }).map((_, i) => (
            <div key={i} className="gofish-card-back" />
          ))}
          {oppHandSize > 10 && <span className="gofish-more">+{oppHandSize - 10}</span>}
        </div>
      </div>

      {lastResult && (
        <div className={`gofish-result ${lastResult.includes('Go Fish') ? 'gofish-miss' : 'gofish-hit'}`}>
          {lastAskPlayer === 'player1' ? 'You' : 'AI'} asked for {lastAskRank}s — {lastResult}
        </div>
      )}

      <div className="gofish-my-hand">
        <div className="gofish-hand-label">Your hand — tap a rank to ask for it</div>
        <div className="gofish-cards">
          {myHand.map((card, i) => (
            <button
              key={card.id}
              className={`gofish-card ${disabled || !isMyTurn ? 'disabled' : ''} ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}
              onClick={() => handleAsk(card.rank)}
              disabled={disabled || !isMyTurn}
            >
              <span className="gofish-card-rank">{card.rank}</span>
              <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default GoFishBoard
