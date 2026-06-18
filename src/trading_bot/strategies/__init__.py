"""Trading strategies. Importing this package registers all built-in strategies.

To add a new strategy: create a module here, subclass ``Strategy``, decorate it with
``@register("your_key")``, and import it below so registration runs.
"""

from trading_bot.strategies.base import (
    Strategy,
    available_strategies,
    get_strategy,
    register,
)

# Importing each module triggers its @register(...) decorator.
from trading_bot.strategies import ma_crossover, mean_reversion, rsi, pairs  # noqa: E402,F401

__all__ = [
    "Strategy",
    "register",
    "get_strategy",
    "available_strategies",
]
