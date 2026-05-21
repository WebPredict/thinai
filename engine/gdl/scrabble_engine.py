"""Scrabble word placement engine for ThinAI.

Enumerates valid word placements given a board state and player's rack.
Handles cross-word validation and bonus square scoring.
"""

from __future__ import annotations
from collections import Counter

from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace
from engine.gdl.scrabble_dict import SCRABBLE_WORDS, LETTER_VALUES
from engine.gdl.scrabble_tiles import BONUS_SQUARES


def get_valid_placements(state: GameState, player: str, quick: bool = False) -> list[dict]:
    """Find all valid word placements for the current player."""
    suffix = "p1" if player == "player1" else "p2"
    rack = state.state_vars.get(f"rack_{suffix}", [])
    if not rack:
        return []

    board = state.board
    if not isinstance(board, GridBoard):
        return []

    rows, cols = board.rows, board.cols
    center = (rows // 2, cols // 2)

    # Build board letter map
    board_letters = {}
    for space in board.spaces:
        piece = state.get_piece(space)
        if piece and piece.name and len(piece.name) == 1:
            board_letters[(space.row, space.col)] = piece.name

    is_empty_board = len(board_letters) == 0
    rack_letters = [t['letter'] for t in rack]
    rack_counter = Counter(rack_letters)

    # Find anchor squares (empty cells adjacent to existing tiles)
    anchors = set()
    if is_empty_board:
        anchors.add(center)
    else:
        for (r, c) in board_letters:
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in board_letters:
                    anchors.add((nr, nc))

    # Strategy: try a small batch of words, stop early if we find enough.
    # Sort candidates by length desc (longer words = higher scores).
    # Quick filter: every unique letter must be in rack or on board.
    all_board_letters = set(board_letters.values())
    rack_set = set(rack_letters)
    available = rack_set | all_board_letters

    formable = [w for w in SCRABBLE_WORDS
                if 2 <= len(w) <= 7 and all(c in available for c in set(w))]
    formable.sort(key=len, reverse=True)

    placements = []
    seen = set()
    words_tried = 0

    for word in formable:
        words_tried += 1
        wlen = len(word)

        for anchor_r, anchor_c in anchors:
            # Horizontal: word could start up to wlen-1 before anchor
            for offset in range(wlen):
                sc = anchor_c - offset
                if sc < 0 or sc + wlen > cols:
                    continue
                p = _try_placement(word, anchor_r, sc, 0, 1,
                                   board_letters, rack_letters, anchors,
                                   is_empty_board, center, rows, cols, seen)
                if p:
                    p['score'] = _calculate_score(p, board_letters)
                    placements.append(p)

            # Vertical
            for offset in range(wlen):
                sr = anchor_r - offset
                if sr < 0 or sr + wlen > rows:
                    continue
                p = _try_placement(word, sr, anchor_c, 1, 0,
                                   board_letters, rack_letters, anchors,
                                   is_empty_board, center, rows, cols, seen)
                if p:
                    p['score'] = _calculate_score(p, board_letters)
                    placements.append(p)

        # Quick mode: stop early once we have enough
        if quick:
            if len(placements) >= 5 and words_tried >= 30:
                break
            if words_tried >= 200:
                break

    placements.sort(key=lambda p: p['score'], reverse=True)
    for i, p in enumerate(placements):
        p['id'] = i
    return placements[:10]


def _try_placement(word, start_r, start_c, dr, dc,
                   board_letters, rack_letters, anchors,
                   is_empty_board, center, rows, cols, seen):
    """Try placing a word at a specific position. Returns placement dict or None."""
    direction = 'V' if dr == 1 else 'H'
    key = (word, start_r, start_c, direction)
    if key in seen:
        return None

    tiles_used = []
    rack_copy = list(rack_letters)
    uses_board_tile = False
    covers_center = False

    for i, letter in enumerate(word):
        r = start_r + i * dr
        c = start_c + i * dc
        existing = board_letters.get((r, c))

        if existing:
            if existing != letter:
                return None
            uses_board_tile = True
        else:
            if letter in rack_copy:
                rack_copy.remove(letter)
                tiles_used.append({'letter': letter, 'row': r, 'col': c})
                if (r, c) == center:
                    covers_center = True
            else:
                return None

    if not tiles_used:
        return None
    if is_empty_board and not covers_center:
        return None

    # Check: word must not extend into adjacent existing tiles
    # (otherwise "COZY" next to a "D" makes "COZYD" which isn't valid)
    end_r = start_r + len(word) * dr
    end_c = start_c + len(word) * dc
    if 0 <= end_r < rows and 0 <= end_c < cols and (end_r, end_c) in board_letters:
        return None  # tile immediately after word
    prev_r = start_r - dr
    prev_c = start_c - dc
    if 0 <= prev_r < rows and 0 <= prev_c < cols and (prev_r, prev_c) in board_letters:
        return None  # tile immediately before word

    if not is_empty_board and not uses_board_tile:
        # Must have cross-contact: a placed tile adjacent to board tile perpendicular
        cross_dr = 0 if direction == 'V' else 1
        cross_dc = 0 if direction == 'H' else 1
        has_contact = False
        for t in tiles_used:
            for sign in (1, -1):
                if (t['row'] + sign * cross_dr, t['col'] + sign * cross_dc) in board_letters:
                    has_contact = True
                    break
            if has_contact:
                break
        if not has_contact:
            return None

    # Validate cross-words
    if not _validate_cross_words(tiles_used, board_letters, rows, cols, direction):
        return None

    seen.add(key)
    return {
        'word': word,
        'start_row': start_r,
        'start_col': start_c,
        'direction': direction,
        'tiles_used': tiles_used,
    }


def _validate_cross_words(tiles_used, board_letters, rows, cols, direction):
    """Check that all cross-words formed by placed tiles are valid."""
    cross_dr = 0 if direction == 'V' else 1
    cross_dc = 0 if direction == 'H' else 1

    for tile in tiles_used:
        r, c = tile['row'], tile['col']

        # Extend backward
        nr, nc = r - cross_dr, c - cross_dc
        prefix = ''
        while 0 <= nr < rows and 0 <= nc < cols:
            letter = board_letters.get((nr, nc))
            if not letter:
                break
            prefix = letter + prefix
            nr -= cross_dr
            nc -= cross_dc

        # Extend forward
        nr, nc = r + cross_dr, c + cross_dc
        suffix = ''
        while 0 <= nr < rows and 0 <= nc < cols:
            letter = board_letters.get((nr, nc))
            if not letter:
                break
            suffix += letter
            nr += cross_dr
            nc += cross_dc

        cross_word = prefix + tile['letter'] + suffix
        if len(cross_word) > 1 and cross_word not in SCRABBLE_WORDS:
            return False

    return True


def _calculate_score(placement, board_letters):
    """Calculate placement score including bonus squares and cross-words."""
    word = placement['word']
    tiles_used = {(t['row'], t['col']): t['letter'] for t in placement['tiles_used']}
    start_r = placement['start_row']
    start_c = placement['start_col']
    direction = placement['direction']
    dr = 1 if direction == 'V' else 0
    dc = 1 if direction == 'H' else 0

    word_multiplier = 1
    word_score = 0

    for i, letter in enumerate(word):
        r = start_r + i * dr
        c = start_c + i * dc
        letter_value = LETTER_VALUES.get(letter, 0)
        bonus = ''

        if (r, c) in tiles_used:
            bonus = BONUS_SQUARES.get((r, c), '')
            if bonus == 'DL':
                letter_value *= 2
            elif bonus == 'TL':
                letter_value *= 3
            elif bonus == 'DW':
                word_multiplier *= 2
            elif bonus == 'TW':
                word_multiplier *= 3

        word_score += letter_value

    total = word_score * word_multiplier

    # Add cross-word scores for each newly placed tile
    cross_dr = 0 if direction == 'V' else 1
    cross_dc = 0 if direction == 'H' else 1

    for tile in placement['tiles_used']:
        r, c = tile['row'], tile['col']
        # Build cross-word
        prefix_letters = []
        nr, nc = r - cross_dr, c - cross_dc
        while 0 <= nr < 9 and 0 <= nc < 9:
            letter = board_letters.get((nr, nc))
            if not letter:
                break
            prefix_letters.insert(0, (nr, nc, letter))
            nr -= cross_dr
            nc -= cross_dc

        suffix_letters = []
        nr, nc = r + cross_dr, c + cross_dc
        while 0 <= nr < 9 and 0 <= nc < 9:
            letter = board_letters.get((nr, nc))
            if not letter:
                break
            suffix_letters.append((nr, nc, letter))
            nr += cross_dr
            nc += cross_dc

        if prefix_letters or suffix_letters:
            cw_score = 0
            cw_mult = 1
            for _, _, cl in prefix_letters:
                cw_score += LETTER_VALUES.get(cl, 0)
            # The placed tile (with its bonus)
            tv = LETTER_VALUES.get(tile['letter'], 0)
            bonus = BONUS_SQUARES.get((r, c), '')
            if bonus == 'DL':
                tv *= 2
            elif bonus == 'TL':
                tv *= 3
            elif bonus == 'DW':
                cw_mult *= 2
            elif bonus == 'TW':
                cw_mult *= 3
            cw_score += tv
            for _, _, cl in suffix_letters:
                cw_score += LETTER_VALUES.get(cl, 0)
            total += cw_score * cw_mult

    return total
