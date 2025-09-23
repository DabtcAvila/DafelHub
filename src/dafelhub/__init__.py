"""
DafelHub - SaaS Consulting Hub
Built with Spec-Driven Development principles for enterprise-grade consulting services.
"""

__version__ = "0.1.0"
__author__ = "Dafel Consulting"
__email__ = "contact@dafelconsulting.com"

from dafelhub.core.config import settings
from dafelhub.core.logging import get_logger

logger = get_logger(__name__)
logger.info(f"DafelHub v{__version__} initialized")

__all__ = ["settings", "get_logger", "__version__"]