from pydantic import BaseModel
from typing import List, Optional

class SuggestionRequest(BaseModel):
    categories: Optional[List[str]] = None  # ['ramp', 'draw', 'removal', 'counter', 'recursion', 'tutor']
    max_cmc: Optional[int] = None
    min_synergy: Optional[float] = 0.5
