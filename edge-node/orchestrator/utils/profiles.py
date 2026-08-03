from dataclasses import dataclass, asdict
import json
from typing import Dict

@dataclass
class EventProfile:
    name: str
    description: str
    engagement_threshold: float
    motion_velocity_threshold: int
    min_sustain_frames: int
    cooldown_base_sec: float
    allow_burst: bool
    lookback_seconds: float
    use_pose_model: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data: str):
        return EventProfile(**json.loads(data))


PROFILES: Dict[str, EventProfile] = {
    "DEFAULT": EventProfile(
        name="Default Photography",
        description="Standard balanced capture logic.",
        engagement_threshold=0.55,
        motion_velocity_threshold=15,
        min_sustain_frames=3,
        cooldown_base_sec=12.0,
        allow_burst=False,
        lookback_seconds=1.0,
        use_pose_model=False
    ),
    "CRICKET": EventProfile(
        name="Cricket Match",
        description="High motion, tracks bats/bowling action via pose.",
        engagement_threshold=0.30,  # Lower engagement needed for sports
        motion_velocity_threshold=35, # Expects high velocity
        min_sustain_frames=1,       # Instant capture on peak action
        cooldown_base_sec=5.0,      # Shorter cooldown for fast-paced action
        allow_burst=True,
        lookback_seconds=1.5,
        use_pose_model=True
    ),
    "DANCE": EventProfile(
        name="Dance / Garba",
        description="Optimized for spins, group formations, and rapid bursts.",
        engagement_threshold=0.40,
        motion_velocity_threshold=25,
        min_sustain_frames=2,
        cooldown_base_sec=8.0,
        allow_burst=True,
        lookback_seconds=2.0,
        use_pose_model=True
    ),
    "SCHOOL": EventProfile(
        name="School / Playgroup",
        description="Lowered face height constraints and higher candid ratio.",
        engagement_threshold=0.45,
        motion_velocity_threshold=12,
        min_sustain_frames=4,
        cooldown_base_sec=10.0,
        allow_burst=False,
        lookback_seconds=1.0,
        use_pose_model=False
    ),
    "WEDDING": EventProfile(
        name="Wedding Ceremony",
        description="Extremely strict on sustained engagement (ceremonies/handshakes).",
        engagement_threshold=0.60,
        motion_velocity_threshold=10,
        min_sustain_frames=5,       # Must hold pose
        cooldown_base_sec=15.0,
        allow_burst=False,
        lookback_seconds=1.5,
        use_pose_model=True         # Uses pose for handshakes
    )
}

def get_profile(name: str) -> EventProfile:
    return PROFILES.get(name.upper(), PROFILES["DEFAULT"])
