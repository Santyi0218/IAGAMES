import os
import ujson
import esp32
import _thread
import utime as tm
import machine as m
import max6675 as mx
import network as nt
from machine import Pin
from machine import ADC
import ubinascii as ubi
import usocket as socket
import urequests as requests
from umqttsimple import MQTTClient

global pindos, pinquince
token = 'BBFF-KiYIZkRcnh48FQrWjilcKqi4v34tDu'

client_id = ubi.hexlify(m.unique_id())
server = "industrial.api.ubidots.com"

label_gota = "gotas"
label_humedad = "humedad"
label_temperatura = "temperatura"

USER_AGENT = "miprimerdispositivo/V1.0"
DEVICE_NAME = "miprimerdispositivo"
DEVICE_LABEL = "miprimerdispositivo"
PORT = 9012
TIMEOUT = 10

tiemporestante = 20

#FUNCIONES DE CONFIGURACION WIFI###################################################
def modost(SSID, PASSWORD):
  import network as nt
  global sta_if, conexion
  sta_if = nt.WLAN(nt.STA_IF)
  conexion = 1
  tm.sleep(2)
  if not sta_if.isconnected():
    sta_if.active(True)
    sta_if.connect(SSID, PASSWORD)
    print("CONECTADO A LA RED WI-FI")
    while not sta_if.isconnected():
      print("CREDENCIALES MALAS")
      tm.sleep(2)
      pass
  print("YA CONOCIA ESTA RED")

#FUNCIONES GOTA####################################################################
def sumagota():
  pass
def sinrebote():
  global timer_pluv
  timer_pluv.init(mode = m.Timer.ONE_SHOT, period = 100, callback = sumagota)
  
#FUNCIONES TIEMPO GOTA#############################################################  
def establecertiempo(contador,tiempo):
  with open("tiempo.csv","w") as f:
    f.write(str(contador+tiempo))
def tiempoReanudar():
  global tiemporestante
  try:
    with open("tiempo.csv","r") as f:
      contador = int(f.read())
    tiemporestante = contador-tm.time()
    if (tiemporestante<0):
      tiemporestante = 5
  except Exception as e:
    print("[ERROR] File error",e)
    tiemporestante = 20 #DEBE CORRESPONDER AL TIEMPO DEL DOCUMENTO
    with open("tiempo.csv","w") as f:
      f.write(str(tm.time()+tiemporestante))
  return tiemporestante
