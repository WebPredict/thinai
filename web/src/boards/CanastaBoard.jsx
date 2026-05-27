import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '♥', diamonds: '♦', clubs: '♣', spades: '♠', joker: '★' }
const SUIT_ORDER = ['clubs', 'diamonds', 'spades', 'hearts', 'joker']
const RANK_ORDER = ['2','3','4','5','6','7','8','9','10','J','Q','K','A','Joker']

function CanastaBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const discardCards = zones.discard?.cards || []
  const topDiscard = discardCards.length > 0 ? discardCards[discardCards.length - 1] : null
  const deckSize = zones.deck?.size || 0
  const phase = vars.phase || 'draw'
  const myMelds = vars.melds_p1 || []
  const oppMelds = vars.melds_p2 || []
  const lastPlay = vars.last_play || ''
  const isMyTurn = state.current_player === 'player1'

  const legalMoves = state.legal_moves || []

  const handleMove = (rule, params) => {
    if (disabled) return
    onMove(rule, params)
  }

  const sortedHand = [...myHand].sort((a, b) => {
    const ri = RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank)
    return ri !== 0 ? ri : SUIT_ORDER.indexOf(a.suit) - SUIT_ORDER.indexOf(b.suit)
  })

  const drawMoves = legalMoves.filter(m => m.rule === 'draw_deck' || m.rule === 'draw_pile')
  const meldMoves = legalMoves.filter(m => m.rule === 'lay_meld')
  const addMoves = legalMoves.filter(m => m.rule === 'add_to_meld')
  const skipMeld = legalMoves.find(m => m.rule === 'done_melding')
  const discardMoves = legalMoves.filter(m => m.rule === 'discard')

  const renderMeld = (meld, idx, label) => (
    <div key={idx} style={{
      display: 'inline-flex', gap: '2px', padding: '0.3rem',
      background: 'rgba(92,186,110,0.1)', border: '1px solid rgba(92,186,110,0.3)',
      borderRadius: '6px', margin: '0.2rem',
    }}>
      {meld.map((card, ci) => (
        <span key={ci} style={{
          fontFamily: 'Menlo, monospace', fontSize: '0.8rem',
          color: ['hearts', 'diamonds'].includes(card.suit) ? '#c83030' : 'var(--ink)',
          padding: '0.1rem 0.3rem', background: 'var(--bg-raised)',
          borderRadius: '3px', border: '1px solid var(--rule-dim)',
        }}>
          {card.rank}{SUIT_SYMBOLS[card.suit] || ''}
        </span>
      ))}
      {meld.length >= 7 && <span style={{ fontSize: '0.7rem', color: '#5cba6e' }}>★</span>}
    </div>
  )

  return (
    <div className="crazy8-board">
      {/* Opponent info */}
      <div className="crazy8-info">
        <span>AI hand: {oppHandSize}</span>
        <span>Deck: {deckSize}</span>
        <span>Discard: {discardCards.length}</span>
      </div>

      {/* Opponent melds */}
      {oppMelds.length > 0 && (
        <div style={{ textAlign: 'center', margin: '0.3rem 0' }}>
          <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.7rem', color: 'var(--ink-dim)' }}>AI melds</div>
          {oppMelds.map((m, i) => renderMeld(m, i, 'AI'))}
        </div>
      )}

      {/* Discard pile */}
      {topDiscard && (
        <div className="crazy8-table">
          <div className={`crazy8-top-card ${topDiscard.suit === 'hearts' || topDiscard.suit === 'diamonds' ? 'red' : 'black'}`}>
            <span className="crazy8-card-rank">{topDiscard.rank}</span>
            <span className="crazy8-card-suit">{SUIT_SYMBOLS[topDiscard.suit]}</span>
          </div>
        </div>
      )}

      {/* Status */}
      <div className="crazy8-last-action">
        {isMyTurn && phase === 'discard'
          ? 'Click a card to discard'
          : lastPlay || (isMyTurn ? `Phase: ${phase}` : 'AI thinking...')}
      </div>

      {/* Draw buttons */}
      {isMyTurn && phase === 'draw' && drawMoves.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', margin: '0.5rem 0' }}>
          {drawMoves.map((m, i) => (
            <button key={i} className="crazy8-draw-btn" onClick={() => handleMove(m.rule, m.params)}
              style={{ fontSize: '0.9rem', padding: '0.4rem 1rem' }}>
              {m.rule === 'draw_deck' ? '📥 Draw 2 from deck' : `📥 Pick up pile (${discardCards.length})`}
            </button>
          ))}
        </div>
      )}

      {/* Meld buttons */}
      {isMyTurn && phase === 'meld' && (
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', margin: '0.5rem 0', flexWrap: 'wrap' }}>
          {meldMoves.map((m, i) => {
            const cards = m.params._cards
            const label = cards
              ? cards.map(c => `${c.rank}${SUIT_SYMBOLS[c.suit] || ''}`).join(' ')
              : `Meld #${m.params.meld_id + 1}`
            return (
              <button key={`m${i}`} className="crazy8-draw-btn" onClick={() => handleMove(m.rule, m.params)}
                style={{ fontSize: '0.85rem', padding: '0.3rem 0.8rem' }}>
                Meld: {label}
              </button>
            )
          })}
          {addMoves.map((m, i) => (
            <button key={`a${i}`} className="crazy8-draw-btn" onClick={() => handleMove(m.rule, m.params)}
              style={{ fontSize: '0.85rem', padding: '0.3rem 0.8rem' }}>
              Add to meld
            </button>
          ))}
          {skipMeld && (
            <button className="crazy8-draw-btn" onClick={() => handleMove(skipMeld.rule, skipMeld.params)}
              style={{ fontSize: '0.85rem', padding: '0.3rem 0.8rem' }}>
              Done melding →
            </button>
          )}
        </div>
      )}

      {/* My melds */}
      {myMelds.length > 0 && (
        <div style={{ textAlign: 'center', margin: '0.3rem 0' }}>
          <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.7rem', color: 'var(--accent)' }}>Your melds</div>
          {myMelds.map((m, i) => renderMeld(m, i, 'You'))}
        </div>
      )}

      {/* Hand */}
      <div className="crazy8-my-hand">
        <div className="crazy8-hand-label">Your hand ({myHand.length} cards)</div>
        <div className="gofish-cards">
          {sortedHand.map((card) => {
            const canDiscard = phase === 'discard' && discardMoves.some(m => m.params.card_id === card.id)
            const isWild = card.rank === '2' || card.rank === 'Joker'
            return (
              <button
                key={card.id}
                className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'} ${!canDiscard && phase === 'discard' ? 'disabled' : ''}`}
                style={isWild ? { borderColor: '#5cba6e', borderWidth: '2px' } : {}}
                onClick={() => canDiscard && handleMove('discard', { card_id: card.id })}
                disabled={disabled || !isMyTurn || (phase === 'discard' && !canDiscard)}
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

export default CanastaBoard
