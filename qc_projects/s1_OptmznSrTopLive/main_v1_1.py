from io import StringIO
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import optimize

from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json

class CasualFluorescentYellowCaterpillar(QCAlgorithm):

    def Initialize(self):
        #Backtest dates
        self.SetStartDate(2021, 10, 10)  # Set Start Date
        
        #Algorithm cash
        self.SetCash(4000)
        
        self.SetBrokerageModel(BrokerageName.Bitfinex, AccountType.Cash)
        self.SetBenchmark("BTCUSD")
        
        #Paremeters to get info from coinmarketcap
        self.url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
        self.parameters = {
          'start':'1',
          'limit':'20',
          'convert':'USD'
        }
        headers = {
          'Accepts': 'application/json',
          'X-CMC_PRO_API_KEY': 'YOUR API HERE',
        }
        self.session = Session()
        self.session.headers.update(headers)
        
        #Parameters
        self.window = int(self.GetParameter("window"))
        self.rebalance = int(self.GetParameter("rebalance"))
        self.topx = int(self.GetParameter("topx"))
        self.allocation = float(self.GetParameter("allocation"))
        self.t_count = -1       #This counter is for rebalancing purposes   
        self.week_count = 0     #This counter is for indexing the dataset
        self.symbols = []
        self.last_symbols = []
        self.resolution = Resolution.Hour
        self.last_hour = -1
        
        #Additional variables
        #List to store previous weights
        self.last_w = [0 for i in range(len(self.symbols))]
        self.use_last = True
        
        #Get the first list of top X symbols
        self.GetTopX()
        self.initRollingWindow()
        
        self.Rf=0 # April 2019 average risk  free rate of return in USA approx 3%
        annRiskFreeRate = self.Rf/100
        self.r0 = (np.power((1 + annRiskFreeRate),  (1.0 / 360.0)) - 1.0) * 100 
        self.portfolioSize = len(self.rolling)
        
        self.Debug("Configuration OK")
        return
    
    def GetTopX(self):
        self.symbols = []
        try:
            response = self.session.get(self.url, params=self.parameters)
            data = json.loads(response.text)
            data = data['data']
            idx = 0
            top_idx = 0
            while top_idx < self.topx:
                try:
                    symbol = data[idx]['symbol']+'USD'
                    if symbol != "USDTUSD" and symbol != "USDCUSD" and symbol != "BUSDUSD":
                        dataSymbol = self.AddCrypto(symbol, self.resolution, Market.Bitfinex)
                        dataSymbol.SetFeeModel(CustomFeeModel(self))
                        self.symbols.append(symbol)
                        top_idx += 1
                    idx += 1
                except:
                    idx += 1
                if idx == 19:
                    self.Debug("Unable to form the full top")
                    break
            self.Debug("Get top OK")
        except (ConnectionError, Timeout, TooManyRedirects) as e:
          self.Log(e)
        return
    
    def initRollingWindow(self):
        unavailable = 0
        self.rolling = [RollingWindow[float](self.window) for symbol in self.symbols]
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
        #self.Debug(str(real)+"/"+str(prev))
        return
    
    def OnData(self, data):
        if self.last_hour != self.Time.hour:
            self.Debug("Data Tick")
            self.t_count += 1
            if self.t_count % self.rebalance == 0:
                self.Debug("Starting rebalance")
                self.SpecificTime()
                
                self.last_symbols = list(self.symbols)
                self.GetTopX()
                self.initRollingWindow()
                self.portfolioSize = len(self.rolling)
                
            for c, symbol in enumerate(self.symbols):
                if data.ContainsKey(symbol):
                    self.rolling[c].Add(data[symbol].Close)
                    
            self.last_hour = self.Time.hour
        else:
            self.Debug("Ignoring repeated data tick")
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
        
        loginfo = []
        for i in range(len(self.symbols)):
            loginfo.append(self.symbols[i] + ": " + str(w[i]))
        loginfo = " - ".join(loginfo)
        self.Debug(loginfo)
        
        #self.LiquidateOldSymbols()
        
        if not self.use_last:
            self.Liquidate()
        targets = []
        for i in range(len(w)):
            currency = self.symbols[i]
            if not self.use_last:
                self.SetHoldings(currency, w[i])
            else:
                targets.append(PortfolioTarget(currency, self.allocation*w[i]))
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
        #self.Liquidate()
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
    