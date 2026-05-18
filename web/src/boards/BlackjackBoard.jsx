import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }

function BlackjackBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const dealerHand = zones.hand_p2?.cards || []
  const holeSize = zones.hole_card?.size || 0
  const lastAction = vars.last_action || ''
  const phase = vars.phase || 'player'
  const p1Bust = vars.p1_bust
  const p2Bust = vars.p2_bust

  const handValue = (cards) => {
    let val = 0, aces = 0
    for (const c of cards) {
      if (['J','Q','K'].includes(c.rank)) val += 10
      else if (c.rank === 'A') { val += 11; aces++ }
      else val += parseInt(c.rank)
    }
    while (val > 21 && aces > 0) { val -= 10; aces-- }
    return val
  }

  const handleHit = () => {
    const move = state.legal_moves?.find(m => m.rule === 'hit')
    if (move) onMove(move.rule, move.params)
  }

  const handleStand = () => {
    const move = state.legal_moves?.find(m => m.rule === 'stand')
    if (move) onMove(move.rule, move.params)
  }

  const renderCard = (card) => (
    <div key={card.id} className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}
         style={{ cursor: 'default' }}>
      <span className="gofish-card-rank">{card.rank}</span>
      <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
    </div>
  )

  return (
    <div className="blackjack-board">
      <div className="blackjack-dealer">
        <div className="blackjack-label">Dealer {phase === 'done' ? `(${handValue(dealerHand)})` : ''} {p2Bust === 'True' || p2Bust === true ? 'BUST!' : ''}</div>
        <div className="gofish-cards">
          {dealerHand.map(renderCard)}
          {holeSize > 0 && <div className="gofish-card-back" style={{ width: 52, height: 74 }} />}
        </div>
      </div>

      {lastAction && <div className="blackjack-action">{lastAction}</div>}

      <div className="blackjack-player">
        <div className="blackjack-label">Your hand ({handValue(myHand)}) {p1Bust === 'True' || p1Bust === true ? 'BUST!' : ''}</div>
        <div className="gofish-cards">
          {myHand.map(renderCard)}
        </div>
      </div>

      {phase === 'player' && !disabled && (
        <div className="blackjack-buttons">
          <button className="action-btn action-btn-primary" onClick={handleHit}>Hit</button>
          <button className="action-btn" onClick={handleStand}>Stand</button>
        </div>
      )}
    </div>
  )
}

export default BlackjackBoard
