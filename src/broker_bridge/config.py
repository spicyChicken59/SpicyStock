"""Deployment configuration; secrets belong only in the private service."""
from dataclasses import dataclass, field
from decimal import Decimal
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Config:
    origin: str = "https://localhost"
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    encryption_key: str = field(default="", repr=False)
    database: Path = Path("/data/broker.sqlite3")
    docs: Path = Path(__file__).resolve().parents[2] / "docs"
    live_enabled: bool = False
    common_stock_symbols: frozenset = frozenset()
    live_account_ids: frozenset = field(default=frozenset(), repr=False)
    max_positions: int = 5
    max_risk_percent: Decimal = Decimal("1")
    max_position_percent: Decimal = Decimal("25")
    max_notional: Decimal = Decimal("5000")
    max_spread_percent: Decimal = Decimal("1")
    max_limit_deviation_percent: Decimal = Decimal("2")
    session_seconds: int = 28800
    preview_seconds: int = 30

    def __post_init__(self):
        u = urlsplit(self.origin)
        if u.scheme != "https" or not u.netloc or u.path or u.query or u.fragment or u.username:
            raise ValueError("BRIDGE_ORIGIN must be one exact HTTPS origin without a path")
        if self.live_enabled and not self.live_account_ids:
            raise ValueError("Live trading requires an explicit account allowlist")
        for x in (self.max_risk_percent, self.max_position_percent, self.max_notional,
                  self.max_spread_percent, self.max_limit_deviation_percent):
            if not x.is_finite() or x <= 0:
                raise ValueError("Risk limits must be finite positive decimals")
        if isinstance(self.max_positions, bool) or not isinstance(self.max_positions, int) or not 1 <= self.max_positions <= 20:
            raise ValueError("Position cap must be an integer between one and twenty")
        if self.max_risk_percent > 2 or self.max_position_percent > 100:
            raise ValueError("Risk limits exceed bridge safety ceiling")
        if not 1 <= self.preview_seconds <= 30:
            raise ValueError("Preview expiry must be at most 30 seconds")
        if not 60 <= self.session_seconds <= 86400:
            raise ValueError("Session lifetime must be between one minute and one day")
        if self.database.resolve().is_relative_to(self.docs.resolve()):
            raise ValueError("The private database cannot be inside the public docs directory")

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret and self.encryption_key)

    @property
    def redirect_uri(self):
        return self.origin + "/api/oauth/callback"

    @classmethod
    def from_env(cls):
        symbols = os.getenv("BRIDGE_COMMON_STOCK_SYMBOLS")
        if symbols is None:
            path = Path(os.getenv("BRIDGE_COMMON_STOCK_FILE", str(Path(__file__).resolve().parents[2] / "data" / "symbols.txt")))
            try:
                symbols = ",".join(line.split("#", 1)[0].strip() for line in path.read_text().splitlines())
            except OSError:
                symbols = ""
        return cls(
            origin=os.getenv("BRIDGE_ORIGIN", "https://localhost").rstrip("/"),
            client_id=os.getenv("ALPACA_OAUTH_CLIENT_ID", ""),
            client_secret=os.getenv("ALPACA_OAUTH_CLIENT_SECRET", ""),
            encryption_key=os.getenv("BRIDGE_ENCRYPTION_KEY", ""),
            database=Path(os.getenv("BRIDGE_DATABASE", "/data/broker.sqlite3")),
            docs=Path(os.getenv("BRIDGE_DOCS", str(cls.docs))),
            live_enabled=os.getenv("BRIDGE_LIVE_ENABLED", "false").lower() == "true",
            common_stock_symbols=frozenset(x.strip().upper() for x in symbols.split(",") if x.strip()),
            live_account_ids=frozenset(x.strip() for x in os.getenv("BRIDGE_LIVE_ACCOUNT_IDS", "").split(",") if x.strip()),
            max_positions=int(os.getenv("BRIDGE_MAX_POSITIONS", "5")),
            max_risk_percent=Decimal(os.getenv("BRIDGE_MAX_RISK_PERCENT", "1")),
            max_position_percent=Decimal(os.getenv("BRIDGE_MAX_POSITION_PERCENT", "25")),
            max_notional=Decimal(os.getenv("BRIDGE_MAX_NOTIONAL", "5000")),
        )
