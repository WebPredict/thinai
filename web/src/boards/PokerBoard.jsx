import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }

function PokerBoard({ state, onMove, disabled }) {
  const [selectedCards, setSelectedCards] = useState(new Set())

  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const phase = vars.phase || 'discard_p1'
  const lastAction = vars.last_action || ''
  const roundOver = vars.round_over
  const isMyTurn = state.current_player === 'player1'
  const isMyDiscard = phase === 'discard_p1'
  const showdown = roundOver || phase === 'showdown'

  // Revealed hands at showdown
  const revealP1 = zones.reveal_p1?.cards || []
  const revealP2 = zones.reveal_p2?.cards || []

  const canDiscard = state.legal_moves?.some(m => m.rule === 'discard_card')
  const canStand = state.legal_moves?.some(m => m.rule === 'stand_pat')

  const handleDiscard = (cardId) => {
    if (disabled || !isMyDiscard) return
    const move = state.legal_moves?.find(m => m.rule === 'discard_card' && m.params.card_id === cardId)
    if (move) {
      onMove(move.rule, move.params)
      setSelectedCards(prev => { const n = new Set(prev); n.delete(cardId); return n })
    }
  }

  const handleStandPat = () => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.rule === 'stand_pat')
    if (move) {
      onMove(move.rule, move.params)
      setSelectedCards(new Set())
    }
  }

  const toggleSelect = (cardId) => {
    if (!isMyDiscard || disabled) return
    setSelectedCards(prev => {
      const n = new Set(prev)
      if (n.has(cardId)) n.delete(cardId)
      else if (n.size < 3) n.add(cardId)
      return n
    })
  }

  const renderCard = (card, clickable, selected) => (
    <button
      key={card.id}
      className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'} ${selected ? '' : ''}`}
      style={selected ? { transform: 'translateY(-8px)', boxShadow: '0 6px 16px rgba(212, 166, 86, 0.5)', borderColor: 'var(--accent)' } : {}}
      onClick={() => clickable && toggleSelect(card.id)}
      disabled={!clickable}
    >
      <span className="gofish-card-rank">{card.rank}</span>
      <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
    </button>
  )

  const handRankP1 = vars.p1_hand_rank || ''
  const handRankP2 = vars.p2_hand_rank || ''

  return (
    <div className="crazy8-board">
      <div className="crazy8-info">
        <span>AI hand: {oppHandSize} cards</span>
      </div>

      {showdown && revealP2.length > 0 && (
        <div style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
          <div className="crazy8-hand-label">AI's hand {handRankP2 && `— ${handRankP2}`}</div>
          <div className="gofish-cards">
            {revealP2.map(c => renderCard(c, false, false))}
          </div>
        </div>
      )}

      <div className="crazy8-last-action">
        {isMyDiscard && !roundOver && `Select up to 3 cards to discard (${selectedCards.size} selected)`}
        {phase === 'discard_p2' && !roundOver && 'AI is choosing cards to discard...'}
        {showdown && 'Showdown!'}
      </div>

      <div className="crazy8-my-hand">
        <div className="crazy8-hand-label">Your hand {showdown && handRankP1 && `— ${handRankP1}`}</div>
        <div className="gofish-cards">
          {(showdown && revealP1.length > 0 ? revealP1 : myHand).map(card =>
            renderCard(card, isMyDiscard && !roundOver, selectedCards.has(card.id))
          )}
        </div>
        {isMyDiscard && !roundOver && (
          <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
            {selectedCards.size > 0 && [...selectedCards].map(cid => {
              const move = state.legal_moves?.find(m => m.rule === 'discard_card' && m.params.card_id === cid)
              return move ? (
                <button key={cid} className="crazy8-draw-btn" style={{ fontSize: '0.8rem' }}
                  onClick={() => handleDiscard(cid)}>
                  Discard selected
                </button>
              ) : null
            }).filter(Boolean).slice(0, 1)}
            <button className="crazy8-draw-btn" onClick={handleStandPat}>
              {selectedCards.size === 0 ? 'Keep all cards' : 'Done discarding'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default PokerBoard
