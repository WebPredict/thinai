/**
 * Unified game board renderer — routes to the correct board component
 * based on gameType and board_type. Used for both play mode and replay mode.
 */
import GridBoard from './GridBoard'
import MancalaBoard from './MancalaBoard'
import NimBoard from './NimBoard'
import CheckersBoard from './CheckersBoard'
import BlackjackBoard from './BlackjackBoard'
import CrazyEightsBoard from './CrazyEightsBoard'
import GoFishBoard from './GoFishBoard'
import WarBoard from './WarBoard'
import ChutesAndLaddersBoard from './ChutesAndLaddersBoard'
import BackgammonBoard from './BackgammonBoard'
import HexBoard from './HexBoard'
import TrackBoard from './TrackBoard'
import HeartsBoard from './HeartsBoard'
import GinRummyBoard from './GinRummyBoard'
import PokerBoard from './PokerBoard'
import WizardBoard from './WizardBoard'
import ScrabbleBoard from './ScrabbleBoard'
import CanastaBoard from './CanastaBoard'

export default function GameBoardRenderer({ gameType, state, onMove, disabled, aiLastMove }) {
  if (!state) return null

  const noOp = () => {}
  const move = onMove || noOp
  const off = disabled ?? true

  switch (gameType) {
    case 'mancala':
      return <MancalaBoard state={state} onMove={move} disabled={off} aiLastMove={aiLastMove} />
    case 'nim':
      return <NimBoard state={state} onMove={move} disabled={off} />
    case 'checkers':
      return <CheckersBoard state={state} onMove={move} disabled={off} />
    case 'uno':
    case 'crazy_eights':
      return <CrazyEightsBoard state={state} onMove={move} disabled={off} />
    case 'blackjack':
      return <BlackjackBoard state={state} onMove={move} disabled={off} />
    case 'go_fish':
      return <GoFishBoard state={state} onMove={move} disabled={off} />
    case 'hex':
      return <HexBoard state={state} onMove={move} disabled={off} />
    case 'backgammon':
      return <BackgammonBoard state={state} onMove={move} disabled={off} />
    case 'hearts':
      return <HeartsBoard state={state} onMove={move} disabled={off} />
    case 'wizard':
    case 'spades':
      return <WizardBoard state={state} onMove={move} disabled={off} />
    case 'scrabble':
      return <ScrabbleBoard state={state} onMove={move} disabled={off} />
    case 'canasta':
      return <CanastaBoard state={state} onMove={move} disabled={off} />
    case 'gin_rummy':
      return <GinRummyBoard state={state} onMove={move} disabled={off} />
    case 'five_card_draw':
      return <PokerBoard state={state} onMove={move} disabled={off} />
    case 'war':
      return <WarBoard state={state} onMove={move} disabled={off} />
    case 'chutes_and_ladders':
      return <ChutesAndLaddersBoard state={state} onMove={move} disabled={off} aiLastMove={aiLastMove} />
    default:
      // Generic fallback based on board type
      if (state.board_type === 'track') {
        return <TrackBoard state={state} onMove={move} disabled={off} />
      }
      if (state.board_type === 'card_zones') {
        return <CrazyEightsBoard state={state} onMove={move} disabled={off} />
      }
      return <GridBoard state={state} onMove={move} disabled={off} gameType={gameType} aiLastMove={aiLastMove} />
  }
}
