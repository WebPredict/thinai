import { useState } from 'react'

function WarBoard({ state, onMove, disabled }) {
  if (!state) return null

  const zones = state.card_zones || {}
  const vars = state.state_vars || {}
  const p1Size = zones.hand_p1?.size || 0
  const p2Size = zones.hand_p2?.size || 0
  const lastP1 = vars.last_p1_card || ''
  const lastP2 = vars.last_p2_card || ''
  const roundWinner = vars.round_winner || ''

  const handleBattle = () => {
    if (disabled) return
    const moves = state.legal_moves
    if (moves && moves.length > 0) {
      onMove(moves[0].rule, moves[0].params)
    }
  }

  return (
    <div className="war-board">
      <div className="war-players">
        <div className="war-player">
          <div className="war-deck-pile war-p1-pile">
            <span className="war-card-count">{p1Size}</span>
          </div>
          <div className="war-player-label">You</div>
        </div>

        <div className="war-center">
          {lastP1 && lastP2 ? (
            <div className="war-flipped">
              <div className="war-card war-card-p1">{lastP1}</div>
              <div className="war-vs">vs</div>
              <div className="war-card war-card-p2">{lastP2}</div>
            </div>
          ) : (
            <div className="war-prompt">Flip cards!</div>
          )}
          {roundWinner && (
            <div className={`war-round-result ${roundWinner === 'war' ? 'war-tie' : ''}`}>
              {roundWinner === 'player1' ? 'You win this round!' :
               roundWinner === 'player2' ? 'AI wins this round!' :
               roundWinner === 'war' ? 'WAR!' : ''}
            </div>
          )}
        </div>

        <div className="war-player">
          <div className="war-deck-pile war-p2-pile">
            <span className="war-card-count">{p2Size}</span>
          </div>
          <div className="war-player-label">AI</div>
        </div>
      </div>

      {!state.game_result && (
        <button className="war-flip-btn" onClick={handleBattle} disabled={disabled}>
          Flip Cards
        </button>
      )}
    </div>
  )
}

export default WarBoard
