"""
Arbitrage Detection System for Polymarket

Detects and executes arbitrage opportunities across related prediction markets.
Supports multiple arbitrage types with real-time monitoring and risk controls.

Arbitrage Types:
- Complementary: YES on Market A vs NO on complementary Market B
- Parity: Related markets should sum to 1.0
- Temporal: Same market across time (futures vs spot)
- Cross-Exchange: Price differences between venues
- CTF: Conditional token framework mispricings

Example:
    >>> detector = ArbitrageDetector(polymarket_client)
    >>> 
    >>> # Start continuous scanning
    >>> await detector.start_monitoring()
    >>> 
    >>> # Or scan once
    >>> opportunities = await detector.scan_for_arbitrage()
    >>> 
    >>> # Execute an opportunity
    >>> result = await detector.execute_arbitrage(opportunities[0])
"""

import asyncio
import time
import uuid
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Set, Tuple, Union
from enum import Enum, auto
from collections import defaultdict
import json

from ..utils.logger import setup_logging

logger = setup_logging()


# ============================================================================
# Enums
# ============================================================================

class ArbitrageType(Enum):
    """Types of arbitrage opportunities."""
    COMPLEMENTARY = "complementary"  # YES A vs NO B (complementary events)
    PARITY = "parity"                # Related markets should sum to 1.0
    TEMPORAL = "temporal"            # Same market across time
    CROSS_EXCHANGE = "cross_exchange"  # Price differences between venues
    CTF = "ctf"                      # Conditional token framework mispricing
    SUBSET = "subset"                # Subset relationship (e.g., Trump -> Republican)
    SYNTHETIC = "synthetic"          # Synthetic positions via combinations


class ArbitrageStatus(Enum):
    """Status of an arbitrage opportunity."""
    DETECTED = "detected"
    VALIDATING = "validating"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


class ExecutionMode(Enum):
    """Execution mode for arbitrage."""
    SIMULATION = "simulation"        # Paper trading only
    LIVE = "live"                    # Live execution
    HYBRID = "hybrid"                # Simulated validation, then live


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ArbitrageLeg:
    """
    Represents one leg of an arbitrage trade.
    
    Attributes:
        market_id: Polymarket market ID
        token_id: Token ID for the outcome
        side: 'buy' or 'sell'
        size: Position size in shares
        expected_price: Expected execution price
        outcome: Market outcome (e.g., 'YES', 'NO')
    """
    market_id: str
    side: str  # 'buy' or 'sell'
    size: float
    expected_price: float
    token_id: Optional[str] = None
    outcome: str = "YES"
    
    def __post_init__(self):
        self.side = self.side.lower()
        self.outcome = self.outcome.upper()
    
    @property
    def notional(self) -> float:
        """Calculate notional value of the leg."""
        return self.size * self.expected_price
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'market_id': self.market_id,
            'token_id': self.token_id,
            'side': self.side,
            'size': self.size,
            'expected_price': self.expected_price,
            'outcome': self.outcome,
            'notional': self.notional,
        }


@dataclass
class ArbitrageOpportunity:
    """
    Represents an arbitrage opportunity between related markets.
    
    Attributes:
        opportunity_id: Unique identifier
        market_a: First market identifier
        market_b: Second market identifier (if applicable)
        arb_type: Type of arbitrage
        legs: List of trade legs
        profit_percent: Expected profit percentage
        confidence: Confidence score (0.0 to 1.0)
        detected_at: Detection timestamp
        expires_at: Expiration timestamp
        status: Current status
        metadata: Additional opportunity data
    """
    opportunity_id: str
    market_a: str
    market_b: Optional[str]
    arb_type: ArbitrageType
    legs: List[ArbitrageLeg]
    profit_percent: float
    confidence: float
    detected_at: datetime
    expires_at: datetime
    status: ArbitrageStatus = ArbitrageStatus.DETECTED
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.opportunity_id:
            self.opportunity_id = f"arb_{uuid.uuid4().hex[:12]}"
    
    @property
    def total_investment(self) -> float:
        """Calculate total capital required."""
        return sum(leg.notional for leg in self.legs if leg.side == 'buy')
    
    @property
    def expected_profit(self) -> float:
        """Calculate expected profit in dollars."""
        return self.total_investment * (self.profit_percent / 100)
    
    @property
    def is_expired(self) -> bool:
        """Check if opportunity has expired."""
        return datetime.now() > self.expires_at
    
    @property
    def time_to_expiry_seconds(self) -> float:
        """Get seconds until expiry."""
        return max(0, (self.expires_at - datetime.now()).total_seconds())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'opportunity_id': self.opportunity_id,
            'market_a': self.market_a,
            'market_b': self.market_b,
            'arb_type': self.arb_type.value,
            'legs': [leg.to_dict() for leg in self.legs],
            'profit_percent': round(self.profit_percent, 4),
            'expected_profit': round(self.expected_profit, 4),
            'total_investment': round(self.total_investment, 4),
            'confidence': round(self.confidence, 4),
            'detected_at': self.detected_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'status': self.status.value,
            'metadata': self.metadata,
        }


@dataclass
class ArbitrageResult:
    """
    Result of an arbitrage execution.
    
    Attributes:
        opportunity_id: ID of the executed opportunity
        success: Whether execution was successful
        profit_actual: Actual profit realized
        execution_time_ms: Time to execute in milliseconds
        leg_results: Results for each leg
        error: Error message if failed
        executed_at: Execution timestamp
    """
    opportunity_id: str
    success: bool
    profit_actual: float = 0.0
    execution_time_ms: float = 0.0
    leg_results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'opportunity_id': self.opportunity_id,
            'success': self.success,
            'profit_actual': round(self.profit_actual, 4),
            'execution_time_ms': round(self.execution_time_ms, 2),
            'leg_results': self.leg_results,
            'error': self.error,
            'executed_at': self.executed_at.isoformat(),
        }


