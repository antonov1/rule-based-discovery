from typing import List, Any, String, Optional
from abc import ABC, abstractmethod

class AbstractRule(ABC):
    def __init__(self, name: String, activities : List[String]) -> None:
        self.name = name
        if len(activities) < 1 or len(activities) > 2:
            raise ValueError("Activities list must contain one or two activities.")
        self.activities = activities

    def __repr__(self) -> str:
        return f"{self.name}({', '.join(self.activities)})"
    
    @abstractmethod
    def apply(self, data: List[Any]) -> List[Any]:
        pass

    @abstractmethod
    def get_support(self, data: List[Any]) -> float:
        pass

    @abstractmethod
    def get_confidence(self, data: List[Any]) -> float:
        pass

    


 
