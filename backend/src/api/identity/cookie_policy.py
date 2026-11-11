"""HTTP cookie settings supplied by the process host."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrowserCookiePolicy:
    secure: bool
