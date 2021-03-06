"""
stategy
---------
"""

# use future imports for python 3.x forward compatibility
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

# other imports
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from talib.abstract import *

# project imports
import pinkfish as pf

class Strategy():
    """ strategy """

    def __init__(self, symbol, capital, start, end, use_adj, period,
                 slippage_per_trade=0, commissions_per_trade=0):
        self._symbol = symbol
        self._capital = capital
        self._start = start
        self._end = end
        self._use_adj = use_adj
        self._period = period
        self._slippage_per_trade = slippage_per_trade
        self._commissions_per_trade = commissions_per_trade

    def _algo(self):
        """ Algo:
            1. The SPY is above its 200-day moving average
            2. The SPY makes an intraday X-day low, buy.
            3. If the SPY makes an intraday X-day high, sell your long position.
        """

        self._tlog.cash = self._capital
        start_flag = True
        end_flag = False
        stop_loss = 0

        for i, row in enumerate(self._ts.itertuples()):

            date = row.Index.to_pydatetime()
            high = row.high
            low = row.low
            close = row.close
            open_ = row.open
            prev_close = self._ts['close'][i-1]
            sma200 = self._ts['sma200'][i-1]
            period_high = self._ts['period_high'][i-1]
            period_low = self._ts['period_low'][i-1]
            end_flag = True if (i == len(self._ts) - 1) else False
            trade_state = None

            if i == 0 or pd.isnull(sma200) or date < self._start:
                continue
            elif start_flag:
                start_flag = False
                # set start and end
                self._start = date
                self._end = self._ts.index[-1]

            # buy
            if (self._tlog.num_open_trades() == 0
                and prev_close > sma200
                and low <= period_low
                and not end_flag):

                # adjust price if opened less than period_low
                price = open_ if open_ <= period_low else period_low
               
                # enter buy in trade log
                shares = self._tlog.enter_trade(date, price)
                trade_state = pf.TradeState.OPEN
                #print("{0} BUY  {1} {2} @ {3:.2f}".format(
                #      date, shares, self._symbol, close))
                
                # set stop loss
                stop_loss = 0*low

            # sell
            elif (self._tlog.num_open_trades() > 0
                  and (high >= period_high or low < stop_loss or end_flag)):

                # adjust price if opened greater than period_high; stop_loss; close
                if high >= period_high:
                    price = open_ if open_ >= period_high else period_high
                elif low < stop_loss:
                    price = stop_loss
                else:
                    price = close

                # enter sell in trade log
                shares = self._tlog.exit_trade(date, price)
                trade_state = pf.TradeState.CLOSE
                #print("{0} SELL {1} {2} @ {3:.2f}".format(
                #      date, shares, self._symbol, close))
                #if (low < stop_loss):
                #    print("--------------------STOP-----------------------------")

            # hold
            else:
                trade_state = pf.TradeState.HOLD

            # record daily balance
            self._dbal.append(date, high, low, close,
                              self._tlog.shares, self._tlog.cash,
                              trade_state) 

    def run(self):
        self._ts = pf.fetch_timeseries(self._symbol)
        self._ts = pf.select_tradeperiod(self._ts, self._start,
                                         self._end, use_adj=self._use_adj)

        # Add technical indicator: 200 day sma
        sma200 = SMA(self._ts, timeperiod=200)
        self._ts['sma200'] = sma200

        # Add technical indicator: X day high, and X day low
        period_high = pd.Series(self._ts.high).rolling(self._period).max()
        period_low = pd.Series(self._ts.high).rolling(self._period).min()
        self._ts['period_high'] = period_high
        self._ts['period_low'] = period_low

        self._tlog = pf.TradeLog()
        self._dbal = pf.DailyBal()

        self._algo()

    def get_logs(self):
        """ return DataFrames """
        tlog = self._tlog.get_log()
        dbal = self._dbal.get_log()
        return tlog, dbal

    def stats(self):
        tlog, dbal = self.get_logs()

        stats = pf.stats(self._ts, tlog, dbal,
                         self._start, self._end, self._capital)
        return stats

def summary(strategies, *metrics):
    """ Stores stats summary in a DataFrame.
        stats() must be called before calling this function
    """
    index = []
    columns = strategies.index
    data = []
    # add metrics
    for metric in metrics:
        index.append(metric)
        data.append([strategy.stats[metric] for strategy in strategies])

    df = pd.DataFrame(data, columns=columns, index=index)
    return df

def plot_bar_graph(df, metric):
    """ Plot Bar Graph: Strategy
        stats() must be called before calling this function
    """
    df = df.loc[[metric]]
    df = df.transpose()
    fig = plt.figure()
    axes = fig.add_subplot(111, ylabel=metric)
    df.plot(kind='bar', ax=axes, legend=False)
    axes.set_xticklabels(df.index, rotation=0)