@dataclass
class ArbitrageStats:
    """
    Statistics for arbitrage detection and execution.
    
    Attributes:
        opportunities_found: Total opportunities detected
        opportunities_executed: Number of executed opportunities
        opportunities_expired: Number that expired before execution
        total_profit: Total profit realized
        avg_profit_percent: Average profit percentage
        success_rate: Percentage of successful executions
        avg_execution_time_ms: Average execution time
        by_type: Statistics broken down by arbitrage type
    """
    opportunities_found: int = 0
    opportunities_executed: int = 0
    opportunities_failed: int = 0
    opportunities_expired: int = 0
    total_profit: float = 0.0
    total_fees: float = 0.0
    avg_profit_percent: float = 0.0
    success_rate: float = 0.0
    avg_execution_time_ms: float = 0.0
    by_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Internal tracking
    _profits: List[float] = field(default_factory=list, repr=False)
    _execution_times: List[float] = field(default_factory=list, repr=False)
    
    def record_opportunity(self, arb_type: ArbitrageType):
        """Record a detected opportunity."""
        self.opportunities_found += 1
        type_key = arb_type.value
        if type_key not in self.by_type:
            self.by_type[type_key] = {'found': 0, 'executed': 0, 'failed': 0}
        self.by_type[type_key]['found'] += 1
    
    def record_execution(self, result: ArbitrageResult, arb_type: ArbitrageType):
        """Record an execution result."""
        type_key = arb_type.value
        
        if result.success:
            self.opportunities_executed += 1
            self.total_profit += result.profit_actual
            self._profits.append(result.profit_actual)
            if type_key in self.by_type:
                self.by_type[type_key]['executed'] += 1
        else:
            self.opportunities_failed += 1
            if type_key in self.by_type:
                self.by_type[type_key]['failed'] += 1
        
        self._execution_times.append(result.execution_time_ms)
        
        # Update averages
        total_attempted = self.opportunities_executed + self.opportunities_failed
        if total_attempted > 0:
            self.success_rate = self.opportunities_executed / total_attempted
        
        if self._profits:
            self.avg_profit_percent = sum(self._profits) / len(self._profits)
        
        if self._execution_times:
            self.avg_execution_time_ms = sum(self._execution_times) / len(self._execution_times)
    
    def record_expired(self):
        """Record an expired opportunity."""
        self.opportunities_expired += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'opportunities_found': self.opportunities_found,
            'opportunities_executed': self.opportunities_executed,
            'opportunities_failed': self.opportunities_failed,
            'opportunities_expired': self.opportunities_expired,
            'total_profit': round(self.total_profit, 4),
            'total_fees': round(self.total_fees, 4),
            'net_profit': round(self.total_profit - self.total_fees, 4),
            'avg_profit_percent': round(self.avg_profit_percent, 4),
            'success_rate': round(self.success_rate, 4),
            'avg_execution_time_ms': round(self.avg_execution_time_ms, 2),
            'by_type': self.by_type,
        }


@dataclass
class MarketRelationship:
    """
    Represents a relationship between two markets for arbitrage detection.
    
    Attributes:
        market_a: First market ID
        market_b: Second market ID
        relationship_type: Type of relationship
        correlation: Expected price correlation (-1 to 1)
        description: Human-readable description
    """
    market_a: str
    market_b: str
    relationship_type: str  # 'complement', 'subset', 'equivalent', 'synthetic'
    correlation: float  # -1 = inverse, 0 = independent, 1 = identical
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'market_a': self.market_a,
            'market_b': self.market_b,
            'relationship_type': self.relationship_type,
            'correlation': self.correlation,
            'description': self.description,
        }


# ============================================================================
# Main Arbitrage Detector Class
# ============================================================================

