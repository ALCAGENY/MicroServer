from typing import List, Dict, Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from paho.mqtt.client import Client
from statistics import mean, mode
from datetime import datetime, timedelta
import json
from collections import Counter

app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Permite solicitudes desde este origen
    allow_credentials=True,                  # Permite el uso de cookies
    allow_methods=["*"],                     # Permite todos los métodos HTTP (GET, POST, etc.)
    allow_headers=["*"],                     # Permite todos los encabezados
)

# Configuración MQTT
BROKER = "34.233.40.216"
PORT = 1883
TOPIC = "body_temperature"
MQTT_USER = "Didier"
MQTT_PASSWORD = "proyecto"

# Variables globales
data = []  # Almacena temperaturas con timestamp
processed_data = []  # Almacena resultados procesados (JSON)
TIME_WINDOW = timedelta(minutes=5)  # Ventana de 5 minutos para procesar datos

def process_time_window():
    """
    Procesa los datos en ventanas de 5 minutos y calcula media y moda.
    """
    global processed_data

    # Hora actual y límite inferior de tiempo
    now = datetime.now()
    window_start = now - TIME_WINDOW

    # Filtrar datos dentro de la ventana
    recent_data = [entry['temperature'] for entry in data if entry['timestamp'] >= window_start]

    if recent_data:
        avg_temp = mean(recent_data)
        status = "Normal"
        message = "Temperatura dentro del rango saludable."

        # Calcular la moda
        try:
            mode_temp = mode(recent_data)
        except:
            mode_temp = "Sin moda (temperaturas únicas)"

        # Condiciones de estado según la media
        if avg_temp >= 37.5:
            status = "Advertencia"
            message = "Riesgo de fiebre. Consulte a un médico."
        elif avg_temp >= 36.5:
            status = "Atención"
            message = "Temperatura ligeramente elevada, monitoree al paciente."

        # Crear el resultado procesado
        result = {
            "start_time": window_start.strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": now.strftime('%Y-%m-%d %H:%M:%S'),
            "average_temperature": round(avg_temp, 2),
            "mode_temperature": mode_temp,
            "status": status,
            "message": message
        }
        processed_data.append(result)

        # Mantener solo los datos recientes en la lista
        data[:] = [entry for entry in data if entry['timestamp'] >= window_start]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conexión exitosa al broker MQTT")
        client.subscribe(TOPIC)
    else:
        print(f"Fallo al conectar, código de error: {rc}")

def on_message(client, userdata, msg):
    try:
        message = json.loads(msg.payload.decode())
        if "temperature" in message:
            value = float(message["temperature"])
            data.append({"temperature": value, "timestamp": datetime.now()})
            print(f"Dato procesado: {value}")
        else:
            print("Advertencia: La clave 'temperature' no está en el mensaje")
    except json.JSONDecodeError:
        print("Advertencia: El mensaje no es un JSON válido")
    except ValueError:
        print("Advertencia: El valor de 'temperature' no es numérico")

client = Client()
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

@app.on_event("startup")
def startup_event():
    """
    Conectar al broker MQTT al iniciar FastAPI.
    """
    client.connect(BROKER, PORT, 60)
    print("Intentando conectar al broker MQTT...")
    client.loop_start()  # Inicia el loop de MQTT en un hilo

@app.on_event("shutdown")
def shutdown_event():
    """
    Desconectar del broker MQTT al detener FastAPI.
    """
    client.loop_stop()
    client.disconnect()

@app.get("/temperature_summary")
def get_temperature_summary():
    """
    Endpoint para devolver el resumen de temperatura con media y moda.
    """
    process_time_window()  # Procesar los datos al acceder al endpoint
    if not processed_data:
        return {"message": "No hay datos suficientes para generar un resumen"}
    return processed_data[-1]  # Último resumen generado

@app.get("/temperature_details")
def get_temperature_details():
    """
    Endpoint para devolver los detalles con la media y la moda de las temperaturas.
    """
    process_time_window()  # Procesar los datos al acceder al endpoint
    if not processed_data:
        return {"message": "No hay datos suficientes para generar un resumen"}
    
    # Obtener el último resumen procesado
    latest_summary = processed_data[-1]
    return {
        "average_temperature": latest_summary["average_temperature"],
        "mode_temperature": latest_summary["mode_temperature"]
    }
