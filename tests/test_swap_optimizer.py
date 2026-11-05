import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.swap_optimizer import SwapPortfolioOptimizer


def test_joint_matching_avoids_greedy_cut_assignment():
    optimizer = SwapPortfolioOptimizer()

    selected = optimizer.select(
        [
            [
                {"cut_index": 0, "score": 10},
                {"cut_index": 1, "score": 9},
            ],
            [
                {"cut_index": 0, "score": 100},
            ],
        ],
        cut_count=2,
    )

    assert [option["cut_index"] for option in selected] == [1, 0]


def test_joint_matching_can_abstain_from_negative_swap():
    optimizer = SwapPortfolioOptimizer()

    assert optimizer.select(
        [[{"cut_index": 0, "score": -3}]],
        cut_count=1,
    ) == [None]
