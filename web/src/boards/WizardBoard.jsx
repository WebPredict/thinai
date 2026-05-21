import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }
const SUIT_ORDER = ['clubs', 'diamonds', 'spades', 'hearts']
const RANK_ORDER = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
const SUIT_COLORS = { hearts: '#c83030', diamonds: '#c83030', clubs: '#e8dfd1', spades: '#e8dfd1' }

function WizardBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const trickCards = zones.trick?.cards || []
  const trumpCards = zones.trump_card?.cards || []
  const trumpSuit = vars.trump_suit || ''
  const phase = vars.phase || 'bid_p1'
  const p1Bid = vars.p1_bid ?? -1
  const p2Bid = vars.p2_bid ?? -1
  const p1Tricks = vars.p1_tricks_won || 0
  const p2Tricks = vars.p2_tricks_won || 0
  const p1Score = vars.p1_score || 0
  const p2Score = vars.p2_score || 0
  const roundNumber = vars.round_number || 1
  const tricksPlayed = vars.tricks_played || 0
  const lastPlay = vars.last_play || ''
  const lastAction = vars.last_action || ''
  const isMyTurn = state.current_player === 'player1'
  const isBidding = phase.startsWith('bid')

  const playableIds = new Set()
  const bidOptions = []
  for (const m of (state.legal_moves || [])) {
    if (m.params.card_id != null) playableIds.add(m.params.card_id)
    if (m.params.bid_value != null) bidOptions.push(m.params.bid_value)
  }

  const handlePlay = (cardId) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.params.card_id === cardId)
    if (move) onMove(move.rule, move.params)
  }

  const handleBid = (bidValue) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.params.bid_value === bidValue)
    if (move) onMove(move.rule, move.params)
  }

  const sortedHand = [...myHand].sort((a, b) => {
    // Sort trump suit first, then by suit, then by rank
    const aIsTrump = a.suit === trumpSuit ? -1 : 0
    const bIsTrump = b.suit === trumpSuit ? -1 : 0
    if (aIsTrump !== bIsTrump) return aIsTrump - bIsTrump
    const si = SUIT_ORDER.indexOf(a.suit) - SUIT_ORDER.indexOf(b.suit)
    return si !== 0 ? si : RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank)
  })

  return (
    <div className="crazy8-board">
      {/* Score and round info */}
      <div className="crazy8-info" style={{ gap: '1.5rem' }}>
        <span>Round {roundNumber}/5</span>
        <span>You: {p1Score} pts</span>
        <span>AI: {p2Score} pts</span>
      </div>

      {/* Bid and tricks info */}
      {(p1Bid >= 0 || p2Bid >= 0) && (
        <div style={{
          display: 'flex', justifyContent: 'center', gap: '2rem',
          fontFamily: 'Menlo, monospace', fontSize: '0.9rem',
          margin: '0.3rem 0', padding: '0.5rem 1rem',
          background: 'rgba(212,166,86,0.08)', border: '1px solid rgba(212,166,86,0.2)',
          borderRadius: '6px', maxWidth: '500px', marginLeft: 'auto', marginRight: 'auto',
        }}>
          {p1Bid >= 0 && (
            <span>
              <span style={{ color: 'var(--accent)' }}>You</span>
              {' '}bid {p1Bid}, won {p1Tricks}
            </span>
          )}
          {p2Bid >= 0 && (
            <span>
              <span style={{ color: 'var(--ink-faint)' }}>AI</span>
              {' '}bid {p2Bid}, won {p2Tricks}
            </span>
          )}
          {!isBidding && <span>Trick {tricksPlayed}/5</span>}
        </div>
      )}

      {/* Trump card display */}
      {trumpCards.length > 0 && (
        <div style={{ textAlign: 'center', margin: '0.5rem 0' }}>
          <span style={{ fontFamily: 'Menlo, monospace', fontSize: '0.75rem', color: 'var(--ink-faint)' }}>
            Trump:
          </span>
          <span style={{
            display: 'inline-block', padding: '0.3rem 0.6rem', margin: '0 0.4rem',
            background: 'var(--bg-raised)', border: '2px solid var(--accent)',
            borderRadius: '6px', fontFamily: 'Menlo, monospace', fontSize: '1.1rem',
            color: SUIT_COLORS[trumpSuit] || 'var(--ink)',
          }}>
            {trumpCards[0].rank}{SUIT_SYMBOLS[trumpSuit]}
          </span>
        </div>
      )}

      {/* Trick area */}
      {trickCards.length > 0 && (
        <div className="crazy8-table">
          {trickCards.map((card) => (
            <div key={card.id} className={`crazy8-top-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}
              style={card.suit === trumpSuit ? { borderColor: 'var(--accent)', borderWidth: '2px' } : {}}>
              <span className="crazy8-card-rank">{card.rank}</span>
              <span className="crazy8-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
            </div>
          ))}
        </div>
      )}

      {/* Status message */}
      <div className="crazy8-last-action">
        {isBidding ? (
          isMyTurn ? `${lastPlay ? lastPlay + '. ' : ''}How many tricks will you win?` : lastPlay
        ) : lastAction === 'trick_won' ? (
          lastPlay
        ) : lastAction === 'game_over' ? (
          lastPlay
        ) : lastAction === 'play' && !isMyTurn ? (
          `AI played ${lastPlay}`
        ) : isMyTurn && trickCards.length === 0 ? (
          'Lead a card'
        ) : isMyTurn && trickCards.length === 1 ? (
          'Play a card (must follow suit if possible)'
        ) : lastPlay}
      </div>

      {/* Bidding UI */}
      {isBidding && isMyTurn && bidOptions.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', margin: '0.75rem 0', flexWrap: 'wrap' }}>
          {bidOptions.sort((a, b) => a - b).map(bid => (
            <button key={bid} className="crazy8-draw-btn"
              onClick={() => handleBid(bid)}
              style={{ fontSize: '1rem', padding: '0.5rem 1.2rem', minWidth: '3rem' }}
            >
              {bid}
            </button>
          ))}
        </div>
      )}

      {/* Card hand */}
      {!isBidding && (
        <div className="crazy8-my-hand">
          <div className="crazy8-hand-label">Your hand ({myHand.length} cards)</div>
          <div className="gofish-cards">
            {sortedHand.map((card) => {
              const playable = playableIds.has(card.id)
              const isTrump = card.suit === trumpSuit
              return (
                <button
                  key={card.id}
                  className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'} ${!playable ? 'disabled' : ''}`}
                  style={isTrump ? { borderColor: 'var(--accent)', borderWidth: '2px' } : {}}
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
      )}

      {/* Show hand during bidding phase too */}
      {isBidding && (
        <div className="crazy8-my-hand">
          <div className="crazy8-hand-label">Your hand ({myHand.length} cards)</div>
          <div className="gofish-cards">
            {sortedHand.map((card) => {
              const isTrump = card.suit === trumpSuit
              return (
                <button
                  key={card.id}
                  className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'} disabled`}
                  style={isTrump ? { borderColor: 'var(--accent)', borderWidth: '2px' } : {}}
                  disabled
                >
                  <span className="gofish-card-rank">{card.rank}</span>
                  <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default WizardBoard
