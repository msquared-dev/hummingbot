import asyncio
import threading
import time
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Set, Tuple, Any

import pandas as pd

from hummingbot.client.command.gateway_command import GatewayCommand
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT, AllConnectorSettings
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.trade_fill import TradeFill
from hummingbot.user.user_balances import UserBalances
import json

s_float_0 = float(0)
s_decimal_0 = Decimal("0")


if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def get_timestamp(days_ago: float = 0.) -> float:
    return time.time() - (60. * 60. * 24. * days_ago)


class HistoryCommand:
    def history(self,  # type: HummingbotApplication
                days: float = 0,
                verbose: bool = False,
                precision: Optional[int] = None
                ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.history, days, verbose, precision)
            return

        if self.strategy_file_name is None:
            self.notify("\n  Please first import a strategy config file of which to show historical performance.")
            return
        start_time = get_timestamp(days) if days > 0 else self.init_time
        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name)
            if not trades:
                self.notify("\n  No past trades to report.")
                return
            if verbose:
                self.list_trades(start_time)
            safe_ensure_future(self.history_report(start_time, trades, precision))

    def get_history_trades_json(self,  # type: HummingbotApplication
                                days: float = 0):
        if self.strategy_file_name is None:
            return
        start_time = get_timestamp(days) if days > 0 else self.init_time
        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name)
            return list([TradeFill.to_bounty_api_json(t) for t in trades])

    async def history_report(self,  # type: HummingbotApplication
                             start_time: float,
                             trades: List[TradeFill],
                             precision: Optional[int] = None,
                             display_report: bool = True) -> Decimal:
        market_info: Set[Tuple[str, str]] = set((t.market, t.symbol) for t in trades)
        if display_report:
            self.report_header(start_time)
        return_pcts = []
        for market, symbol in market_info:
            cur_trades = [t for t in trades if t.market == market and t.symbol == symbol]
            network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
            try:
                cur_balances = await asyncio.wait_for(self.get_current_balances(market), network_timeout)
            except asyncio.TimeoutError:
                self.notify(
                    "\nA network error prevented the balances retrieval to complete. See logs for more details."
                )
                raise
            perf = await PerformanceMetrics.create(symbol, cur_trades, cur_balances)
            if display_report:
                self.report_performance_by_market(market, symbol, perf, precision)
            return_pcts.append(perf.return_pct)
        avg_return = sum(return_pcts) / len(return_pcts) if len(return_pcts) > 0 else s_decimal_0
        if display_report and len(return_pcts) > 1:
            self.notify(f"\nAveraged Return = {avg_return:.2%}")
        return avg_return

    async def get_current_balances(self,  # type: HummingbotApplication
                                   market: str):
        if market in self.markets and self.markets[market].ready:
            return self.markets[market].get_all_balances()
        elif "Paper" in market:
            paper_balances = self.client_config_map.paper_trade.paper_trade_account_balance
            if paper_balances is None:
                return {}
            return {token: Decimal(str(bal)) for token, bal in paper_balances.items()}
        else:
            if UserBalances.instance().is_gateway_market(market):
                await GatewayCommand.update_exchange_balances(self, market, self.client_config_map)
                return GatewayCommand.all_balance(self, market)
            else:
                await UserBalances.instance().update_exchange_balance(market, self.client_config_map)
                return UserBalances.instance().all_balances(market)

    def report_header(self,  # type: HummingbotApplication
                      start_time: float):
        lines = []
        current_time = get_timestamp()
        lines.extend(
            [f"\nStart Time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"Current Time: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"Duration: {pd.Timedelta(seconds=int(current_time - start_time))}"]
        )
        self.notify("\n".join(lines))

    def report_performance_by_market(self,  # type: HummingbotApplication
                                     market: str,
                                     trading_pair: str,
                                     perf: PerformanceMetrics,
                                     precision: int):
        lines = []
        base, quote = trading_pair.split("-")
        lines.extend(
            [f"\n{market} / {trading_pair}"]
        )

        trades_columns = ["", "buy", "sell", "total"]
        trades_data = [
            [f"{'Number of trades':<27}", perf.num_buys, perf.num_sells, perf.num_trades],
            [f"{f'Total trade volume ({base})':<27}",
             PerformanceMetrics.smart_round(perf.b_vol_base, precision),
             PerformanceMetrics.smart_round(perf.s_vol_base, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_base, precision)],
            [f"{f'Total trade volume ({quote})':<27}",
             PerformanceMetrics.smart_round(perf.b_vol_quote, precision),
             PerformanceMetrics.smart_round(perf.s_vol_quote, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_quote, precision)],
            [f"{'Avg price':<27}",
             PerformanceMetrics.smart_round(perf.avg_b_price, precision),
             PerformanceMetrics.smart_round(perf.avg_s_price, precision),
             PerformanceMetrics.smart_round(perf.avg_tot_price, precision)],
        ]
        trades_df: pd.DataFrame = pd.DataFrame(data=trades_data, columns=trades_columns)
        lines.extend(["", "  Trades:"] + ["    " + line for line in trades_df.to_string(index=False).split("\n")])

        assets_columns = ["", "start", "current", "change"]
        assets_data = [
            [f"{base:<17}", "-", "-", "-"] if market in AllConnectorSettings.get_derivative_names() else  # No base asset for derivatives because they are margined
            [f"{base:<17}",
             PerformanceMetrics.smart_round(perf.start_base_bal, precision),
             PerformanceMetrics.smart_round(perf.cur_base_bal, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_base, precision)],
            [f"{quote:<17}",
             PerformanceMetrics.smart_round(perf.start_quote_bal, precision),
             PerformanceMetrics.smart_round(perf.cur_quote_bal, precision),
             PerformanceMetrics.smart_round(perf.tot_vol_quote, precision)],
            [f"{trading_pair + ' price':<17}",
             PerformanceMetrics.smart_round(perf.start_price),
             PerformanceMetrics.smart_round(perf.cur_price),
             PerformanceMetrics.smart_round(perf.cur_price - perf.start_price)],
            [f"{'Base asset %':<17}", "-", "-", "-"] if market in AllConnectorSettings.get_derivative_names() else  # No base asset for derivatives because they are margined
            [f"{'Base asset %':<17}",
             f"{perf.start_base_ratio_pct:.2%}",
             f"{perf.cur_base_ratio_pct:.2%}",
             f"{perf.cur_base_ratio_pct - perf.start_base_ratio_pct:.2%}"],
        ]
        assets_df: pd.DataFrame = pd.DataFrame(data=assets_data, columns=assets_columns)
        lines.extend(["", "  Assets:"] + ["    " + line for line in assets_df.to_string(index=False).split("\n")])

        perf_data = [
            ["Hold portfolio value    ", f"{PerformanceMetrics.smart_round(perf.hold_value, precision)} {quote}"],
            ["Current portfolio value ", f"{PerformanceMetrics.smart_round(perf.cur_value, precision)} {quote}"],
            ["Trade P&L               ", f"{PerformanceMetrics.smart_round(perf.trade_pnl, precision)} {quote}"]
        ]
        perf_data.extend(
            ["Fees paid               ", f"{PerformanceMetrics.smart_round(fee_amount, precision)} {fee_token}"]
            for fee_token, fee_amount in perf.fees.items()
        )
        perf_data.extend(
            [["Total P&L               ", f"{PerformanceMetrics.smart_round(perf.total_pnl, precision)} {quote}"],
             ["Return %                ", f"{perf.return_pct:.2%}"]]
        )
        perf_df: pd.DataFrame = pd.DataFrame(data=perf_data)
        lines.extend(["", "  Performance:"] +
                     ["    " + line for line in perf_df.to_string(index=False, header=False).split("\n")])

        self.notify("\n".join(lines))

    async def calculate_profitability(self,  # type: HummingbotApplication
                                      ) -> Decimal:
        """
        Determines the profitability of the trading bot.
        This function is used by the KillSwitch class.
        Must be updated if the method of performance report gets updated.
        """
        if not self.markets_recorder:
            return s_decimal_0
        if any(not market.ready for market in self.markets.values()):
            return s_decimal_0

        start_time = self.init_time

        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name)
            avg_return = await self.history_report(start_time, trades, display_report=False)
        return avg_return

    def list_trades(self,  # type: HummingbotApplication
                    start_time: float):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.list_trades, start_time)
            return

        lines = []

        with self.trade_fill_db.get_new_session() as session:
            queried_trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                number_of_rows=MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT + 1,
                config_file_path=self.strategy_file_name)
            df: pd.DataFrame = TradeFill.to_pandas(queried_trades)

        if len(df) > 0:
            # Check if number of trades exceed maximum number of trades to display
            if len(df) > MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT:
                df = df[:MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT]
                self.notify(
                    f"\n  Showing last {MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT} trades in the current session.")
            df_lines = format_df_for_printout(df, self.client_config_map.tables_format).split("\n")
            lines.extend(["", "  Recent trades:"] +
                         ["    " + line for line in df_lines])
        else:
            lines.extend(["\n  No past trades in this session."])
        self.notify("\n".join(lines))

    def full_report(self,  # type: HummingbotApplication
                days: float = 0,
                verbose: bool = False,
                precision: Optional[int] = None
                ):
        """
        Generates a full performance report in JSON format.

        :param days: Number of days of trade history to include.
        :param precision: Decimal precision for numerical values.
        :return: JSON string containing the performance report.
        """
        # if threading.current_thread() != threading.main_thread():
        #     self.ev_loop.call_soon_threadsafe(self.full_report, days, precision)
        #     return json.dumps({"error": "Report generation must be run in the main thread."})

        # if self.strategy_file_name is None:
        #     return json.dumps({"error": "Please import a strategy config file to show historical performance."})

        # Retrieve all unique strategy config files from the database
        with self.trade_fill_db.get_new_session() as session:
            unique_strategy_files = session.query(TradeFill.config_file_path).distinct().all()
            unique_strategy_files = [row[0] for row in unique_strategy_files if row[0] is not None]

        if not unique_strategy_files:
            return json.dumps({"error": "No strategy config files found in trade history."})

        report_data = {}

        for strategy_file in unique_strategy_files:
            start_time = get_timestamp(days) if days > 0 else self.init_time
            with self.trade_fill_db.get_new_session() as session:
                trades: List[TradeFill] = self._get_trades_from_session(
                    int(start_time * 1e3),
                    session=session,
                    config_file_path=strategy_file)
                    # config_file_path=self.strategy_file_name)
                if not trades:
                    # return json.dumps({"error": "No past trades to report."}), []
                    answer, addition = json.dumps({"error": "No past trades to report."}), []
                    report_data["strategies"][strategy_file] = answer

                else:
                    # return asyncio.run(self.history_full_report(start_time, trades, precision, verbose, True))
                    answer = asyncio.run(self.history_full_report(start_time, trades, precision, verbose, True))
                    report_data["strategies"][strategy_file] = answer

                report_data['unique_strategy_files'] = unique_strategy_files
                return json.dumps(report_data, indent=4)

            return json.dumps(report_data, indent=4)

    async def history_full_report(self,  # type: HummingbotApplication
                             start_time: float,
                             trades: List[TradeFill],
                             precision: Optional[int] = None,
                             display_report: bool = False,
                             return_json: bool = True) -> dict[str, Any]:
        """
        Processes historical trade data and generates a performance report.

        :param start_time: The start time of the report.
        :param trades: List of trades.
        :param precision: Decimal precision for numerical values.
        :param display_report: Whether to display the report.
        :param return_json: Whether to return the report as JSON.
        :return: JSON string if return_json is True.
        """
        market_info: Set[Tuple[str, str]] = set((t.market, t.symbol) for t in trades)
        report_data = {
            "start_time": datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S'),
            "current_time": datetime.fromtimestamp(get_timestamp()).strftime('%Y-%m-%d %H:%M:%S'),
            "duration": str(pd.Timedelta(seconds=int(get_timestamp() - start_time))),
            "markets": []
        }

        return_pcts = []
        for market, symbol in market_info:
            cur_trades = [t for t in trades if t.market == market and t.symbol == symbol]
            network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)

            try:
                cur_balances = await asyncio.wait_for(self.get_current_balances(market), network_timeout)
            except asyncio.TimeoutError:
                return json.dumps({"error": "Network timeout prevented balance retrieval."})

            perf = await PerformanceMetrics.create(symbol, cur_trades, cur_balances)
            market_report = self.collect_performance_data(market, symbol, perf, precision)
            report_data["markets"].append(market_report)

            return_pcts.append(perf.return_pct)

        avg_return = sum(return_pcts) / len(return_pcts) if return_pcts else s_decimal_0
        report_data["average_return"] = f"{avg_return:.2%}" if return_pcts else "N/A"

        return json.dumps(report_data, indent=4)

    def collect_performance_data(self,  # type: HummingbotApplication
                                 market: str,
                                 trading_pair: str,
                                 perf: PerformanceMetrics,
                                 precision: int) -> dict:
        """
        Collects performance data for a given market and trading pair.

        :param market: The market name.
        :param trading_pair: The trading pair.
        :param perf: PerformanceMetrics instance.
        :param precision: Decimal precision.
        :return: Dictionary with performance data.
        """
        base, quote = trading_pair.split("-")

        # **Trades Data**
        trades_data = {
            "number_of_trades": {
                "buy": perf.num_buys,
                "sell": perf.num_sells,
                "total": perf.num_trades
            },
            "total_trade_volume": {
                base: {
                    "buy": str(PerformanceMetrics.smart_round(perf.b_vol_base, precision)),
                    "sell": str(PerformanceMetrics.smart_round(perf.s_vol_base, precision)),
                    "total": str(PerformanceMetrics.smart_round(perf.tot_vol_base, precision))
                },
                quote: {
                    "buy": str(PerformanceMetrics.smart_round(perf.b_vol_quote, precision)),
                    "sell": str(PerformanceMetrics.smart_round(perf.s_vol_quote, precision)),
                    "total": str(PerformanceMetrics.smart_round(perf.tot_vol_quote, precision))
                }
            },
            "average_price": {
                "buy": str(PerformanceMetrics.smart_round(perf.avg_b_price, precision)),
                "sell": str(PerformanceMetrics.smart_round(perf.avg_s_price, precision)),
                "total": str(PerformanceMetrics.smart_round(perf.avg_tot_price, precision))
            }
        }

        # **Assets Data**
        assets_data = {
            base: "-" if market in AllConnectorSettings.get_derivative_names() else {
                "start": str(PerformanceMetrics.smart_round(perf.start_base_bal, precision)),
                "current": str(PerformanceMetrics.smart_round(perf.cur_base_bal, precision)),
                "change": str(PerformanceMetrics.smart_round(perf.tot_vol_base, precision))
            },
            quote: {
                "start": str(PerformanceMetrics.smart_round(perf.start_quote_bal, precision)),
                "current": str(PerformanceMetrics.smart_round(perf.cur_quote_bal, precision)),
                "change": str(PerformanceMetrics.smart_round(perf.tot_vol_quote, precision))
            },
            "trading_pair_price": {
                "start": str(PerformanceMetrics.smart_round(perf.start_price, precision)),
                "current": str(PerformanceMetrics.smart_round(perf.cur_price, precision)),
                "change": str(PerformanceMetrics.smart_round(perf.cur_price - perf.start_price, precision))
            },
            "base_asset_percentage": "-" if market in AllConnectorSettings.get_derivative_names() else {
                "start": f"{perf.start_base_ratio_pct:.2%}",
                "current": f"{perf.cur_base_ratio_pct:.2%}",
                "change": f"{perf.cur_base_ratio_pct - perf.start_base_ratio_pct:.2%}"
            }
        }

        # **Performance Data**
        performance_data = {
            "hold_portfolio_value": f"{PerformanceMetrics.smart_round(perf.hold_value, precision)} {quote}",
            "current_portfolio_value": f"{PerformanceMetrics.smart_round(perf.cur_value, precision)} {quote}",
            "trade_pnl": f"{PerformanceMetrics.smart_round(perf.trade_pnl, precision)} {quote}",
            "fees_paid": {
                fee_token: str(PerformanceMetrics.smart_round(fee_amount, precision))
                for fee_token, fee_amount in perf.fees.items()
            },
            "total_pnl": f"{PerformanceMetrics.smart_round(perf.total_pnl, precision)} {quote}",
            "return_percentage": f"{perf.return_pct:.2%}"
        }

        trading_data = {
            "accumulation_distribution": {
                "total_holdings": str(PerformanceMetrics.smart_round(perf.tot_vol_base, precision)),
                "average_cost_basis": str(PerformanceMetrics.smart_round(
                    perf.b_vol_quote / perf.tot_vol_base if perf.tot_vol_base > 0 else 0, precision
                )),
                "total_usdt_spent": str(PerformanceMetrics.smart_round(perf.b_vol_quote, precision)),
                "total_usdt_received": str(PerformanceMetrics.smart_round(perf.s_vol_quote, precision))
            },
            "profit_performance_metrics": {
                "unrealized_pnl": str(PerformanceMetrics.smart_round(
                    (perf.cur_price - (
                        perf.b_vol_quote / perf.tot_vol_base if perf.tot_vol_base > 0 else 0)) * perf.tot_vol_base,
                    precision
                )),
                "realized_pnl": str(PerformanceMetrics.smart_round(perf.s_vol_quote - perf.b_vol_quote, precision)),
                "total_net_pnl": str(PerformanceMetrics.smart_round(
                    (perf.s_vol_quote - perf.b_vol_quote) + ((perf.cur_price - (
                        perf.b_vol_quote / perf.tot_vol_base if perf.tot_vol_base > 0 else 0)) * perf.tot_vol_base),
                    precision
                )),
                "effective_sell_vs_buy_price": str(
                    PerformanceMetrics.smart_round(perf.avg_s_price - perf.avg_b_price, precision))
            },
            "capital_recycling": {
                "usdt_available_for_reentry": str(PerformanceMetrics.smart_round(
                    (perf.s_vol_quote - perf.b_vol_quote) + perf.cur_quote_bal, precision
                )),
                "reinvestment_amount_per_cycle": str(PerformanceMetrics.smart_round(
                    (perf.s_vol_quote - perf.b_vol_quote) + perf.cur_quote_bal, precision
                )),
                "retracement_buy_trigger_price": "N/A"  # Needs historical peak price tracking
            }
        }

        return {
            "market": market,
            "trading_pair": trading_pair,
            "trades": trades_data,
            "assets": assets_data,
            "performance": performance_data,
            "trading": trading_data
        }
