from abc import ABC, abstractmethod
from typing import Any, List

from utils.directly_follows_graph import DirectlyFollowsGraph


class BaseCut(ABC):
    def __init__(
        self, name: str, activities: List[str], dfg: DirectlyFollowsGraph
    ) -> None:
        pass

    @abstractmethod
    def discover(self) -> List[Any]:
        pass

    @abstractmethod
    def project(self, trace: List[str], group: set) -> List[str]:
        pass
