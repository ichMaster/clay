"""
Needs: the drives that make the bot want to act.

Each need has a level in [0, 1] where 1 = fully satisfied. Levels decay
every tick. Activities replenish the matching need. The brain reads
`urgency` (1 - level) and acts on whatever is most pressing.

These three generic needs are deliberately a stand-in. When Lili is
plugged in, this maps onto her six canonical NEEDS:

    novelty   -> новизна
    creation  -> творчість
    rest      -> (vitality / a body need; alongside усамітнення, зв'язок,
                 свобода, сенс which the richer world will ground)

The shape stays the same: a dict of named drives with decay + replenish.
Only the names, counts and grounding change.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Need:
    name: str
    level: float = 1.0
    decay: float = 0.004        # lost per tick
    floor: float = 0.0
    ceil: float = 1.0

    def tick(self):
        self.level = max(self.floor, self.level - self.decay)

    def replenish(self, amount: float):
        self.level = min(self.ceil, self.level + amount)

    @property
    def urgency(self) -> float:
        return 1.0 - self.level


@dataclass
class Needs:
    items: dict = field(default_factory=dict)

    @classmethod
    def default(cls) -> "Needs":
        return cls(items={
            "novelty": Need("novelty", decay=0.004),
            "creation": Need("creation", decay=0.003),
            "rest": Need("rest", decay=0.005),
        })

    def tick(self):
        for n in self.items.values():
            n.tick()

    def replenish(self, name: str, amount: float):
        if name in self.items:
            self.items[name].replenish(amount)

    def most_urgent(self):
        return max(self.items.values(), key=lambda n: n.urgency)

    def levels(self) -> dict:
        return {k: round(v.level, 3) for k, v in self.items.items()}

    def urgencies(self) -> dict:
        return {k: round(v.urgency, 3) for k, v in self.items.items()}
