from abc import ABC, abstractmethod
from typing import Any, List


class AbstractRule(ABC):
    def __init__(self, args: List[str]) -> None:
        if len(args) < 1 or len(args) > 2:
            raise ValueError("Activities list must contain one or two activities.")
        self.args = args
        self.sup = 0
        self.conf = 0

    def set_metrics(
        self,
        *,
        data_len: int,
        valid_traces_len: int,
        support: float,
        confidence: float,
    ) -> None:
        self.data_len = data_len
        self.valid_traces_len = valid_traces_len
        self.sup = support
        self.conf = confidence

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

    @abstractmethod
    def to_automaton(self, alphabet: set) -> Any:
        pass

    def get_support(self):
        return self.sup

    def get_confidence(self):
        return self.conf
