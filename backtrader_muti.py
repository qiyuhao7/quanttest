# -*- coding: utf-8 -*-
import backtrader as bt
import pandas as pd
from datetime import datetime

class MultiStrategy(bt.Strategy):
    params = (
        ('sma_fast', 10),
        ('sma_slow', 30),
        ('rsi_period', 14),
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('bollinger_period', 20),
        ('devfactor', 2),
        ('atr_period', 14),
        ('adx_period', 14),
        ('stoploss', 0.02),
        ('takeprofit', 0.04),
        ('risk_per_trade', 0.02),
        ('vwap_period', 20),
        ('obv_ema', 21)
    )

    def __init__(self):
        self.orders = {}  # 多股票订单管理
        self.indicators = {}  # 多股票指标存储
        
        for d in self.datas:
            # 基础指标
            self.indicators[d] = {
                'sma_fast': bt.indicators.SMA(d.close, period=self.p.sma_fast),
                'sma_slow': bt.indicators.SMA(d.close, period=self.p.sma_slow),
                'rsi': bt.indicators.RSI(d.close, period=self.p.rsi_period),
                'macd': bt.indicators.MACD(d,
                    period_me1=self.p.macd_fast,
                    period_me2=self.p.macd_slow,
                    period_signal=self.p.macd_signal),
                'bollinger': bt.indicators.BollingerBands(d,
                    period=self.p.bollinger_period,
                    devfactor=self.p.devfactor),
                'atr': bt.indicators.ATR(d, period=self.p.atr_period),
                'adx': bt.indicators.ADX(d, period=self.p.adx_period),
                'vwap': bt.indicators.VWAP(d, period=self.p.vwap_period),
                'obv': bt.indicators.OBV(d),
                'obv_ema': bt.indicators.EMA(bt.indicators.OBV(d),
                    period=self.p.obv_ema),
                'volume_sma': bt.indicators.SMA(d.volume, period=10)
            }

    def next(self):
        for d in self.datas:
            pos = self.getposition(d).size
            indicators = self.indicators[d]
            
            # 趋势判断
            trend_up = (indicators['sma_fast'][0] > indicators['sma_slow'][0] and
                       indicators['macd'].macd[0] > indicators['macd'].signal[0] and
                       d.close[0] > indicators['bollinger'].lines.top[0])
            
            # 反转信号
            reversal = (indicators['rsi'][0] < 30 and
                       d.close[0] < indicators['bollinger'].lines.bot[0] and
                       indicators['obv'][0] > indicators['obv_ema'][0])
            
            # 动量确认
            momentum = (indicators['adx'][0] > 25 and
                       indicators['volume_sma'][0] > d.volume[-20:].mean())
            
            # 风险管理
            price = d.close[0]
            atr_stop = price - 2 * indicators['atr'][0]
            risk_amount = self.broker.getvalue() * self.p.risk_per_trade
            size = risk_amount / indicators['atr'][0]
            
            # 订单执行逻辑
            if not pos:
                if trend_up and momentum:
                    tp = price * (1 + self.p.takeprofit)
                    sl = atr_stop
                    os = self.order_target_size(target=size)
                    self.sell(exectype=bt.Order.StopTrail, trailamount=sl)
                    self.buy(exectype=bt.Order.Limit, price=tp, parent=os)
            else:
                if reversal or d.close[0] < sl:
                    self.close(data=d)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            self.orders[order.data._name] = order

class PandasData(bt.feeds.PandasData):
    params = (
        ('datetime', None),
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', None)
    )

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    
    # 添加多股票数据
    symbols = ['AAPL', 'MSFT', 'GOOG']  # 示例股票
    for sym in symbols:
        df = pd.read_csv(f'{sym}.csv', parse_dates=['Date'], index_col='Date')
        data = PandasData(dataname=df)
        cerebro.adddata(data, name=sym)
    
    cerebro.addstrategy(MultiStrategy)
    cerebro.broker.setcash(1000000)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addsizer(bt.sizers.PercentSizer, percents=90)
    
    results = cerebro.run()
    print(f'最终组合价值: {cerebro.broker.getvalue():.2f}')
    cerebro.plot(style='candlestick')
