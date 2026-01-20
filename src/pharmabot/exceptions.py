from dataclasses import dataclass


@dataclass
class PharmaBotError(Exception):
    """Base exception for all Pharmabot related errors."""

    message: str

    def __post_init__(self):
        super().__init__(self.message)


class PharmaBotMissingCookieBanner(PharmaBotError):
    """Not finding cookie banner."""

    pass
