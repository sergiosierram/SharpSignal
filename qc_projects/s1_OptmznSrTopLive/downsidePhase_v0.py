from io import StringIO
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import optimize

class CasualFluorescentYellowCaterpillar(QCAlgorithm):
    '''
    Short Description: This algorithm introduces downside protection and start date effect.
    Stop loss parameter controls the percentage that each crypto should fall to be liquidated
    Stop loss size parameter defines the amount of the crypto that will be liquidate when it falls 
    Stop loss freq parameter defines how frequently each crypto is monitored.

    If you want to disable stop loss behavior, just set stop loss parameter greater than 1.

    To modify the start date or "phase" use the offset parameter to define how many hours should the
    algorithm wait to begin.
    '''

    def Initialize(self):
        #Backtest dates
        self.SetStartDate(2017, 1, 2)  # Set Start Date
        #self.SetStartDate(2021, 11, 2)
        self.SetEndDate(2021, 10, 9)
        
        #Algorithm cash
        self.SetCash(4000)
        
        #Download returns from each strategy
        csv = self.Download('https://raw.githubusercontent.com/sergiosierram/SharpSignal/main/data/market_cap.csv')
        self.market_data = pd.read_csv(StringIO(csv), index_col=0)
        self.aux_func = lambda x: x+"USD"   #This function is used to append USD to the cryptos
        
        #Parameters
        self.window = int(self.GetParameter("window"))
        self.rebalance = int(self.GetParameter("rebalance"))
        self.topx = int(self.GetParameter("topx"))
        self.stop_loss = float(self.GetParameter("stop_loss"))
        self.stop_loss_size = float(self.GetParameter("stop_loss_size"))
        self.stop_loss_freq = float(self.GetParameter("stop_loss_freq"))
        self.offset = float(self.GetParameter("offset"))
        self.t_count = -1       #This counter is for rebalancing purposes
        self.t_count2 = -1
        self.sl_count = 0
        self.week_count = 0    #This counter is for indexing the dataset
        self.symbols = []
        self.last_symbols = []
        self.resolution = Resolution.Hour
        
        #Additional variables
        #List to store previous weights
        self.last_w = [0 for i in range(len(self.symbols))]
        self.use_last = True
        
        #Get the first list of top X symbols
        self.symbols = list(self.market_data.iloc[self.week_count,0:self.topx])
        self.symbols = list(map(self.aux_func, self.symbols))
        #self.symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
        self.initializeSymbols()
        self.initRollingWindow()
        
        self.Rf=0 # April 2019 average risk  free rate of return in USA approx 3%
        annRiskFreeRate = self.Rf/100
        self.r0 = (np.power((1 + annRiskFreeRate),  (1.0 / 360.0)) - 1.0) * 100 
        self.portfolioSize = len(self.rolling)
        
        self.SetBrokerageModel(BrokerageName.Bitfinex)
        self.SetBenchmark("BTCUSD")
        return
    
    def initializeSymbols(self):
        self.symbols_objects = []
        prev = len(self.symbols)
        for symbol in self.symbols:
            try:
                data = self.AddCrypto(symbol, self.resolution, Market.Bitfinex)
                data.SetFeeModel(CustomFeeModel(self))
                self.symbols_objects.append(data.Symbol)
            except:
                self.symbols.remove(symbol)
                #self.Debug("Rm: "+str(symbol))
        real = len(self.symbols)
        #self.Debug(str(real)+"/"+str(prev))
        return
    
    def initRollingWindow(self):
        unavailable = 0
        self.rolling = [RollingWindow[float](self.window) for symbol in self.symbols]
        prev = len(self.rolling)
        for c, symbol in enumerate(self.symbols):
            df = pd.DataFrame()
            while df.empty:
                try:
                    df = self.History(self.Symbol(symbol), self.window)
                    d = df['close'].to_list()
                    for x in d:
                        self.rolling[c].Add(x)
                except:
                    #del self.rolling[c]
                    #del self.symbols[c]
                    #self.Debug("No data: "+symbol)
                    break
        real = len(self.rolling)
        #self.Debug(str(real)+"/"+str(prev))
        return
    
    def OnData(self, data):
        self.t_count2 += 1
        if self.t_count2 >= self.offset:
            self.Debug("d")
            self.t_count += 1
            self.sl_count += 1
            if self.t_count % self.rebalance == 0:
                #self.Debug("Starting rebalance")
                self.SpecificTime()
                try:
                    day, month, year = list(map(int, self.market_data.index[self.week_count].split('/')))
                    prevd = datetime(year+2000, month, day)
                    day, month, year = list(map(int, self.market_data.index[self.week_count+1].split('/')))
                    nextd = datetime(year+2000, month, day)
                    currentd = self.Time
                    if currentd > prevd and currentd <= nextd:
                        pass
                    else:
                        self.week_count += 1
                        self.last_symbols = list(self.symbols)
                        self.symbols = list(self.market_data.iloc[self.week_count,0:self.topx])
                        self.symbols = list(map(self.aux_func, self.symbols))
                        self.initializeSymbols()
                        self.initRollingWindow()
                        self.portfolioSize = len(self.rolling)
                except:
                    #This try except is to avoid problems with the last row of the dataset
                    pass
                self.sl_count = 0
            
            for c, symbol in enumerate(self.symbols):
                if data.ContainsKey(symbol):
                    self.rolling[c].Add(data[symbol].Close)
            
            #Downside Protection
            if self.sl_count % self.stop_loss_freq == 0 and self.sl_count > 0:
                equity = self.Portfolio.TotalPortfolioValue
                for symbol in self.symbols:
                    unrealized = self.Portfolio[symbol].UnrealizedProfit
                    pl_percent = unrealized/equity
                    if pl_percent < -1*self.stop_loss:
                        if self.stop_loss_size < 1:
                            quantity = self.CalculateOrderQuantity(symbol, self.stop_loss_size)
                            self.MarketOrder(symbol, -1*quantity)
                        else:
                            self.Liquidate(symbol)
                        self.Debug("Liquidating {0} StopLoss".format(symbol))
            return
    
    def SpecificTime(self):
        #Check the len of the rolling windows
        flag = True
        for roll in self.rolling:
            l = [i for i in roll][::-1]
            if len(l) < self.window:
                flag = False
        if not flag:
            return
        
        Ri = []
        for c, symbol in enumerate(self.symbols):
            Ri.append([i for i in self.rolling[c]][::-1])
        Ri = np.array(Ri).transpose()
        Ri = StockReturnsComputing(Ri, self.window, self.portfolioSize)
        Ei = np.mean(Ri, axis = 0)
        
        cov = np.cov(Ri, rowvar=False)
            
        #initialization
        xOptimal =[]
        minRiskPoint = []
        expPortfolioReturnPoint =[]
        maxSharpeRatio = 0
        
        #compute maximal Sharpe Ratio and optimal weights
        result = MaximizeSharpeRatioOptmzn(Ei, cov, self.r0, self.portfolioSize)
        xOptimal.append(result.x)
        
        w = list(xOptimal[0])
        w = [ 0 if wx < 0.0000001 else wx for wx in w ]
        
        self.Debug(w)
        #self.Debug(self.symbols)
        #self.LiquidateOldSymbols()
        
        if not self.use_last:
            self.Liquidate()
        targets = []
        for i in range(len(w)):
            currency = self.symbols[i]
            if not self.use_last:
                self.SetHoldings(currency, w[i])
            else:
                targets.append(PortfolioTarget(currency, 0.7*w[i]))
        if self.use_last:
            self.SetHoldings(targets)
        return
    
    def LiquidateOldSymbols(self):
        for symbol in self.last_symbols:
            if symbol not in self.symbols:
                self.Log("Not in last: "+symbol)
                self.Liquidate(symbol)
        return
    
    def OnEndOfAlgorithm(self):
        self.SpecificTime()
        self.Liquidate()
        return

