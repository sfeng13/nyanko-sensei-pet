import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nyanko_choreography import ALL_CLIPS, IDLE, PUBLIC, SQUINT, Choreography  # noqa: E402


def test_satisfied_squint_is_a_public_one_shot_action():
    choreography = Choreography()

    assert SQUINT == '眯眯眼'
    assert SQUINT in PUBLIC
    assert SQUINT in ALL_CLIPS
    assert choreography.request(SQUINT) == SQUINT
    assert choreography.current == SQUINT
    assert choreography.finished(SQUINT) == IDLE