#FUNCIONES HUMEDAD#################################################################
def measure(channel, nsamples):#Realiza un estadistico para estabilizar una medida
  list_values = []
  for i in range(nsamples):
    list_values.append(channel.read())
    tm.sleep(10e-3)
  list_values.sort()
  median = (list_values[nsamples//2]+list_values[1+nsamples//2])/2
  return median
def scale(adc, adc_min, adc_max, v_min, v_max):
  m=0
  v=0
  m = (v_max - v_min)/(adc_max - adc_min)
  v = m*(adc - adc_min)+(v_min)
  return v#Establece rangos de medida
#FUNCIONES RELACIONADAS CON ARCHIVOS###############################################
def writefile(name_file, dato):#Realiza escritura de un archivo
  with open(name_file, "a") as f:
    f.write("{}\n".format(dato))
def readfile(name_file):
  num_rows = 0
  for row in open(name_file):
    num_rows += 1
  return num_rows
def verificacion(nombre, encabezado):
  puta = os.listdir("/")
  if nombre in puta:
    pass
  else:
    newfile(nombre, encabezado)
def newfile(nombre, encabezado):
  with open(nombre, "a") as f:
    f.write(encabezado)
#FUNCIONES SELECTOR DE PROTOCOLO DE COM############################################
  
#FUNCION SELECTOR MODO COM#########################################################
def selector(numerodelineas, medidareal, temperatura):
  global pindos, pinquince, token, label_gota, label_humedad, label_temperatura
  if pindos.value() == True and pinquince.value() == False: #HTTP
    print("HTTP")
    gotas_dic = {label_gota:{'value':numerodelineas, 'context': {'Comunicado':'HTTP'}}}
    humedad_dic = {label_humedad:{'value':medidareal, 'context': {'Comunicado':'HTTP'}}}
    temperatura_dic = {label_temperatura:{'value':temperatura, 'context': {'Comunicado':'HTTP'}}}
    enviar_datos(gotas_dic, token)
    enviar_datos(humedad_dic, token)
    enviar_datos(temperatura_dic, token)
    tm.sleep(1)
    print("Subi datos por HTTP")
  elif pinquince.value() == True and pindos.value() == False: #MQTT
    print("MQTT")
    try:
      print("CONECTADO A SERVER MQTT...")
      client = connect_and_suscribe()
      tm.sleep(1)
    except Exception as e:
      print("NO CONECTO...")
      m.reset()
    print("[INFO] MQTT Server connected!")
    json_gotas = ujson.dumps({'gotas':{'value':numerodelineas, 'context':{'Comunicado':'MQTT'}}}).encode('UTF-8')
    json_humedad = ujson.dumps({'humedad':{'value':medidareal, 'context':{'Comunicado':'MQTT'}}}).encode('UTF-8')
    json_temperatura = ujson.dumps({'temperatura':{'value':temperatura, 'context':{'Comunicado':'MQTT'}}}).encode('UTF-8')
    client.publish('/v1.6/devices/miprimerdispositivo', json_gotas)
    client.publish('/v1.6/devices/miprimerdispositivo', json_humedad)
    client.publish('/v1.6/devices/miprimerdispositivo', json_temperatura)
    print("Subi datos por MQTT")
    tm.sleep(1)
  else:
    print("SOCKET")
    send_data(numerodelineas, medidareal, temperatura)
#MQTT##############################################################################
def connect_and_suscribe():
  global client_id, server, client, token
  client = MQTTClient(client_id, server, port = 1883, user = token, password = '')
  try:
    client.connect()
  except Exception as e:
    print("[ERROR] {}".format(e))
  print("[INFO] Connected to MQTT Server: {}".format(server))
  return client
#HTTP##############################################################################
def enviar_datos(payload, token):
  global server
  try:
    url = "http://{}/api/v1.6/devices/miprimerdispositivo".format(server)
    print("[INFO] Endpoint: ",url)
    headers = {"X-Auth-Token": token, "Content-Type": "application/json"}
    attempts = 0
    response = 400
    while response>=400 and attempts <=5:
      print("[INFO] Sending information to the HTTP Server...")
      http_request = requests.post(url = url,
                                   headers = headers,
                                   json = payload)
      response = http_request.status_code
      print("[INFO] Response code: ", response)
      print("[INFO] Response: ", http_request.text)
      attempts+=1
  except Exception as e:
    print("[ERROR] Error sending data to the server: ",e)
#SOCKET############################################################################
def send_data(numerodelineas, medidareal, temperatura):
  global token, server, PORT, label_gota, label_humedad, label_temperatura, DEVICE_LABEL, DEVICE_NAME, TIMEOUT, USER_AGENT
  try:
    print("[INFO] Sending information...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # crear un nuevo socket
    conn_parameters = socket.getaddrinfo(server, PORT)
    print("[INFO] Connection parameters", conn_parameters)
    s.connect(conn_parameters[0][-1])
    print("[INFO] Socket connected!")
    s.settimeout(TIMEOUT)  
    message = "{}|POST|{}|{}:{}=>{}:{},{}:{},{}:{}|end".format(USER_AGENT,
                                                               token,
                                                               DEVICE_LABEL,
                                                               DEVICE_NAME,
                                                               label_gota,
                                                               numerodelineas,
                                                               label_humedad,
                                                               medidareal,
                                                               label_temperatura,
                                                               temperatura)
    s.send(message.encode("UTF-8"))
    # Recibir la respuesta del servidor
    answer = s.recv(1024)
    print("[INFO] Sever response: ",answer)
  except Exception as e:
    print("[ERROR] Exception sending: ",e)
#INCIO DE LA EJECUCION PRINCIPAL###################################################  
if __name__ == "__main__":
  try:
    global pindos, pinquince
    debugpin = m.Pin(25, m.Pin.IN, m.Pin.PULL_UP)
    #ESTANDAR 00=SOCKET (POR DEFECTO), 01=HTTP, 11=MQTT#####################
    #ESTANDAR PINES, PINDOS PRIMER BINARIO, PINQUINCE SEGUNDO BINARIO      #
    pinquince = m.Pin(15, m.Pin.IN, m.Pin.PULL_UP) #CAFE                   #
    pindos = m.Pin(2, m.Pin.IN, m.Pin.PULL_UP) #AZUL                       #
    #FINALIZA CONFIGURACION SELECTOR########################################
    #GOTA#######################################################################
    input_switch_gota = m.Pin(12, m.Pin.IN, m.Pin.PULL_UP)                     #
    input_switch_gota.irq(trigger = m.Pin.IRQ_FALLING, handler = sinrebote)    #
    timer_pluv = m.Timer(2)                                                    #
    #FINALIZA GOTA##############################################################
    #Humedad####################################################################
    moisture = ADC(Pin(36))                                                    #  
    moisture.atten(ADC.ATTN_11DB)                                              #
    with open("config.json", "r") as f:                                        #
      config = f.read()                                                        #
    config = ujson.loads(config)                                               #
    adc_min = config["adc_min"]                                                #
    adc_max = config["adc_max"]                                                #
    v_max = config["v_max"]                                                    #
    v_min = config["v_min"]                                                    #
    sck = m.Pin(18, m.Pin.OUT)                                                 #
    cs = m.Pin(5, m.Pin.OUT)                                                   #
    so = m.Pin(19, m.Pin.IN)                                                   #
    sensor = mx.MAX6675(sck, cs, so)                                           #
    #Fin humedad################################################################
    #ENCABEZADOS ARCHIVOS#######################################################
    name_file1="gotas.csv"                                                     #  
    encabezado1 = "Gotas \n"                                                   #
    #FIN########################################################################
    if debugpin.value() == True:
      modost("Santiago", "MONAHANNA18")
      verificacion(name_file1, encabezado1)
      wakereason = m.wake_reason()#Razon de levantarse
      if wakereason == 3:
        print("SUMA GOTA")
        gota = 1
        writefile(name_file1, gota)
        tiemporestante = tiempoReanudar()
        print("ME QUEDAN ESTOS SEGUNDOS: ", tiemporestante)
        establecertiempo(tm.time(), tiemporestante)
      elif wakereason == 0 or wakereason == 4:
        print("ES 4")
        establecertiempo(tm.time(),tiemporestante)
        numerodelineas = readfile(name_file1)
        numerodelineas = (numerodelineas-1)*0.2
        try:
          os.remove("gotas.csv")
        except Exception as e:
          pass
        #print("BORRE ARCHIVO GOTAS")
        moisturevalor = measure(moisture, 200)
        medidareal = scale(moisturevalor, adc_min, adc_max, v_min, v_max)
        temperatura = mx.MAX6675.read(sensor)
        selector(numerodelineas, medidareal, temperatura)
      else:
        pass
      esp32.wake_on_ext1(pins = [input_switch_gota], level = esp32.WAKEUP_ANY_HIGH)
      print("ME FUI A DORMIR: ", tiemporestante)
      m.deepsleep(tiemporestante*1000) #A mimir xd
    else:
      print("PIN DEBUG")
  except KeyboardInterrupt:
    print("Entre a la interrupcion")




