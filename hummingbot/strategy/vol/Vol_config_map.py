from decimal import Decimal
from typing import Optional
from hummingbot.client.config.config_validators import validate_bool, validate_decimal, validate_exchange, validate_market_trading_pair
from hummingbot.client.config.config_var import ConfigVar


def maker_trading_pair_prompt() -> str:
    exchange = buy_sell_loop_config_map.get("exchange").value
    return f"Enter the trading pair you want to execute the strategy on {exchange} >>> "


buy_sell_loop_config_map = {
    "strategy": ConfigVar(key="strategy", prompt=None, default="buy_sell_loop"),
    "exchange": ConfigVar(
        key="exchange",
        prompt="Enter the exchange where the bot will trade >>> ",
        validator=validate_exchange,
        prompt_on_new=True,
    ),
    "market": ConfigVar(
        key="market",
        prompt=maker_trading_pair_prompt,
        validator=validate_market_trading_pair,
        prompt_on_new=True,
    ),
    "trade_amount_usdt": ConfigVar(
        key="trade_amount_usdt",
        prompt="Trade amount in USDT per order >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, 0, inclusive=False),
        prompt_on_new=True,
    ),
    "trade_frequency": ConfigVar(
        key="trade_frequency",
        prompt="Trade frequency in seconds >>> ",
        type_str="int",
        validator=lambda v: validate_decimal(v, 0, inclusive=False),
        prompt_on_new=True,
    ),
    "max_buy_price": ConfigVar(
        key="max_buy_price",
        prompt="Max buy price (stop buying above this price) >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, 0, inclusive=False),
        prompt_on_new=True,
    ),
    "min_sell_price": ConfigVar(
        key="min_sell_price",
        prompt="Min sell price (stop selling below this price) >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, 0, inclusive=False),
        prompt_on_new=True,
    ),
    "auto_mode": ConfigVar(
        key="auto_mode",
        prompt="Auto mode (continuous trading)? (True/False) >>> ",
        type_str="bool",
        validator=validate_bool,
        prompt_on_new=True,
    ),
}
