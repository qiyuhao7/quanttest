import backtrader as bt
import pandas as pd
import numpy as np

class SuperStrategy(bt.Strategy):
    params = (
        ('ema_fast', 10),
        ('ema_slow', 30),
        ('rsi_period', 14),
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('boll_period', 20),
        ('adx_period', 14),
        ('atr_period', 14),
        ('stochastic_period', 14),
        ('volatility_threshold', 0.02),
        ('risk_per_trade', 0.02),
        ('trailpercent', 2.0),
    )

    def __init__(self):
        # 价格指标
        self.ema_fast = bt.indicators.EMA(period=self.p.ema_fast)
        self.ema_slow = bt.indicators.EMA(period=self.p.ema_slow)
        self.boll = bt.indicators.BollingerBands(period=self.p.boll_period)
        self.atr = bt.indicators.ATR(period=self.p.atr_period)
        
        # 动量指标
        self.rsi = bt.indicators.RSI_SMA(
            self.data.close, period=self.p.rsi_period)
        self.macd = bt.indicators.MACD(
            self.data.close, 
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.stoch = bt.indicators.Stochastic(self.data, period=self.p.stochastic_period)
        
        # 趋势强度
        self.adx = bt.indicators.ADX(
            self.data, period=self.p.adx_period)
        
        # 波动率指标
        self.volatility = bt.indicators.StdDev(
            self.data.close, period=self.p.boll_period)
        
        # 成交量指标
        self.vol_ma = bt.indicators.SMA(
            self.data.volume, period=20)
        
        # 形态识别（示例：三乌鸦）
        self.candle_pattern = bt.indicators.CDL3BLACKCROWS(self.data)
        
        # 风险控制
        self.order = None
        self.trade_risk = 0

    def next(self):
        # 确保有足够的历史数据
        if len(self) < max(self.p.ema_slow, self.p.boll_period, self.p.adx_period):
            return

        # 多因子条件组合
        trend_cond = (self.ema_fast[0] > self.ema_slow[0] and 
                     self.data.close[0] > self.boll.lines.top[0])
        
        momentum_cond = (self.rsi[0] < 70 and 
                        self.macd.macd[0] > self.macd.signal[0] and
                        self.stoch.percD[0] < 80)
        
        volatility_cond = self.volatility[0] > self.p.volatility_threshold
        volume_cond = self.data.volume[0] > self.vol_ma[0] * 1.2
        trend_strength = self.adx[0] > 25

        # 信号生成
        long_signal = (trend_cond and momentum_cond and 
                      volatility_cond and volume_cond and trend_strength)
        
        short_signal = (self.ema_fast[0] < self.ema_slow[0] and 
                       self.data.close[0] < self.boll.lines.bot[0] and 
                       self.rsi[0] > 30 and 
                       self.candle_pattern[0] == -100)

        # 头寸管理
        if self.position:
            # 动态追踪止损
            self.trailing_stop()
            
            # 止盈条件
            if (self.data.close[0] >= self.entry_price * 1.15 or 
                self.rsi[0] > 90):
                self.close()
        else:
            # 计算头寸规模
            risk_amount = self.broker.getvalue() * self.p.risk_per_trade
            size = risk_amount / self.atr[0]
            size = int(size / self.data.close[0])

            # 开仓逻辑
            if long_signal and not self.position:
                self.buy(size=size)
                self.entry_price = self.data.close[0]
                # 初始止损
                self.stop_price = self.data.close[0] - 2 * self.atr[0]
                
            elif short_signal and not self.position:
                self.sell(size=size)
                self.entry_price = self.data.close[0]
                self.stop_price = self.data.close[0] + 2 * self.atr[0]

    def trailing_stop(self):
        if self.position.size > 0:  # 多头
            price = self.data.close[0]
            self.stop_price = max(
                self.stop_price, 
                price * (1 - self.p.trailpercent / 100)
            )
            if price <= self.stop_price:
                self.close()
                
        elif self.position.size < 0:  # 空头
            price = self.data.close[0]
            self.stop_price = min(
                self.stop_price,
                price * (1 + self.p.trailpercent / 100)
            )
            if price >= self.stop_price:
                self.close()

    def notify_trade(self, trade):
        if trade.isclosed:
            print(f'交易利润：{trade.pnl:.2f}, 净利润：{trade.pnlcomm:.2f}')

# 初始化引擎
cerebro = bt.Cerebro()

# 添加数据
data = bt.feeds.YahooFinanceData(
    dataname='AAPL',
    fromdate=datetime(2015,1,1),
    todate=datetime(2023,1,1))
cerebro.adddata(data)

# 添加策略
cerebro.addstrategy(SuperStrategy)

# 设置初始资金
cerebro.broker.setcash(100000.0)

# 设置佣金
cerebro.broker.setcommission(commission=0.001)

# 添加分析器
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio')

# 运行回测
results = cerebro.run()

# 性能分析
print('夏普比率:', results[0].analyzers.sharpe.get_analysis())
print('最大回撤:', results[0].analyzers.drawdown.get_analysis())

# 可视化
cerebro.plot(style='candlestick')
