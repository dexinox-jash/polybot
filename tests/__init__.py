"""
Comprehensive Test Suite for Polymarket Copy-Trading Bot

Testing Strategy:
- Unit tests for each module
- Integration tests for workflows
- Property-based tests for edge cases
- Mock-based tests for API independence
- Performance tests for calculation efficiency
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
