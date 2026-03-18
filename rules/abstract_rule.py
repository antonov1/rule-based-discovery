from abc import ABC, abstractmethod
from typing import Any, List


class AbstractRule(ABC):
    def __init__(self, activities: List[str]) -> None:
        if len(activities) < 1 or len(activities) > 2:
            raise ValueError("Activities list must contain one or two activities.")
        self.activities = activities
        self.sup = 0
        self.conf = 0

    def __repr__(self) -> str:
        return f"{self.name}({', '.join(self.activities)})"

    @abstractmethod
    def apply(self, data: List[Any]) -> List[Any]:
        pass

    @abstractmethod
    def calc_support(self, data: List[Any]) -> float:
        pass

    @abstractmethod
    def calc_confidence(self, data: List[Any]) -> float:
        pass

    def get_support(self):
        return self.sup

    def get_confidence(self):
        return self.conf
