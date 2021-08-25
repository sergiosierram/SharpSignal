#Importamos la clase EClient y Contract
from ibapi.client import EClient, Contract
#Importamos la clase EWrapper
from ibapi.wrapper import EWrapper
#Importamos las anotaciones
from ibapi.utils import iswrapper

#Importamos algunos modulos para manejo de hilos y tiempo
from datetime import datetime
from threading import Thread
import time

class SimpleHistorical(EWrapper, EClient):
    def __init__(self, host, port, client_id):
        #Almacenamos los argumentos de entrada
        self.__host = host
        self.__port = port
        self.__client_id = client_id

        #Iniciamos el EClient
        EClient. __init__(self, self)

        #Iniciamos la conexion
        self.connect(self.__host, self.__port, self.__client_id)

        #Creamos el hilo sobre el que se ejecutara la conexion
        thread = Thread(target=self.run)
        thread.start()

    @iswrapper
    def historicalData(self, reqId, bar):
        #Callback ejecutado en respuesta a reqHistoricalData '''
        print('{} - Close price: {}'.format(bar.date, bar.close))

    def error(self, reqId, code, msg):
        #Se ejecuta si ocurre un error
        print('Error {}: {}'.format(code, msg))

def main():
    #Instanciamos el cliente y nos conectamos
    client = SimpleHistorical('127.0.0.1', 7497, 0)

    #Creamos el contrato
    con = Contract()
    con.symbol = 'SPY'
    con.secType = 'STK'
    con.exchange = 'SMART'
    con.currency = 'USD'

    # Request historical bars
    now = datetime.now().strftime("%Y%m%d, %H:%M:%S")
    client.reqHistoricalData(3, con, now, '2 m', '3 mins',
        'MIDPOINT', False, 1, False, [])

    # Sleep while the requests are processed
    time.sleep(20)

    # Disconnect from TWS
    client.disconnect()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("Something unexpected just occurred!")
        print(e)