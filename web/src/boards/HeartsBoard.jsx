import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }
const SUIT_ORDER = ['clubs', 'diamonds', 'spades', 'hearts']
const RANK_ORDER = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']

function HeartsBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const trickCards = zones.trick?.cards || []
  const p1Points = vars.p1_points || 0
  const p2Points = vars.p2_points || 0
  const tricksPlayed = vars.tricks_played || 0
  const lastPlay = vars.last_play || ''
  const lastAction = vars.last_action || ''
  const isMyTurn = state.current_player === 'player1'

  const playableIds = new Set()
  for (const m of (state.legal_moves || [])) {
    if (m.params.card_id != null) playableIds.add(m.params.card_id)
  }

  const handlePlay = (cardId) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.params.card_id === cardId)
    if (move) onMove(move.rule, move.params)
  }

  const sortedHand = [...myHand].sort((a, b) => {
    const si = SUIT_ORDER.indexOf(a.suit) - SUIT_ORDER.indexOf(b.suit)
    return si !== 0 ? si : RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank)
  })

  return (
    <div className="crazy8-board">
      <div className="crazy8-info">
        <span>Your points: {p1Points}</span>
        <span>AI points: {p2Points}</span>
        <span>Tricks: {tricksPlayed}/13</span>
        <span>AI hand: {oppHandSize}</span>
      </div>

      {trickCards.length > 0 && (
        <div className="crazy8-table">
          {trickCards.map((card, i) => (
            <div key={card.id} className={`crazy8-top-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}>
              <span className="crazy8-card-rank">{card.rank}</span>
              <span className="crazy8-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
            </div>
          ))}
        </div>
      )}

      <div className="crazy8-last-action">
        {lastAction === 'trick_won' && lastPlay}
        {lastAction === 'play' && !isMyTurn && `AI played ${lastPlay}`}
        {isMyTurn && lastAction !== 'trick_won' && trickCards.length === 0 && 'Lead a card'}
        {isMyTurn && trickCards.length === 1 && 'Play a card (must follow suit if possible)'}
      </div>

      <div className="crazy8-my-hand">
        <div className="crazy8-hand-label">Your hand ({myHand.length} cards)</div>
        <div className="gofish-cards">
          {sortedHand.map((card) => {
            const playable = playableIds.has(card.id)
            const isDangerous = card.suit === 'hearts' || (card.suit === 'spades' && card.rank === 'Q')
            return (
              <button
                key={card.id}
                className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'} ${!playable ? 'disabled' : ''}`}
                style={isDangerous ? { borderColor: '#c83030' } : {}}
                onClick={() => playable && handlePlay(card.id)}
                disabled={disabled || !isMyTurn || !playable}
              >
                <span className="gofish-card-rank">{card.rank}</span>
                <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default HeartsBoard
