"""Configuration management for Polymarket Whale Tracker."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration."""
    
    # API Keys
    thegraph_api_key: str = ""
    polymarket_api_key: Optional[str] = None
    
    # Database
    database_url: str = "sqlite:///polymarket_tracker.db"
    redis_url: Optional[str] = None
    
    # Notifications
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_bot_token: Optional[str] = None
    discord_channel_id: Optional[str] = None
    
    # Blockchain
    polygon_rpc_url: str = "https://polygon-rpc.com"
    
    # Application
    debug: bool = False
    
    # Subgraph Endpoints
    @property
    def subgraph_positions_url(self) -> str:
        """URL for Positions subgraph."""
        return f"https://gateway.thegraph.com/api/{self.thegraph_api_key}/subgraphs/id/Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp"
    
    @property
    def subgraph_activity_url(self) -> str:
        """URL for Activity subgraph."""
        return f"https://gateway.thegraph.com/api/{self.thegraph_api_key}/subgraphs/id/9AAsF5GbijppB9oC8z37LyBgC7R5fbHRGz5VjG4V4WQp"
    
    @property
    def subgraph_pnl_url(self) -> str:
        """URL for PnL subgraph."""
        return f"https://gateway.thegraph.com/api/{self.thegraph_api_key}/subgraphs/id/7W1hT7fWz2G5e2R1sY3t8u4i6o9p2q5r7s9t1u3v5w7y9z1"
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            thegraph_api_key=os.getenv("THEGRAPH_API_KEY", ""),
            polymarket_api_key=os.getenv("POLYMARKET_API_KEY"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///polymarket_tracker.db"),
            redis_url=os.getenv("REDIS_URL"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            discord_channel_id=os.getenv("DISCORD_CHANNEL_ID"),
            polygon_rpc_url=os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )
