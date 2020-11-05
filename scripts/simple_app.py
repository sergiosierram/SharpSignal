#Importamos la clase EClient
from ibapi.client import EClient
#Importamos la clase EWrapper
from ibapi.wrapper import EWrapper
#Importamos las anotaciones
from ibapi.utils import iswrapper

#Importamos algunos modulos genericos para manejar los hilos y el tiempo
from datetime import datetime
from threading import Thread
import time

class SimpleApp(EWrapper, EClient):
    def __init__(self, host, port, clientId):
        #Almacenamos los argumentos de entrada
        self.__host = host
        self.__port = port
        self.__clientId = clientId

        #Iniciamos el EClient
        EClient.__init__(self, self)
    
        #Iniciamos la conexión
        self.connect(self.__host, self.__port, self.__clientId)

        #Creamos el hilo lector
        thread = Thread(target=self.run)
        thread.start()
    
    @iswrapper
    def currentTime(self, cur_time):
        t = datetime.fromtimestamp(cur_time)
        print('Current time: {}'.format(t))

    @iswrapper
    def error(self, req_id, code, msg):
        print('Error {}: {}'.format(code, msg))

def main():
    # Instanciamos nuestra app
    app = SimpleApp('127.0.0.1', 7497, 0)
    # Solicitamos el tiempo 10 veces
    count = 0
    while (count < 10):
        app.reqCurrentTime()
        # Esperamos a que sea procesada la solicitud
        time.sleep(1)
        count += 1
    # Terminamos la conexion con TWS
    app.disconnect()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("Something unexpected just occurred!")
        print(e)

