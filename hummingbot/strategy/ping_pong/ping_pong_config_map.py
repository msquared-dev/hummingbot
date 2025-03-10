from hummingbot.client.config.config_var import ConfigVar

def market_prompt() -> str:
    connector = ping_pong_config_map.get("connector").value
    return f'Enter the token trading pair on {connector} >>> '


# List of parameters defined by the strategy
ping_pong_config_map ={
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="ping_pong",
    ),
    "connector":
        ConfigVar(key="connector",
                  prompt="Enter the name of the exchange >>> ",
                  prompt_on_new=True,
    ),
    "market": ConfigVar(
        key="market",
        prompt=market_prompt,
        prompt_on_new=True,
    ),
    "min_sell_price": ConfigVar(
        key="min_sell_price",
        prompt="Enter the minimum sell price >>> ",
        prompt_on_new=True,
    ),
    "max_buy_price": ConfigVar(
        key="max_buy_price",
        prompt="Enter the maximum buy price >>> ",
        prompt_on_new=True,
    ),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt="Enter the amount >>> ",
        prompt_on_new=True,
    ),
    "time_between_trades": ConfigVar(
        key="time_between_trades",
        prompt="Enter the time between trades in seconds >>> ",
        prompt_on_new=True,
    ),
    "rounds": ConfigVar(
        key="rounds",
        prompt="Enter the number of cycles (-1 = infinity) >>> ",
        prompt_on_new=True,
    ),
    "count_sell_order_in_cycle": ConfigVar(
        key="count_sell_order_in_cycle",
        prompt="Enter the count sell orders in cycle >>> ",
        prompt_on_new=True,
    ),
    "count_buy_order_in_cycle": ConfigVar(
        key="count_buy_order_in_cycle",
        prompt="Enter the count buy orders in cycle >>> ",
        prompt_on_new=True,
    ),
    "time_after_buys": ConfigVar(
        key="time_after_buys",
        prompt="Enter sleep time after buys order >>>",
        prompt_on_new=True,
    ),
    "time_after_sells": ConfigVar(
        key="time_after_sells",
        prompt="Enter sleep time after sell order >>>",
        prompt_on_new=True,
    ),
}