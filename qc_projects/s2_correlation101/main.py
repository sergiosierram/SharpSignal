from System.Drawing import Color
from Execution.ImmediateExecutionModel import ImmediateExecutionModel
from Portfolio.EqualWeightingPortfolioConstructionModel import EqualWeightingPortfolioConstructionModel
from Risk.MaximumDrawdownPercentPerSecurity import MaximumDrawdownPercentPerSecurity
from Correlation101AlphaModel import Correlation101AlphaModel


class S2Correlation101(QCAlgorithm):

    def Initialize(self):
        #Initial investment and backtest period
        self.SetStartDate(2010, 1, 1)   # Set Start Date
        self.SetCash(100000)            # Set Strategy Cash
        
        #Universe
        tickers = ['SPY'] # S&P 500
        symbols = [ Symbol.Create(ticker, SecurityType.Equity, Market.USA) for ticker in tickers ]
        self.SetUniverseSelection( ManualUniverseSelectionModel(symbols) )
        self.UniverseSettings.Resolution = Resolution.Daily
        
        #Alpha
        self.AddAlpha(Correlation101AlphaModel(Resolution.Daily, [-1], 10, 3))
        
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())
        
        self.SetExecution(ImmediateExecutionModel())

        self.SetRiskManagement(MaximumDrawdownPercentPerSecurity(0.01))
        
        #Plots
        stockPlot = Chart("Comparison")
        stockPlot.AddSeries(Series("Benchmark", SeriesType.Line, 100000, Color.Blue))
        stockPlot.AddSeries(Series("Algorithm", SeriesType.Line, 100000))
        self.AddChart(stockPlot)
        
        #Benchmarking
        self.buy_and_hold()
        
    def buy_and_hold(self):
        self.shares_bench = 0
        self.balance_bench = 100000
        return

    def OnEndOfAlgorithm(self):
        self.Debug(str("[QCAlgorithm] Liquidating all holdings on end of algorithm"))
        self.Liquidate()
        return


    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.
            Arguments:
                data: Slice object keyed by symbol containing the stock data
        '''
        if (self.shares_bench == 0):
            price_bench = data['SPY'].Close
            self.shares_bench = int(self.balance_bench / price_bench)
            self.base_bench = self.balance_bench-(self.shares_bench*price_bench)
            self.unrealized_bench = self.shares_bench*price_bench
        else:
            price_bench = data['SPY'].Close
            self.balance_bench = self.base_bench + (self.shares_bench*price_bench)
            
        self.Plot("Strategy Equity", "Benchmark", self.balance_bench)    
        self.Plot("Comparison", "Benchmark", self.balance_bench)
        self.Plot("Comparison", "Algorithm", self.Portfolio.TotalPortfolioValue)
        # if not self.Portfolio.Invested:
        #    self.SetHoldings("SPY", 1)