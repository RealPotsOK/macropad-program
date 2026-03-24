from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class ExponentialBackoff:
    """Simple exponential backoff with jitter."""

    initial: float = 1.0
    max_delay: float = 30.0
    factor: float = 2.0
    jitter_low: float = 0.8
    jitter_high: float = 1.2
    random_fn: Callable[[float, float], float] = field(default=random.uniform)
    _attempt: int = field(default=0, init=False, repr=False)
    _base_delay: float = field(default=0.0, init=False, repr=False)

    def next_delay(self) -> float:
        if self._attempt == 0:
            base = min(max(0.0, self.initial), self.max_delay)
        else:
            grown = max(0.0, self._base_delay * self.factor)
            base = min(grown, self.max_delay)
        self._base_delay = base
        self._attempt += 1
        multiplier = self.random_fn(self.jitter_low, self.jitter_high)
        return max(0.0, base * multiplier)

    def reset(self) -> None:
        self._attempt = 0
        self._base_delay = 0.0
