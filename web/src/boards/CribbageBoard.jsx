const SUIT_SYMBOLS = { hearts: '\u2665', diamonds: '\u2666', clubs: '\u2663', spades: '\u2660' }
const SUIT_ORDER = ['clubs', 'diamonds', 'spades', 'hearts']
const RANK_ORDER = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']

function CribbageBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const phase = vars.phase || 'discard'
  const dealer = vars.dealer || 'player2'
  const p1Score = vars.p1_score || 0
  const p2Score = vars.p2_score || 0
  const pegCount = vars.peg_count || 0
  const lastPlay = vars.last_play || ''
  const isMyTurn = state.current_player === 'player1'
  const iAmDealer = dealer === 'player1'

  const myHand = zones.hand_p1?.cards || []
  const oppHandSize = zones.hand_p2?.size || 0
  const starterCards = zones.starter?.cards || []
  const playAreaCards = zones.play_area?.cards || []
  const cribSize = zones.crib?.size || 0
  const p1DiscardsLeft = 2 - (vars.p1_discards_done || 0)

  // Build playable card IDs from legal moves
  const playableIds = new Set()
  let hasGoMove = false
  let hasScoreShow = false
  let hasCutMove = false
  for (const m of (state.legal_moves || [])) {
    if (m.params?.card_id != null) playableIds.add(m.params.card_id)
    if (m.rule === 'say_go') hasGoMove = true
    if (m.rule === 'score_show') hasScoreShow = true
    if (m.rule === 'cut_deck') hasCutMove = true
  }

  const handleCardClick = (cardId) => {
    if (disabled || !isMyTurn) return
    const move = state.legal_moves?.find(m => m.params?.card_id === cardId)
    if (move) onMove(move.rule, move.params)
  }

  const handleAction = (rule) => {
    if (disabled || !isMyTurn) return
    const move = state.legal_moves?.find(m => m.rule === rule)
    if (move) onMove(move.rule, move.params)
  }

  const sortedHand = [...myHand].sort((a, b) => {
    const ri = RANK_ORDER.indexOf(a.rank) - RANK_ORDER.indexOf(b.rank)
    return ri !== 0 ? ri : SUIT_ORDER.indexOf(a.suit) - SUIT_ORDER.indexOf(b.suit)
  })

  // Phase-specific prompt
  let prompt = lastPlay
  if (isMyTurn) {
    if (phase === 'discard') {
      prompt = p1DiscardsLeft > 0
        ? `Discard ${p1DiscardsLeft} card${p1DiscardsLeft > 1 ? 's' : ''} to the crib`
        : 'Waiting for AI to discard...'
    } else if (phase === 'cut') {
      prompt = 'Cut the deck to reveal the starter card'
    } else if (phase === 'peg') {
      if (hasGoMove) prompt = "You can't play — say Go"
      else if (playableIds.size > 0) prompt = 'Play a card (count toward 31)'
    } else if (phase.startsWith('show') || phase === 'round_end') {
      prompt = lastPlay || 'Score this hand'
    }
  } else {
    prompt = lastPlay || "AI's turn..."
  }

  const renderCard = (card, playable, onClick) => {
    const isRed = card.suit === 'hearts' || card.suit === 'diamonds'
    return (
      <button
        key={card.id}
        className={`gofish-card ${isRed ? 'red' : 'black'} ${!playable ? 'disabled' : ''}`}
        onClick={() => playable && onClick?.(card.id)}
        disabled={disabled || !playable}
      >
        <span className="gofish-card-rank">{card.rank}</span>
        <span className="gofish-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
      </button>
    )
  }

  const renderCardStatic = (card) => {
    const isRed = card.suit === 'hearts' || card.suit === 'diamonds'
    return (
      <div key={card.id}
        className={`crazy8-top-card ${isRed ? 'red' : 'black'}`}
        style={{ width: '52px', height: '74px', fontSize: '0.9rem' }}
      >
        <span className="crazy8-card-rank">{card.rank}</span>
        <span className="crazy8-card-suit">{SUIT_SYMBOLS[card.suit]}</span>
      </div>
    )
  }

  return (
    <div className="crazy8-board">
      {/* Scores */}
      <div className="crazy8-info" style={{ gap: '1.5rem' }}>
        <span>You: <b>{p1Score}</b>/121</span>
        <span>AI: <b>{p2Score}</b>/121</span>
        <span>{iAmDealer ? 'You deal' : 'AI deals'}</span>
      </div>

      {/* Starter card + peg count */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2rem', margin: '0.5rem 0' }}>
        {starterCards.length > 0 && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.75rem', color: 'var(--ink-faint)', marginBottom: '0.3rem' }}>
              Starter
            </div>
            {renderCardStatic(starterCards[0])}
          </div>
        )}

        {phase === 'peg' && (
          <div style={{
            textAlign: 'center', padding: '0.8rem 1.5rem',
            background: 'rgba(212,166,86,0.08)', border: '1px solid rgba(212,166,86,0.2)',
            borderRadius: '8px',
          }}>
            <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.75rem', color: 'var(--ink-faint)' }}>
              Count
            </div>
            <div style={{ fontFamily: 'Menlo, monospace', fontSize: '2rem', color: 'var(--accent)', fontWeight: 'bold' }}>
              {pegCount}<span style={{ fontSize: '1rem', color: 'var(--ink-faint)' }}>/31</span>
            </div>
          </div>
        )}

        {phase === 'discard' && (
          <div style={{
            textAlign: 'center', padding: '0.8rem 1.5rem',
            background: 'rgba(212,166,86,0.08)', border: '1px solid rgba(212,166,86,0.2)',
            borderRadius: '8px',
          }}>
            <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.75rem', color: 'var(--ink-faint)' }}>
              Crib
            </div>
            <div style={{ fontFamily: 'Menlo, monospace', fontSize: '1.5rem', color: 'var(--ink)' }}>
              {cribSize}/4
            </div>
          </div>
        )}
      </div>

      {/* Play area — cards played during pegging */}
      {phase === 'peg' && playAreaCards.length > 0 && (
        <div style={{ textAlign: 'center', margin: '0.3rem 0' }}>
          <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.75rem', color: 'var(--ink-faint)', marginBottom: '0.3rem' }}>
            Cards played
          </div>
          <div style={{ display: 'flex', gap: '4px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {playAreaCards.map(card => renderCardStatic(card))}
          </div>
        </div>
      )}

      {/* Status / prompt */}
      <div className="crazy8-last-action">{prompt}</div>

      {/* AI hand count */}
      <div style={{ fontFamily: 'Menlo, monospace', fontSize: '0.8rem', color: 'var(--ink-faint)', textAlign: 'center' }}>
        AI hand: {oppHandSize} card{oppHandSize !== 1 ? 's' : ''}
      </div>

      {/* Action buttons */}
      {isMyTurn && hasCutMove && (
        <button className="crazy8-draw-btn" onClick={() => handleAction('cut_deck')}>
          Cut the deck
        </button>
      )}
      {isMyTurn && hasGoMove && (
        <button className="crazy8-draw-btn" onClick={() => handleAction('say_go')}>
          Go!
        </button>
      )}
      {isMyTurn && hasScoreShow && (
        <button className="crazy8-draw-btn" onClick={() => handleAction('score_show')}>
          {phase === 'round_end' ? 'Deal next round' : 'Score hand'}
        </button>
      )}

      {/* Player's hand */}
      <div className="crazy8-my-hand">
        <div className="crazy8-hand-label">
          Your hand ({myHand.length} card{myHand.length !== 1 ? 's' : ''})
        </div>
        <div className="gofish-cards">
          {sortedHand.map(card => renderCard(card, playableIds.has(card.id), handleCardClick))}
        </div>
      </div>
    </div>
  )
}

export default CribbageBoard
