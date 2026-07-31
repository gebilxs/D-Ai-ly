from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Article:
    id: str
    source_id: str
    source_name: str
    title: str
    url: str
    published: str
    summary: str = ""
    fetched_via: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
