import { useState } from 'react'

const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }
const RANK_ORDER = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
const SUIT_ORDER = ['hearts','diamonds','clubs','spades']
const CARD_VALUES = { A:1, '2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, J:10, Q:10, K:10 }

function GinRummyBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const deckSize = zones.deck?.size || 0
  const discardCards = zones.discard?.cards || []
  const topDiscard = discardCards.length > 0 ? discardCards[discardCards.length - 1] : null
  const phase = vars.phase || 'draw'
  const lastAction = vars.last_action || ''
  const lastPlay = vars.last_play || ''
  const isMyTurn = state.current_player === 'player1'
  const roundOver = vars.round_over

  const canDrawDiscard = state.legal_moves?.some(m => m.rule === 'draw_discard')
  const canDrawDeck = state.legal_moves?.some(m => m.rule === 'draw_deck')
  const canKnock = state.legal_moves?.some(m => m.rule === 'knock')
  const discardableIds = new Set()
  for (const m of (state.legal_moves || [])) {
    if ((m.rule === 'discard' || m.rule === 'knock') && m.params.card_id != null)
      discardableIds.add(m.params.card_id)
  }

  const handleDraw = (source) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.rule === source)
    if (move) onMove(move.rule, move.params)
  }

  const handleDiscard = (cardId) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.rule === 'discard' && m.params.card_id === cardId)
    if (move) onMove(move.rule, move.params)
  }

  const handleKnock = (cardId) => {
    if (disabled) return
    const move = state.legal_moves?.find(m => m.rule === 'knock' && m.params.card_id === cardId)
    if (move) onMove(move.rule, move.params)
  }

  // Sort hand by suit then rank for readability
  const sortedHand = [...myHand].sort((a, b) => {
    const si = SUIT_ORDER.indexOf(a.suit) - SUIT_ORDER.indexOf(b.suit)
    return si !== 0 ? si : RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank)
  })

  // Find melds and deadwood for display
  const meldCardIds = new Set()
  const findMelds = (cards) => {
    const melds = []
    // Sets: 3+ of same rank
    const byRank = {}
    cards.forEach(c => { (byRank[c.rank] = byRank[c.rank] || []).push(c) })
    Object.values(byRank).forEach(group => { if (group.length >= 3) melds.push(group.slice(0, Math.min(group.length, 4))) })
    // Runs: 3+ sequential same suit
    const bySuit = {}
    cards.forEach(c => { (bySuit[c.suit] = bySuit[c.suit] || []).push(c) })
    Object.values(bySuit).forEach(group => {
      const sorted = [...group].sort((a, b) => RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank))
      let run = [sorted[0]]
      for (let i = 1; i < sorted.length; i++) {
        if (RANK_ORDER.indexOf(sorted[i].rank) === RANK_ORDER.indexOf(run[run.length-1].rank) + 1) {
          run.push(sorted[i])
        } else {
          if (run.length >= 3) melds.push([...run])
          run = [sorted[i]]
        }
      }
      if (run.length >= 3) melds.push([...run])
    })
    // Greedy non-overlapping (good enough for display)
    const used = new Set()
    const best = []
    melds.sort((a, b) => b.length - a.length)
    melds.forEach(m => {
      if (m.every(c => !used.has(c.id))) {
        best.push(m)
        m.forEach(c => used.add(c.id))
      }
    })
    return { melds: best, meldIds: used }
  }
  const { melds, meldIds } = findMelds(myHand)
  const deadwood = myHand.filter(c => !meldIds.has(c.id)).reduce((s, c) => s + (CARD_VALUES[c.rank] || 0), 0)

  return (
    <div className="crazy8-board">
      <div className="crazy8-info">
        <span>Deck: {deckSize} cards remaining</span>
        <span>AI hand: {oppHandSize} cards</span>
      </div>

      <div className="crazy8-table">
        <div className="crazy8-deck-pile" onClick={() => canDrawDeck && handleDraw('draw_deck')}
             style={{ cursor: canDrawDeck ? 'pointer' : 'default' }}>
        </div>
        {topDiscard && (
          <div className={`crazy8-top-card ${topDiscard.suit === 'hearts' || topDiscard.suit === 'diamonds' ? 'red' : 'black'}`}
               onClick={() => canDrawDiscard && handleDraw('draw_discard')}
               style={{ cursor: canDrawDiscard ? 'pointer' : 'default' }}>
            <span className="crazy8-card-rank">{topDiscard.rank}</span>
            <span className="crazy8-card-suit">{SUIT_SYMBOLS[topDiscard.suit]}</span>
          </div>
        )}
      </div>

      <div className="crazy8-last-action">
        {phase === 'draw' && isMyTurn && !roundOver && 'Draw from deck or discard pile'}
        {phase === 'discard' && isMyTurn && !roundOver && (canKnock ? 'Discard a card, or click Knock to end the round' : 'Discard a card')}
        {!isMyTurn && !roundOver && 'AI is thinking...'}
        {lastPlay && roundOver && lastPlay}
      </div>

      {/* Reveal AI's hand at game over */}
      {roundOver && zones.hand_p2?.cards?.length > 0 && (() => {
        const aiHand = zones.hand_p2.cards
        const { melds: aiMelds, meldIds: aiMeldIds } = findMelds(aiHand)
        const aiDeadwood = aiHand.filter(c => !aiMeldIds.has(c.id)).reduce((s, c) => s + (CARD_VALUES[c.rank] || 0), 0)
        const aiSorted = [...aiHand].sort((a, b) => {
          const aM = aiMeldIds.has(a.id) ? 0 : 1
          const bM = aiMeldIds.has(b.id) ? 0 : 1
          if (aM !== bM) return aM - bM
          const si = SUIT_ORDER.indexOf(a.suit) - SUIT_ORDER.indexOf(b.suit)
          return si !== 0 ? si : RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank)
        })
        return (
          <div style={{ marginTop: '1rem', textAlign: 'center' }}>
            <div className="crazy8-hand-label">
              AI's hand — Deadwood: {aiDeadwood}
            </div>
            {aiMelds.length > 0 && (
              <div style={{ fontSize: '0.8rem', color: 'var(--ink-dim)', marginBottom: '0.3rem', fontFamily: 'Menlo, monospace' }}>
                Melds: {aiMelds.map(m => m.map(c => `${c.rank}${SUIT_SYMBOLS[c.suit]}`).join(' ')).join(' | ')}
              </div>
            )}
            <div className="gofish-cards">
              {aiSorted.map(card => (
                <div key={card.id}
                  className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'}`}
                  style={aiMeldIds.has(card.id) ? { borderColor: '#5cba6e', borderWidth: '2px', background: '#f0fff4' } : {}}
                >
                  <span className="gofish-card-rank">{card.rank}</span>
                  <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
                </div>
              ))}
            </div>
          </div>
        )
      })()}

      <div className="crazy8-my-hand">
        <div className="crazy8-hand-label">
          Your hand ({myHand.length} cards) — Deadwood: {deadwood} {deadwood <= 10 && myHand.length >= 10 ? '(can knock!)' : ''} {deadwood === 0 && myHand.length >= 10 ? '🎉 GIN!' : ''}
        </div>
        {melds.length > 0 && (
          <div style={{ fontSize: '0.8rem', color: 'var(--ink-dim)', marginBottom: '0.3rem', fontFamily: 'Menlo, monospace' }}>
            Melds: {melds.map((m, i) => m.map(c => `${c.rank}${SUIT_SYMBOLS[c.suit]}`).join(' ')).join(' | ')}
          </div>
        )}
        <div className="gofish-cards">
          {/* Show meld cards first, then deadwood */}
          {[...sortedHand].sort((a, b) => {
            const aM = meldIds.has(a.id) ? 0 : 1
            const bM = meldIds.has(b.id) ? 0 : 1
            if (aM !== bM) return aM - bM
            // Within melds/deadwood, keep suit+rank order
            const si = SUIT_ORDER.indexOf(a.suit) - SUIT_ORDER.indexOf(b.suit)
            return si !== 0 ? si : RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank)
          }).map((card) => {
            const canDiscard = discardableIds.has(card.id) && phase === 'discard'
            const inMeld = meldIds.has(card.id)
            return (
              <button
                key={card.id}
                className={`gofish-card ${card.suit === 'hearts' || card.suit === 'diamonds' ? 'red' : 'black'} ${!canDiscard ? 'disabled' : ''}`}
                style={inMeld ? { borderColor: '#5cba6e', borderWidth: '2px', background: '#f0fff4' } : {}}
                onClick={() => canDiscard && handleDiscard(card.id)}
                disabled={disabled || !isMyTurn || !canDiscard}
              >
                <span className="gofish-card-rank">{card.rank}</span>
                <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
              </button>
            )
          })}
        </div>
        {isMyTurn && phase === 'discard' && !roundOver && (
          canKnock ? (
            <div style={{ marginTop: '0.75rem', textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--accent)', marginBottom: '0.4rem', fontFamily: 'Menlo, monospace' }}>
                Deadwood is {deadwood} — you can knock! Pick a card to discard:
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                {sortedHand.filter(c => !meldIds.has(c.id)).slice(0, 4).map(card => (
                  <button key={`knock-${card.id}`} className="crazy8-draw-btn"
                    onClick={() => handleKnock(card.id)}>
                    Knock (discard {card.rank}{SUIT_SYMBOLS[card.suit]})
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--ink-dim)', fontFamily: 'Menlo, monospace', textAlign: 'center' }}>
              Knock requires deadwood ≤ 10 (currently {deadwood}). Discard a card to continue.
            </div>
          )
        )}
      </div>
    </div>
  )
}

export default GinRummyBoard
