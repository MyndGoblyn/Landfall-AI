"""Deterministic maximum-weight matching for addition/cut portfolios."""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple


class SwapPortfolioOptimizer:
    """Choose globally compatible swaps from prevalidated pair options.

    Each addition can either remain standalone or consume one cut.  Dynamic
    programming over the (small) cut bitmask avoids the common greedy failure
    where an early addition takes the only safe cut for a later, much stronger
    replacement.
    """

    VERSION = "swap-portfolio-v1"

    def select(
        self,
        option_rows: Sequence[Sequence[Mapping]],
        cut_count: int,
    ) -> List[Optional[Dict]]:
        if not option_rows:
            return []
        if cut_count < 0 or cut_count > 20:
            raise ValueError("cut_count must be between 0 and 20")

        # mask -> (total score, matched count, choices)
        states: Dict[int, Tuple[float, int, Tuple[Optional[Dict], ...]]] = {
            0: (0.0, 0, tuple())
        }
        for row in option_rows:
            next_states: Dict[
                int,
                Tuple[float, int, Tuple[Optional[Dict], ...]],
            ] = {}
            ordered_options = sorted(
                (dict(option) for option in row),
                key=lambda option: (
                    -float(option.get("score") or 0),
                    int(option.get("cut_index", 0)),
                ),
            )
            for mask, (score, matched, choices) in states.items():
                self._keep(
                    next_states,
                    mask,
                    (score, matched, (*choices, None)),
                )
                for option in ordered_options:
                    cut_index = int(option["cut_index"])
                    bit = 1 << cut_index
                    if mask & bit:
                        continue
                    self._keep(
                        next_states,
                        mask | bit,
                        (
                            score + float(option.get("score") or 0),
                            matched + 1,
                            (*choices, option),
                        ),
                    )
            states = next_states

        best = max(
            states.values(),
            key=lambda state: (
                state[0],
                state[1],
                tuple(
                    -1 if option is None else -int(option["cut_index"])
                    for option in state[2]
                ),
            ),
        )
        return list(best[2])

    @staticmethod
    def _keep(
        states: Dict[int, Tuple[float, int, Tuple[Optional[Dict], ...]]],
        mask: int,
        candidate: Tuple[float, int, Tuple[Optional[Dict], ...]],
    ) -> None:
        existing = states.get(mask)
        if existing is None or (candidate[0], candidate[1]) > (
            existing[0],
            existing[1],
        ):
            states[mask] = candidate
