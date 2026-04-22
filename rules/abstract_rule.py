from abc import ABC, abstractmethod
from typing import Any, List


class AbstractRule(ABC):
    def __init__(self, args: List[str]) -> None:
        if len(args) < 1 or len(args) > 2:
            raise ValueError("Activities list must contain one or two activities.")
        self.args = args
        self.sup = 0
        self.conf = 0

    @property
    def name(self):
        return self.__class__.__name__.replace("Rule", "")

    def __str__(self):
        return f"{self.name}({', '.join(map(str, self.args))})"

    def __repr__(self):
        return self.__str__()

    @abstractmethod
    def apply(self, data: List[Any]) -> List[Any]:
        pass

    @abstractmethod
    def calc_support(self, data: List[Any]) -> float:
        pass

    @abstractmethod
    def calc_confidence(self, data: List[Any]) -> float:
        pass

    @abstractmethod
    def repair(self, data: List[Any]) -> List:
        pass

    def get_support(self):
        return self.sup

    def get_confidence(self):
        return self.conf