# Custom fee model.
class CustomFeeModel(FeeModel):
    def GetOrderFee(self, parameters):
        fee = parameters.Security.Price * parameters.Order.AbsoluteQuantity * 0.002
        return OrderFee(CashAmount(fee, "USD"))
        
def MaximizeSharpeRatioOptmzn(MeanReturns, CovarReturns, RiskFreeRate, PortfolioSize):
    
    # define maximization of Sharpe Ratio using principle of duality
    def  f(x, MeanReturns, CovarReturns, RiskFreeRate, PortfolioSize):
        funcDenomr = np.sqrt(np.matmul(np.matmul(x, CovarReturns), x.T) )
        funcNumer = np.matmul(np.array(MeanReturns),x.T)-RiskFreeRate
        func = -(funcNumer / funcDenomr)
        return func

    #define equality constraint representing fully invested portfolio
    def constraintEq(x):
        A=np.ones(x.shape)
        b=1
        constraintVal = np.matmul(A,x.T)-b 
        return constraintVal
    
    #define bounds and other parameters
    xinit=np.repeat(0.33, PortfolioSize)
    cons = ({'type': 'eq', 'fun':constraintEq})
    lb = 0
    ub = 1
    bnds = tuple([(lb,ub) for x in xinit])
    
    #invoke minimize solver
    opt = optimize.minimize (f, x0 = xinit, args = (MeanReturns, CovarReturns,\
                             RiskFreeRate, PortfolioSize), method = 'SLSQP',  \
                             bounds = bnds, constraints = cons, tol = 10**-3)
    
    return opt
    
def StockReturnsComputing(StockPrice, Rows, Columns):
    
    StockReturn = np.zeros([Rows-1, Columns])
    for j in range(Columns):        # j: Assets
        for i in range(Rows-1):     # i: Daily Prices
            StockReturn[i,j]=((StockPrice[i+1, j]-StockPrice[i,j])/StockPrice[i,j])*100

    return StockReturn