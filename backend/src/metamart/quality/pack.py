"""Default rule pack: every registered rule active with its registered defaults."""
from metamart.quality.types import RulePack


def default_pack() -> RulePack:
    return RulePack(pack_id="default", name="Default", rules=[])