class ArbitrageDetector:
    """
    Detects and executes arbitrage opportunities across Polymarket markets.
    
    Features:
    - Real-time opportunity scanning via WebSocket
    - Multiple arbitrage type detection
    - Risk-aware execution with atomic orders
    - Profit estimation with fees and gas costs
    - Comprehensive statistics tracking
    
    Example:
        >>> detector = ArbitrageDetector(polymarket_client)
        >>> 
        >>> # Register callback for opportunities
        >>> @detector.on_opportunity
        ... def handle_opportunity(opp):
        ...     print(f"Found: {opp.profit_percent:.2%} profit")
        >>> 
        >>> # Start monitoring
        >>> await detector.start_monitoring()
    """
    
    # Configuration defaults
    DEFAULT_MIN_PROFIT_PERCENT = 2.0  # Minimum 2% profit after fees
    DEFAULT_MAX_EXECUTION_TIME_MS = 5000  # 5 seconds max to execute
    DEFAULT_OPPORTUNITY_TTL_SECONDS = 30  # Opportunities expire in 30s
    DEFAULT_SCAN_INTERVAL_SECONDS = 1.0
    
    # Fee structure (Polymarket)
    DEFAULT_TAKER_FEE = 0.002  # 0.2% taker fee
    DEFAULT_GAS_COST_USD = 0.50  # Estimated gas cost in USD
    
    def __init__(
        self,
        polymarket_client: Optional[Any] = None,
        min_profit_percent: float = DEFAULT_MIN_PROFIT_PERCENT,
        max_execution_time_ms: float = DEFAULT_MAX_EXECUTION_TIME_MS,
        opportunity_ttl_seconds: float = DEFAULT_OPPORTUNITY_TTL_SECONDS,
        scan_interval_seconds: float = DEFAULT_SCAN_INTERVAL_SECONDS,
        execution_mode: ExecutionMode = ExecutionMode.SIMULATION,
        enable_websocket: bool = True,
    ):
        """
        Initialize the arbitrage detector.
        
        Args:
            polymarket_client: Polymarket API client instance
            min_profit_percent: Minimum profit threshold after fees
            max_execution_time_ms: Maximum time allowed for execution
            opportunity_ttl_seconds: How long opportunities remain valid
            scan_interval_seconds: Interval between scans
            execution_mode: Simulation, live, or hybrid mode
            enable_websocket: Whether to use WebSocket for real-time data
        """
        self.client = polymarket_client
        self.min_profit_percent = min_profit_percent
        self.max_execution_time_ms = max_execution_time_ms
        self.opportunity_ttl_seconds = opportunity_ttl_seconds
        self.scan_interval_seconds = scan_interval_seconds
        self.execution_mode = execution_mode
        self.enable_websocket = enable_websocket
        
        # Market data cache
        self._market_data: Dict[str, Dict[str, Any]] = {}
        self._orderbooks: Dict[str, Dict[str, Any]] = {}
        self._market_relationships: List[MarketRelationship] = []
        
        # Active opportunities
        self._active_opportunities: Dict[str, ArbitrageOpportunity] = {}
        self._opportunity_history: List[ArbitrageOpportunity] = []
        
        # Statistics
        self.stats = ArbitrageStats()
        
        # Callbacks
        self._opportunity_callbacks: List[Callable[[ArbitrageOpportunity], None]] = []
        self._execution_callbacks: List[Callable[[ArbitrageResult], None]] = []
        
        # WebSocket client
        self._websocket_client: Optional[Any] = None
        
        # Background tasks
        self._scan_task: Optional[asyncio.Task] = None
        self._running = False
        self._stop_event = asyncio.Event()
        
        # Risk controls
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 3
        self._circuit_breaker_open = False
        self._max_daily_loss = 100.0  # USD
        self._daily_pnl = 0.0
        
        # Load known relationships
        self._load_market_relationships()
        
        logger.info(
            f"ArbitrageDetector initialized: min_profit={min_profit_percent}%, "
            f"mode={execution_mode.value}, websocket={enable_websocket}"
        )
    
    def _load_market_relationships(self):
        """Load known market relationships for arbitrage detection."""
        # These would typically be loaded from a database or config
        # For now, we'll define some common patterns
        self._relationship_patterns = [
            # Complementary patterns (mutually exclusive outcomes)
            {
                'type': 'complement',
                'pattern_a': r'Will (\w+) close above \$([\d,]+)',
                'pattern_b': r'Will \1 close below \$\2',
                'description': 'Above/Below price levels'
            },
            {
                'type': 'complement',
                'pattern_a': r'Will (\w+) end higher',
                'pattern_b': r'Will \1 end lower',
                'description': 'Higher/Lower outcomes'
            },
            # Subset patterns
            {
                'type': 'subset',
                'pattern_a': r'Will (\w+) win',
                'pattern_b': r'Will (\w+) party win',
                'description': 'Candidate vs Party win'
            },
        ]
    
    # ========================================================================
    # Opportunity Detection
    # ========================================================================
    
    async def scan_for_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Scan for arbitrage opportunities across all tracked markets.
        
        Returns:
            List of detected arbitrage opportunities
        """
        opportunities = []
        
        try:
            # Update market data
            await self._update_market_data()
            
            # Check complementary arbitrage
            comp_opps = await self._scan_complementary()
            opportunities.extend(comp_opps)
            
            # Check parity arbitrage
            parity_opps = await self._scan_parity()
            opportunities.extend(parity_opps)
            
            # Check subset relationships
            subset_opps = await self._scan_subset_relationships()
            opportunities.extend(subset_opps)
            
            # Check CTF mispricings
            ctf_opps = await self._scan_ctf_mispricings()
            opportunities.extend(ctf_opps)
            
            # Filter and validate
            valid_opps = self._validate_opportunities(opportunities)
            
            # Store active opportunities
            for opp in valid_opps:
                self._active_opportunities[opp.opportunity_id] = opp
                self.stats.record_opportunity(opp.arb_type)
                
                # Notify callbacks
                self._notify_opportunity(opp)
            
            logger.debug(f"Scan complete: {len(valid_opps)} opportunities found")
            return valid_opps
            
        except Exception as e:
            logger.error(f"Error scanning for arbitrage: {e}")
            return []
    
    async def _scan_complementary(self) -> List[ArbitrageOpportunity]:
        """Scan for complementary arbitrage opportunities."""
        opportunities = []
        markets = list(self._market_data.values())
        
        for i, market_a in enumerate(markets):
            for market_b in markets[i+1:]:
                # Check if markets are complementary
                if self._are_complementary(market_a, market_b):
                    opp = self._check_complementary_arbitrage(market_a, market_b)
                    if opp:
                        opportunities.append(opp)
        
        return opportunities
    
    def _are_complementary(self, market_a: Dict, market_b: Dict) -> bool:
        """Check if two markets are complementary (mutually exclusive)."""
        # Check if they represent the same event with opposite outcomes
        question_a = market_a.get('question', '').lower()
        question_b = market_b.get('question', '').lower()
        
        # Common complementary patterns
        patterns = [
            ('above', 'below'),
            ('higher', 'lower'),
            ('over', 'under'),
            ('more than', 'less than'),
            ('increase', 'decrease'),
            ('bullish', 'bearish'),
        ]
        
        # Check if questions are similar but with opposite keywords
        for pos, neg in patterns:
            if pos in question_a and neg in question_b:
                # Check if rest of question is similar
                base_a = question_a.replace(pos, '').strip()
                base_b = question_b.replace(neg, '').strip()
                if self._string_similarity(base_a, base_b) > 0.7:
                    return True
        
        return False
    
    def _check_complementary_arbitrage(
        self, 
        market_a: Dict, 
        market_b: Dict
    ) -> Optional[ArbitrageOpportunity]:
        """Check for arbitrage between complementary markets."""
        try:
            # Get prices
            yes_a = self._get_best_price(market_a['id'], 'YES', 'buy')
            no_a = self._get_best_price(market_a['id'], 'NO', 'buy')
            yes_b = self._get_best_price(market_b['id'], 'YES', 'buy')
            no_b = self._get_best_price(market_b['id'], 'NO', 'buy')
            
            if not all([yes_a, no_a, yes_b, no_b]):
                return None
            
            # Strategy 1: Buy YES on A + Buy NO on B (should sum to ~1.0)
            # If sum < 1.0, there's an arbitrage
            sum_price = yes_a + no_b
            if sum_price < 0.99:  # Allow for small rounding
                profit = 1.0 - sum_price
                profit_percent = profit * 100
                
                if profit_percent > self.min_profit_percent:
                    legs = [
                        ArbitrageLeg(
                            market_id=market_a['id'],
                            side='buy',
                            size=100.0,
                            expected_price=yes_a,
                            outcome='YES'
                        ),
                        ArbitrageLeg(
                            market_id=market_b['id'],
                            side='buy',
                            size=100.0,
                            expected_price=no_b,
                            outcome='NO'
                        )
                    ]
                    
                    return ArbitrageOpportunity(
                        opportunity_id=f"comp_{uuid.uuid4().hex[:12]}",
                        market_a=market_a['id'],
                        market_b=market_b['id'],
                        arb_type=ArbitrageType.COMPLEMENTARY,
                        legs=legs,
                        profit_percent=profit_percent,
                        confidence=0.8,
                        detected_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(seconds=self.opportunity_ttl_seconds),
                        metadata={
                            'strategy': 'buy_yes_a_buy_no_b',
                            'sum_price': sum_price,
                            'market_a_question': market_a.get('question'),
                            'market_b_question': market_b.get('question'),
                        }
                    )
            
            # Strategy 2: Buy NO on A + Buy YES on B
            sum_price = no_a + yes_b
            if sum_price < 0.99:
                profit = 1.0 - sum_price
                profit_percent = profit * 100
                
                if profit_percent > self.min_profit_percent:
                    legs = [
                        ArbitrageLeg(
                            market_id=market_a['id'],
                            side='buy',
                            size=100.0,
                            expected_price=no_a,
                            outcome='NO'
                        ),
                        ArbitrageLeg(
                            market_id=market_b['id'],
                            side='buy',
                            size=100.0,
                            expected_price=yes_b,
                            outcome='YES'
                        )
                    ]
                    
                    return ArbitrageOpportunity(
                        opportunity_id=f"comp_{uuid.uuid4().hex[:12]}",
                        market_a=market_a['id'],
                        market_b=market_b['id'],
                        arb_type=ArbitrageType.COMPLEMENTARY,
                        legs=legs,
                        profit_percent=profit_percent,
                        confidence=0.8,
                        detected_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(seconds=self.opportunity_ttl_seconds),
                        metadata={
                            'strategy': 'buy_no_a_buy_yes_b',
                            'sum_price': sum_price,
                        }
                    )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking complementary arbitrage: {e}")
            return None
    
    async def _scan_parity(self) -> List[ArbitrageOpportunity]:
        """Scan for parity arbitrage (YES + NO should = 1.0 in same market)."""
        opportunities = []
        
        for market in self._market_data.values():
            opp = self._check_parity_arbitrage(market)
            if opp:
                opportunities.append(opp)
        
        return opportunities
    
    def _check_parity_arbitrage(self, market: Dict) -> Optional[ArbitrageOpportunity]:
        """Check for parity arbitrage within a single market."""
        try:
            yes_buy = self._get_best_price(market['id'], 'YES', 'buy')
            no_buy = self._get_best_price(market['id'], 'NO', 'buy')
            
            if not yes_buy or not no_buy:
                return None
            
            # YES + NO should equal 1.0
            sum_price = yes_buy + no_buy
            
            # If sum < 1.0, buy both for guaranteed profit
            if sum_price < 0.99:
                profit = 1.0 - sum_price
                profit_percent = profit * 100
                
                if profit_percent > self.min_profit_percent:
                    legs = [
                        ArbitrageLeg(
                            market_id=market['id'],
                            side='buy',
                            size=100.0,
                            expected_price=yes_buy,
                            outcome='YES'
                        ),
                        ArbitrageLeg(
                            market_id=market['id'],
                            side='buy',
                            size=100.0,
                            expected_price=no_buy,
                            outcome='NO'
                        )
                    ]
                    
                    return ArbitrageOpportunity(
                        opportunity_id=f"par_{uuid.uuid4().hex[:12]}",
                        market_a=market['id'],
                        market_b=None,
                        arb_type=ArbitrageType.PARITY,
                        legs=legs,
                        profit_percent=profit_percent,
                        confidence=0.95,  # High confidence - mathematical certainty
                        detected_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(seconds=self.opportunity_ttl_seconds),
                        metadata={
                            'sum_price': sum_price,
                            'question': market.get('question'),
                        }
                    )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking parity arbitrage: {e}")
            return None
    
    async def _scan_subset_relationships(self) -> List[ArbitrageOpportunity]:
        """Scan for subset relationship arbitrage (e.g., Trump win vs Republican win)."""
        opportunities = []
        
        # Example: Trump win is a subset of Republican win
        # If Trump wins, Republican must win
        # Therefore: P(Republican) >= P(Trump)
        # If P(Trump) > P(Republican), arbitrage exists
        
        subset_pairs = self._find_subset_pairs()
        
        for subset_market, superset_market in subset_pairs:
            opp = self._check_subset_arbitrage(subset_market, superset_market)
            if opp:
                opportunities.append(opp)
        
        return opportunities
    
    def _find_subset_pairs(self) -> List[Tuple[Dict, Dict]]:
        """Find pairs of markets with subset relationships."""
        pairs = []
        markets = list(self._market_data.values())
        
        for market_a in markets:
            question_a = market_a.get('question', '').lower()
            
            for market_b in markets:
                if market_a['id'] == market_b['id']:
                    continue
                
                question_b = market_b.get('question', '').lower()
                
                # Check for subset patterns
                # Example: "Will Trump win?" is subset of "Will Republican win?"
                if self._is_subset_relationship(question_a, question_b):
                    pairs.append((market_a, market_b))
        
        return pairs
    
    def _is_subset_relationship(self, question_a: str, question_b: str) -> bool:
        """Check if question_a implies question_b (subset relationship)."""
        # Trump -> Republican
        if 'trump' in question_a and 'republican' in question_b and 'win' in question_a:
            return True
        
        # Biden -> Democrat
        if 'biden' in question_a and 'democrat' in question_b and 'win' in question_a:
            return True
        
        # Individual team -> League champion
        # Specific outcome -> Broader category
        
        return False
    
    def _check_subset_arbitrage(
        self, 
        subset_market: Dict, 
        superset_market: Dict
    ) -> Optional[ArbitrageOpportunity]:
        """Check for arbitrage in subset relationship."""
        try:
            # Get YES prices
            subset_yes = self._get_best_price(subset_market['id'], 'YES', 'buy')
            superset_yes = self._get_best_price(superset_market['id'], 'YES', 'sell')
            
            if not subset_yes or not superset_yes:
                return None
            
            # If subset YES price > superset YES price, arbitrage exists
            # Buy superset, sell subset
            if subset_yes > superset_yes * 1.02:  # 2% threshold
                profit = subset_yes - superset_yes
                profit_percent = (profit / superset_yes) * 100
                
                if profit_percent > self.min_profit_percent:
                    legs = [
                        ArbitrageLeg(
                            market_id=superset_market['id'],
                            side='buy',
                            size=100.0,
                            expected_price=superset_yes,
                            outcome='YES'
                        ),
                        ArbitrageLeg(
                            market_id=subset_market['id'],
                            side='sell',
                            size=100.0,
                            expected_price=subset_yes,
                            outcome='YES'
                        )
                    ]
                    
                    return ArbitrageOpportunity(
                        opportunity_id=f"sub_{uuid.uuid4().hex[:12]}",
                        market_a=subset_market['id'],
                        market_b=superset_market['id'],
                        arb_type=ArbitrageType.SUBSET,
                        legs=legs,
                        profit_percent=profit_percent,
                        confidence=0.75,
                        detected_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(seconds=self.opportunity_ttl_seconds),
                        metadata={
                            'subset_question': subset_market.get('question'),
                            'superset_question': superset_market.get('question'),
                            'relationship': f"{subset_market.get('question')} ⊆ {superset_market.get('question')}",
                        }
                    )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking subset arbitrage: {e}")
            return None
    
    async def _scan_ctf_mispricings(self) -> List[ArbitrageOpportunity]:
        """Scan for Conditional Token Framework mispricings."""
        opportunities = []
        
        # CTF allows creating synthetic positions
        # Example: In categorical markets, sum of all outcomes should = 1.0
        
        # Group markets by event
        event_groups = self._group_by_event()
        
        for event_id, markets in event_groups.items():
            if len(markets) > 2:  # Categorical market
                opp = self._check_categorical_arbitrage(markets)
                if opp:
                    opportunities.append(opp)
        
        return opportunities
    
    def _group_by_event(self) -> Dict[str, List[Dict]]:
        """Group markets by underlying event."""
        groups = defaultdict(list)
        
        for market in self._market_data.values():
            # Use event identifier (could be from description, tags, etc.)
            event_id = market.get('event_id') or market.get('slug', '')
            groups[event_id].append(market)
        
        return dict(groups)
    
    def _check_categorical_arbitrage(self, markets: List[Dict]) -> Optional[ArbitrageOpportunity]:
        """Check for arbitrage in categorical markets."""
        try:
            # Sum of all YES prices should be close to 1.0
            total_price = 0.0
            prices = []
            
            for market in markets:
                price = self._get_best_price(market['id'], 'YES', 'buy')
                if price:
                    total_price += price
                    prices.append((market, price))
            
            if total_price < 0.99:
                # Buy all outcomes for guaranteed profit
                profit = 1.0 - total_price
                profit_percent = profit * 100
                
                if profit_percent > self.min_profit_percent:
                    legs = [
                        ArbitrageLeg(
                            market_id=m['id'],
                            side='buy',
                            size=100.0,
                            expected_price=p,
                            outcome='YES'
                        )
                        for m, p in prices
                    ]
                    
                    return ArbitrageOpportunity(
                        opportunity_id=f"ctf_{uuid.uuid4().hex[:12]}",
                        market_a=markets[0]['id'],
                        market_b=None,
                        arb_type=ArbitrageType.CTF,
                        legs=legs,
                        profit_percent=profit_percent,
                        confidence=0.9,
                        detected_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(seconds=self.opportunity_ttl_seconds),
                        metadata={
                            'num_outcomes': len(prices),
                            'total_price': total_price,
                            'event': markets[0].get('question'),
                        }
                    )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking categorical arbitrage: {e}")
            return None
    
    def _validate_opportunities(
        self, 
        opportunities: List[ArbitrageOpportunity]
    ) -> List[ArbitrageOpportunity]:
        """Filter and validate opportunities."""
        valid = []
        
        for opp in opportunities:
            # Check minimum profit
            if opp.profit_percent < self.min_profit_percent:
                continue
            
            # Check confidence threshold
            if opp.confidence < 0.5:
                continue
            
            # Estimate real profit after fees
            profit_after_fees = self.estimate_arbitrage_profit(opp)
            if profit_after_fees['net_profit_percent'] < self.min_profit_percent:
                continue
            
            # Check liquidity
            if not self._check_liquidity(opp):
                continue
            
            # Update with accurate profit estimate
            opp.profit_percent = profit_after_fees['net_profit_percent']
            opp.metadata['profit_breakdown'] = profit_after_fees
            
            valid.append(opp)
        
        # Sort by expected profit
        valid.sort(key=lambda x: x.profit_percent, reverse=True)
        
        return valid
    
    def _check_liquidity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Check if there's sufficient liquidity for execution."""
        for leg in opportunity.legs:
            # Check orderbook depth
            orderbook = self._orderbooks.get(leg.market_id)
            if orderbook:
                # Get depth at the expected price
                depth = self._get_depth_at_price(orderbook, leg.side, leg.expected_price)
                if depth < leg.size:
                    logger.debug(f"Insufficient liquidity for {leg.market_id}: {depth} < {leg.size}")
                    return False
        
        return True
    
    def _get_depth_at_price(
        self, 
        orderbook: Dict, 
        side: str, 
        price: float
    ) -> float:
        """Get available depth at or better than given price."""
        depth = 0.0
        
        if side == 'buy':
            # Looking at asks (selling to us)
            for level in orderbook.get('asks', []):
                if level['price'] <= price:
                    depth += level['size']
        else:
            # Looking at bids (buying from us)
            for level in orderbook.get('bids', []):
                if level['price'] >= price:
                    depth += level['size']
        
        return depth
    
    # ========================================================================
    # Price and Probability Calculations
    # ========================================================================
    
    def calculate_implied_probabilities(self, market_id: str) -> Dict[str, float]:
        """
        Calculate fair value probabilities for a market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            Dictionary with implied probabilities
        """
        market = self._market_data.get(market_id)
        if not market:
            return {}
        
        yes_price = self._get_best_price(market_id, 'YES', 'buy')
        no_price = self._get_best_price(market_id, 'NO', 'buy')
        
        if not yes_price or not no_price:
            return {}
        
        # Midpoint as best estimate
        implied_yes = yes_price
        implied_no = no_price
        
        # Normalize to ensure they sum to 1.0
        total = implied_yes + implied_no
        if total > 0:
            implied_yes /= total
            implied_no /= total
        
        return {
            'YES': implied_yes,
            'NO': implied_no,
            'spread': 1.0 - (yes_price + no_price),
            'confidence': 1.0 - abs(yes_price + no_price - 1.0),
        }
    
    def find_price_divergence(
        self, 
        market_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find price divergences between related markets.
        
        Args:
            market_ids: List of market IDs to compare
            
        Returns:
            List of divergence findings
        """
        divergences = []
        
        for i, market_a in enumerate(market_ids):
            for market_b in market_ids[i+1:]:
                # Compare implied probabilities
                probs_a = self.calculate_implied_probabilities(market_a)
                probs_b = self.calculate_implied_probabilities(market_b)
                
                if not probs_a or not probs_b:
                    continue
                
                # Calculate divergence
                divergence = abs(probs_a.get('YES', 0) - probs_b.get('YES', 0))
                
                if divergence > 0.05:  # 5% threshold
                    divergences.append({
                        'market_a': market_a,
                        'market_b': market_b,
                        'divergence': divergence,
                        'price_a': probs_a.get('YES', 0),
                        'price_b': probs_b.get('YES', 0),
                    })
        
        return sorted(divergences, key=lambda x: x['divergence'], reverse=True)
    
    def estimate_arbitrage_profit(
        self, 
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, float]:
        """
        Estimate arbitrage profit after all costs.
        
        Args:
            opportunity: Arbitrage opportunity to analyze
            
        Returns:
            Dictionary with profit breakdown
        """
        gross_profit = opportunity.expected_profit
        total_investment = opportunity.total_investment
        
        # Calculate fees
        taker_fees = 0.0
        for leg in opportunity.legs:
            notional = leg.notional
            # Taker fee on each leg
            taker_fees += notional * self.DEFAULT_TAKER_FEE
        
        # Gas costs (estimated)
        gas_cost = self.DEFAULT_GAS_COST_USD
        
        # Total costs
        total_costs = taker_fees + gas_cost
        
        # Net profit
        net_profit = gross_profit - total_costs
        net_profit_percent = (net_profit / total_investment * 100) if total_investment > 0 else 0
        
        return {
            'gross_profit': round(gross_profit, 4),
            'taker_fees': round(taker_fees, 4),
            'gas_cost': round(gas_cost, 4),
            'total_costs': round(total_costs, 4),
            'net_profit': round(net_profit, 4),
            'net_profit_percent': round(net_profit_percent, 4),
            'roi': round(net_profit / total_investment, 4) if total_investment > 0 else 0,
        }
    
    # ========================================================================
    # Execution
    # ========================================================================
    
    async def execute_arbitrage(
        self, 
        opportunity: ArbitrageOpportunity
    ) -> ArbitrageResult:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Arbitrage opportunity to execute
            
        Returns:
            Execution result
        """
        start_time = time.perf_counter()
        opportunity.status = ArbitrageStatus.EXECUTING
        
        try:
            # Pre-execution checks
            if not await self._pre_execution_check(opportunity):
                return ArbitrageResult(
                    opportunity_id=opportunity.opportunity_id,
                    success=False,
                    error="Pre-execution checks failed",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000
                )
            
            # Calculate hedge ratios
            hedge_ratios = self.hedge_ratio_calculation(opportunity)
            
            # Adjust leg sizes based on hedge ratios
            for i, leg in enumerate(opportunity.legs):
                if i < len(hedge_ratios):
                    leg.size = leg.size * hedge_ratios[i]
            
            # Execute atomically (all legs or none)
            if self.execution_mode == ExecutionMode.SIMULATION:
                result = await self._simulate_execution(opportunity)
            else:
                result = await self.atomic_execution(opportunity)
            
            # Update opportunity status
            if result.success:
                opportunity.status = ArbitrageStatus.EXECUTED
                await self._profit_locking(opportunity, result)
            else:
                opportunity.status = ArbitrageStatus.FAILED
                self._circuit_breaker_failures += 1
            
            # Update statistics
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            result.execution_time_ms = execution_time_ms
            self.stats.record_execution(result, opportunity.arb_type)
            
            # Notify callbacks
            self._notify_execution(result)
            
            return result
            
        except Exception as e:
            opportunity.status = ArbitrageStatus.FAILED
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            result = ArbitrageResult(
                opportunity_id=opportunity.opportunity_id,
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms
            )
            
            self.stats.record_execution(result, opportunity.arb_type)
            return result
    
    async def _pre_execution_check(self, opportunity: ArbitrageOpportunity) -> bool:
        """Perform pre-execution validation checks."""
        # Check circuit breaker
        if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
            logger.warning("Circuit breaker active - skipping execution")
            return False
        
        # Check daily loss limit
        if self._daily_pnl < -self._max_daily_loss:
            logger.warning("Daily loss limit reached - skipping execution")
            return False
        
        # Verify opportunity not expired
        if opportunity.is_expired:
            logger.debug("Opportunity expired")
            return False
        
        # Re-verify prices
        for leg in opportunity.legs:
            current_price = self._get_best_price(leg.market_id, leg.outcome, leg.side)
            if current_price:
                price_slippage = abs(current_price - leg.expected_price) / leg.expected_price
                if price_slippage > 0.01:  # 1% slippage tolerance
                    logger.warning(f"Price slippage too high: {price_slippage:.2%}")
                    return False
        
        return True
    
    def hedge_ratio_calculation(self, opportunity: ArbitrageOpportunity) -> List[float]:
        """
        Calculate proper position sizes (hedge ratios) for each leg.
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            List of hedge ratios for each leg
        """
        if opportunity.arb_type == ArbitrageType.COMPLEMENTARY:
            # Equal sizing for complementary
            return [1.0] * len(opportunity.legs)
        
        elif opportunity.arb_type == ArbitrageType.PARITY:
            # Equal sizing for parity
            return [1.0] * len(opportunity.legs)
        
        elif opportunity.arb_type == ArbitrageType.SUBSET:
            # Adjust for payout differences
            # If subset pays more when it wins, size down
            ratios = []
            for leg in opportunity.legs:
                if leg.side == 'buy':
                    ratios.append(1.0)
                else:
                    # Short position - adjust for risk
                    ratios.append(0.9)  # Slightly smaller short
            return ratios
        
        else:
            # Default: equal sizing
            return [1.0] * len(opportunity.legs)
    
    async def atomic_execution(
        self, 
        opportunity: ArbitrageOpportunity
    ) -> ArbitrageResult:
        """
        Execute all legs atomically (all or none).
        
        In a real implementation, this would use a smart contract
        or other atomic execution mechanism.
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            Execution result
        """
        leg_results = []
        all_success = True
        total_profit = 0.0
        
        # Execute all legs in parallel
        tasks = []
        for leg in opportunity.legs:
            task = self._execute_leg(leg)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                leg_results.append({
                    'leg': i,
                    'success': False,
                    'error': str(result)
                })
                all_success = False
            else:
                leg_results.append(result)
                if not result.get('success', False):
                    all_success = False
                else:
                    # Calculate leg P&L
                    pnl = result.get('realized_pnl', 0)
                    total_profit += pnl
        
        # If any leg failed, attempt to unwind successful ones
        if not all_success:
            await self._unwind_partial_execution(opportunity, leg_results)
            return ArbitrageResult(
                opportunity_id=opportunity.opportunity_id,
                success=False,
                error="Partial execution - unwound",
                leg_results=leg_results
            )
        
        return ArbitrageResult(
            opportunity_id=opportunity.opportunity_id,
            success=True,
            profit_actual=total_profit,
            leg_results=leg_results
        )
    
    async def _execute_leg(self, leg: ArbitrageLeg) -> Dict[str, Any]:
        """Execute a single arbitrage leg."""
        # In a real implementation, this would call the Polymarket API
        # For now, we simulate
        
        if self.client:
            try:
                # Place order through client
                order_result = await self._place_order(
                    market_id=leg.market_id,
                    side=leg.side,
                    size=leg.size,
                    price=leg.expected_price,
                    outcome=leg.outcome
                )
                return {
                    'success': order_result.get('success', False),
                    'market_id': leg.market_id,
                    'side': leg.side,
                    'size': leg.size,
                    'price': leg.expected_price,
                    'order_id': order_result.get('order_id'),
                    'realized_pnl': 0,  # Would calculate actual P&L
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        else:
            # Simulation mode
            await asyncio.sleep(0.01)  # Simulate latency
            return {
                'success': True,
                'market_id': leg.market_id,
                'side': leg.side,
                'size': leg.size,
                'price': leg.expected_price,
                'simulated': True,
                'realized_pnl': 0,
            }
    
    async def _place_order(
        self, 
        market_id: str, 
        side: str, 
        size: float, 
        price: float,
        outcome: str
    ) -> Dict[str, Any]:
        """Place an order through the Polymarket client."""
        # This would integrate with the actual Polymarket API
        if hasattr(self.client, 'place_order'):
            return await self.client.place_order(
                market_id=market_id,
                side=side,
                size=size,
                price=price
            )
        else:
            raise NotImplementedError("Order placement not implemented")
    
    async def _unwind_partial_execution(
        self, 
        opportunity: ArbitrageOpportunity, 
        leg_results: List[Dict]
    ):
        """Unwind successfully executed legs after partial failure."""
        logger.warning("Unwinding partial execution")
        
        for i, result in enumerate(leg_results):
            if result.get('success', False):
                leg = opportunity.legs[i]
                # Place opposite order to unwind
                try:
                    unwind_side = 'sell' if leg.side == 'buy' else 'buy'
                    await self._place_order(
                        market_id=leg.market_id,
                        side=unwind_side,
                        size=leg.size,
                        price=leg.expected_price,  # May need market price
                        outcome=leg.outcome
                    )
                except Exception as e:
                    logger.error(f"Failed to unwind leg {i}: {e}")
    
    async def _simulate_execution(
        self, 
        opportunity: ArbitrageOpportunity
    ) -> ArbitrageResult:
        """Simulate arbitrage execution for testing."""
        await asyncio.sleep(0.05)  # Simulate execution time
        
        # Simulate some slippage
        slippage = 0.9 + (0.2 * (hash(opportunity.opportunity_id) % 100) / 100)
        simulated_profit = opportunity.expected_profit * slippage
        
        leg_results = [
            {
                'leg': i,
                'success': True,
                'simulated': True,
                'market_id': leg.market_id,
                'realized_pnl': simulated_profit / len(opportunity.legs)
            }
            for i, leg in enumerate(opportunity.legs)
        ]
        
        return ArbitrageResult(
            opportunity_id=opportunity.opportunity_id,
            success=True,
            profit_actual=simulated_profit,
            leg_results=leg_results
        )
    
    async def _profit_locking(
        self, 
        opportunity: ArbitrageOpportunity, 
        result: ArbitrageResult
    ):
        """Lock in profits immediately after execution."""
        # In practice, this might involve:
        # 1. Immediately hedging any residual risk
        # 2. Converting realized profits to stablecoins
        # 3. Updating position tracking
        
        self._daily_pnl += result.profit_actual
        
        logger.info(
            f"Profit locked for {opportunity.opportunity_id}: "
            f"${result.profit_actual:.2f}"
        )
    
    # ========================================================================
    # Market Data Management
    # ========================================================================
    
    async def _update_market_data(self):
        """Update cached market data."""
        if self.client and hasattr(self.client, 'get_markets'):
            try:
                markets = await self.client.get_markets()
                for market in markets:
                    self._market_data[market['id']] = market
            except Exception as e:
                logger.warning(f"Failed to update market data: {e}")
    
    def _get_best_price(
        self, 
        market_id: str, 
        outcome: str, 
        side: str
    ) -> Optional[float]:
        """Get best available price for a market outcome."""
        orderbook = self._orderbooks.get(market_id)
        
        if orderbook:
            if side == 'buy':
                # Best ask (lowest sell price)
                asks = orderbook.get('asks', [])
                if asks:
                    return asks[0]['price']
            else:
                # Best bid (highest buy price)
                bids = orderbook.get('bids', [])
                if bids:
                    return bids[0]['price']
        
        # Fallback to market data
        market = self._market_data.get(market_id)
        if market:
            return market.get(f'{outcome.lower()}_price')
        
        return None
    
    def update_orderbook(self, market_id: str, orderbook: Dict[str, Any]):
        """Update orderbook for a market."""
        self._orderbooks[market_id] = orderbook
    
    # ========================================================================
    # Monitoring and WebSocket
    # ========================================================================
    
    async def start_monitoring(self):
        """Start continuous arbitrage monitoring."""
        if self._running:
            logger.warning("Monitoring already active")
            return
        
        self._running = True
        self._stop_event.clear()
        
        logger.info("Starting arbitrage monitoring")
        
        # Start WebSocket if enabled
        if self.enable_websocket:
            await self._start_websocket()
        
        # Start scan loop
        self._scan_task = asyncio.create_task(self._scan_loop())
    
    async def stop_monitoring(self):
        """Stop arbitrage monitoring."""
        self._running = False
        self._stop_event.set()
        
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        
        if self._websocket_client:
            await self._websocket_client.disconnect()
        
        logger.info("Arbitrage monitoring stopped")
    
    async def _scan_loop(self):
        """Main scanning loop."""
        while self._running and not self._stop_event.is_set():
            try:
                # Scan for opportunities
                opportunities = await self.scan_for_arbitrage()
                
                # Clean up expired opportunities
                self._cleanup_expired()
                
                # Auto-execute if in live mode and high confidence
                if self.execution_mode == ExecutionMode.LIVE:
                    for opp in opportunities:
                        if opp.confidence > 0.8 and opp.profit_percent > self.min_profit_percent * 1.5:
                            await self.execute_arbitrage(opp)
                
                # Wait for next scan
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.scan_interval_seconds
                )
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                await asyncio.sleep(1)
    
    async def _start_websocket(self):
        """Start WebSocket connection for real-time data."""
        try:
            from .websocket_client import PolymarketWebSocket
            
            self._websocket_client = PolymarketWebSocket()
            
            @self._websocket_client.on_orderbook_update
            def on_book(update):
                self.update_orderbook(update.market_id, update.to_dict())
            
            await self._websocket_client.connect()
            logger.info("WebSocket connected for arbitrage monitoring")
            
        except ImportError:
            logger.warning("WebSocket client not available")
        except Exception as e:
            logger.error(f"Failed to start WebSocket: {e}")
    
    def _cleanup_expired(self):
        """Remove expired opportunities."""
        expired = []
        for opp_id, opp in self._active_opportunities.items():
            if opp.is_expired:
                expired.append(opp_id)
                opp.status = ArbitrageStatus.EXPIRED
                self._opportunity_history.append(opp)
                self.stats.record_expired()
        
        for opp_id in expired:
            del self._active_opportunities[opp_id]
    
    # ========================================================================
    # Callbacks
    # ========================================================================
    
    def on_opportunity(self, callback: Callable[[ArbitrageOpportunity], None]):
        """
        Register callback for new opportunities.
        
        Args:
            callback: Function receiving ArbitrageOpportunity
        """
        self._opportunity_callbacks.append(callback)
        return callback
    
    def on_execution(self, callback: Callable[[ArbitrageResult], None]):
        """
        Register callback for execution results.
        
        Args:
            callback: Function receiving ArbitrageResult
        """
        self._execution_callbacks.append(callback)
        return callback
    
    def _notify_opportunity(self, opportunity: ArbitrageOpportunity):
        """Notify opportunity callbacks."""
        for callback in self._opportunity_callbacks:
            try:
                callback(opportunity)
            except Exception as e:
                logger.error(f"Opportunity callback error: {e}")
    
    def _notify_execution(self, result: ArbitrageResult):
        """Notify execution callbacks."""
        for callback in self._execution_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Execution callback error: {e}")
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _string_similarity(self, a: str, b: str) -> float:
        """Calculate simple string similarity (0 to 1)."""
        # Simple Jaccard similarity on words
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        
        if not words_a or not words_b:
            return 0.0
        
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        
        return intersection / union if union > 0 else 0.0
    
    def get_active_opportunities(self) -> List[ArbitrageOpportunity]:
        """Get list of currently active opportunities."""
        return list(self._active_opportunities.values())
    
    def get_opportunity_history(self) -> List[ArbitrageOpportunity]:
        """Get historical opportunities."""
        return self._opportunity_history.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return self.stats.to_dict()
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = ArbitrageStats()
        self._daily_pnl = 0.0
        self._circuit_breaker_failures = 0
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_monitoring()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_monitoring()


# ============================================================================
# Convenience Functions
# ============================================================================

async def scan_single_arbitrage(
    market_a: Dict[str, Any],
    market_b: Dict[str, Any],
    arb_type: ArbitrageType = ArbitrageType.COMPLEMENTARY
) -> Optional[ArbitrageOpportunity]:
    """
    Scan for arbitrage between two specific markets.
    
    Args:
        market_a: First market data
        market_b: Second market data
        arb_type: Type of arbitrage to check
        
    Returns:
        ArbitrageOpportunity if found, None otherwise
    """
    detector = ArbitrageDetector(
        enable_websocket=False,
        scan_interval_seconds=60
    )
    
    # Add markets to cache
    detector._market_data[market_a['id']] = market_a
    detector._market_data[market_b['id']] = market_b
    
    # Check specific type
    if arb_type == ArbitrageType.COMPLEMENTARY:
        return detector._check_complementary_arbitrage(market_a, market_b)
    elif arb_type == ArbitrageType.SUBSET:
        return detector._check_subset_arbitrage(market_a, market_b)
    
    return None


def calculate_theoretical_arbitrage(
    price_yes_a: float,
    price_no_b: float,
    fee_percent: float = 0.2
) -> Dict[str, float]:
    """
    Calculate theoretical arbitrage profit.
    
    Args:
        price_yes_a: Price of YES on market A
        price_no_b: Price of NO on market B
        fee_percent: Trading fee percentage
        
    Returns:
        Dictionary with profit calculations
    """
    total_cost = price_yes_a + price_no_b
    gross_profit = 1.0 - total_cost
    
    # Fees on both legs
    fees = (price_yes_a + price_no_b) * (fee_percent / 100)
    
    net_profit = gross_profit - fees
    
    return {
        'total_cost': round(total_cost, 4),
        'gross_profit': round(gross_profit, 4),
        'fees': round(fees, 4),
        'net_profit': round(net_profit, 4),
        'net_profit_percent': round(net_profit * 100, 2),
        'is_profitable': net_profit > 0,
    }


# ============================================================================
# Main (for testing)
# ============================================================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test():
        """Test the arbitrage detector."""
        print("=" * 60)
        print("Arbitrage Detector Test")
        print("=" * 60)
        
        # Create detector in simulation mode
        detector = ArbitrageDetector(
            min_profit_percent=1.0,
            execution_mode=ExecutionMode.SIMULATION,
            enable_websocket=False
        )
        
        # Register callbacks
        @detector.on_opportunity
        def on_opp(opp):
            print(f"\n🎯 Opportunity Found!")
            print(f"   Type: {opp.arb_type.value}")
            print(f"   Profit: {opp.profit_percent:.2f}%")
            print(f"   Confidence: {opp.confidence:.1%}")
            print(f"   Legs: {len(opp.legs)}")
        
        # Simulate market data
        detector._market_data = {
            'market_1': {
                'id': 'market_1',
                'question': 'Will BTC close above $50,000?',
                'yes_price': 0.60,
                'no_price': 0.40,
            },
            'market_2': {
                'id': 'market_2',
                'question': 'Will BTC close below $50,000?',
                'yes_price': 0.45,
                'no_price': 0.55,
            },
            'market_3': {
                'id': 'market_3',
                'question': 'Will Trump win 2024?',
                'yes_price': 0.55,
                'no_price': 0.45,
            },
            'market_4': {
                'id': 'market_4',
                'question': 'Will Republican win 2024?',
                'yes_price': 0.50,
                'no_price': 0.50,
            },
        }
        
        # Manually scan
        print("\nScanning for complementary arbitrage...")
        opp = detector._check_complementary_arbitrage(
            detector._market_data['market_1'],
            detector._market_data['market_2']
        )
        if opp:
            print(f"Found: {opp.to_dict()}")
        
        print("\nScanning for subset arbitrage...")
        opp = detector._check_subset_arbitrage(
            detector._market_data['market_3'],
            detector._market_data['market_4']
        )
        if opp:
            print(f"Found: {opp.to_dict()}")
        
        # Test full scan
        print("\nFull scan...")
        opportunities = await detector.scan_for_arbitrage()
        print(f"Total opportunities found: {len(opportunities)}")
        
        # Test execution
        if opportunities:
            print("\nTesting execution...")
            result = await detector.execute_arbitrage(opportunities[0])
            print(f"Result: {result.to_dict()}")
        
        # Print stats
        print("\n" + "=" * 60)
        print("Statistics:")
        print("=" * 60)
        print(json.dumps(detector.get_stats(), indent=2))
        
        print("\n✅ Test complete!")
    
    # Run test
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)
