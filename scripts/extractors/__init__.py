"""Video transcript extractors."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptResult:
    lines: list[str]
    source_url: str
    title: str = "Video"
    creator: str = "Unknown"
    language: str = "en"
    transcript_source: str = "Unknown"


class TranscriptError(RuntimeError):
    pass


class BaseExtractor(ABC):
    platform_name: str = ""
    supported_hosts: list[str] = []

    @abstractmethod
    def extract(self, url: str) -> TranscriptResult:
        pass

    def can_handle(self, url: str) -> bool:
        return any(host in url.lower() for host in self.supported_hosts)


_extractors: list[type[BaseExtractor]] = []


def register_extractor(cls: type[BaseExtractor]) -> type[BaseExtractor]:
    _extractors.append(cls)
    return cls


def get_extractor(url: str) -> BaseExtractor | None:
    for cls in _extractors:
        extractor = cls()
        if extractor.can_handle(url):
            return extractor
    return None


# Import to register
from . import youtube, bilibili  # noqa: F401, E402
