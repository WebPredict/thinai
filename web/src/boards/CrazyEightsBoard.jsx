import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }

function CrazyEightsBoard({ state, onMove, disabled }) {
  const [pendingWild, setPendingWild] = useState(null) // card awaiting color choice

  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const deckSize = zones.deck?.size || 0
  const discardCards = zones.discard?.cards || []
  const topCard = discardCards.length > 0 ? discardCards[discardCards.length - 1] : null
  const activeSuit = vars.active_suit || ''
  const lastAction = vars.last_action || ''
  const lastPlay = vars.last_play || ''
  const isMyTurn = state.current_player === 'player1'

  // Abbreviate long Uno action card names to fit card bounds
  const unoLabel = (rank) => {
    const labels = { 'Reverse': 'REV', 'Skip': 'SKIP', 'Draw2': '+2', 'WildDraw4': '+4', 'Wild': 'W' }
    return labels[rank] || rank
  }
  const isUnoGame = ['red','blue','green','yellow','wild'].includes(myHand[0]?.suit)

  // Find playable card IDs from legal moves
  const playableIds = new Set()
  const canDraw = state.legal_moves?.some(m => m.rule === 'draw_card')
  for (const m of (state.legal_moves || [])) {
    if (m.params.card_id != null) playableIds.add(m.params.card_id)
  }

  const handlePlay = (cardId) => {
    if (disabled) return
    // For Uno: if the card is a Wild, show color picker first
    if (isUnoGame) {
      const card = myHand.find(c => c.id === cardId)
      if (card && (card.suit === 'wild')) {
        setPendingWild(cardId)
        return
      }
    }
    const move = state.legal_moves?.find(m => m.params.card_id === cardId)
    if (move) onMove(move.rule, move.params)
  }

  const handleWildColorChoice = (color) => {
    if (!pendingWild) return
    const move = state.legal_moves?.find(m => m.params.card_id === pendingWild)
    if (move) {
      // Play the card — the engine auto-picks color, but we'll override via state
      onMove(move.rule, { ...move.params, wild_color: color })
    }
    setPendingWild(null)
  }

  const handleDraw = () => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.rule === 'draw_card')
    if (move) onMove(move.rule, move.params)
  }

  return (
    <div className="crazy8-board">
      <div className="crazy8-info">
        <span>Deck: {deckSize} cards remaining</span>
        <span>AI hand: {oppHandSize} cards</span>
      </div>

      {/* Score display for compare/score games */}
      {(vars.p1_score != null || vars.p2_score != null) && (
        <div className="crazy8-info" style={{ justifyContent: 'center', gap: '2rem', fontSize: '1rem' }}>
          <span>You: {vars.p1_score || 0} pts</span>
          <span>AI: {vars.p2_score || 0} pts</span>
        </div>
      )}

      {/* Trick zone — show cards played this round */}
      {zones.trick?.cards?.length > 0 && (
        <div className="crazy8-table">
          {zones.trick.cards.map(card => (
            <div key={card.id} className={`crazy8-top-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}>
              <span className="crazy8-card-rank">{card.rank}</span>
              <span className="crazy8-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
            </div>
          ))}
        </div>
      )}

      <div className="crazy8-table">
        {deckSize > 0 && (
          <div className="crazy8-deck-pile">
          </div>
        )}
        {topCard && (
          <div className={`crazy8-top-card ${
            ['red','blue','green','yellow','wild'].includes(topCard.suit)
              ? `uno-${topCard.suit}`
              : topCard.suit === 'hearts' || topCard.suit === 'diamonds' ? 'red' : 'black'
          }`}>
            <span className="crazy8-card-rank">{isUnoGame ? unoLabel(topCard.rank) : topCard.rank}</span>
            <span className="crazy8-card-suit">{SUIT_SYMBOLS[topCard.suit]}</span>
          </div>
        )}
        {activeSuit && (
          <div className="crazy8-active-suit">Active suit: {SUIT_SYMBOLS[activeSuit] || activeSuit}</div>
        )}
      </div>

      {lastPlay && (
        <div className="crazy8-last-action">
          {lastAction === 'draw' ? 'Drew a card' : lastAction === 'round_complete' ? lastPlay : `Played ${lastPlay}`}
        </div>
      )}

      <div className="crazy8-my-hand">
        <div className="crazy8-hand-label">Your hand — play a matching card</div>
        <div className="gofish-cards">
          {myHand.map((card) => {
            const playable = playableIds.has(card.id)
            return (
              <button
                key={card.id}
                className={`gofish-card ${
                  ['red','blue','green','yellow','wild'].includes(card.suit)
                    ? `uno-${card.suit}`
                    : card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'
                } ${!playable ? 'disabled' : ''} ${card.rank === '8' || card.suit === 'wild' ? 'wild' : ''}`}
                onClick={() => playable && handlePlay(card.id)}
                disabled={disabled || !isMyTurn || !playable}
              >
                <span className="gofish-card-rank">{isUnoGame ? unoLabel(card.rank) : card.rank}</span>
                <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
              </button>
            )
          })}
        </div>
        {canDraw && isMyTurn && !disabled && (
          <button className="crazy8-draw-btn" onClick={handleDraw}>
            Draw from deck
          </button>
        )}

        {/* Uno wild card color picker */}
        {pendingWild && (
          <div style={{
            margin: '0.75rem 0', padding: '0.75rem', textAlign: 'center',
            background: 'rgba(212,166,86,0.1)', border: '1px solid rgba(212,166,86,0.3)',
            borderRadius: '8px',
          }}>
            <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.9rem', color: 'var(--ink)', marginBottom: '0.5rem' }}>
              Choose a color:
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
              {[
                { name: 'red', color: '#d42020', bg: '#fff0f0' },
                { name: 'blue', color: '#1050cc', bg: '#f0f4ff' },
                { name: 'green', color: '#18883a', bg: '#f0fff4' },
                { name: 'yellow', color: '#cc8800', bg: '#fffcf0' },
              ].map(c => (
                <button key={c.name} onClick={() => handleWildColorChoice(c.name)}
                  style={{
                    width: '50px', height: '50px', borderRadius: '8px',
                    background: c.bg, border: `3px solid ${c.color}`,
                    cursor: 'pointer', fontSize: '0.7rem', fontWeight: 'bold',
                    color: c.color, fontFamily: 'Menlo, monospace',
                  }}>
                  {c.name}
                </button>
              ))}
            </div>
            <button onClick={() => setPendingWild(null)}
              style={{ marginTop: '0.4rem', background: 'none', border: 'none', color: 'var(--ink-faint)', cursor: 'pointer', fontSize: '0.8rem' }}>
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default CrazyEightsBoard
