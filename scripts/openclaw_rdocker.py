import websocket
import json

# Conéctate al gateway de OpenClaw
ws = websocket.create_connection("ws://127.0.0.1:18789")

# Espera el challenge
challenge = json.loads(ws.recv())
print("Challenge recibido:", challenge)

# Envía el token que acabamos de encontrar
token = "08e3a9a115f71c744981b39fd8cdd7850e6a8c8843913717"
ws.send(json.dumps({
    "type": "connect.response",
    "payload": {"token": token}
}))

# Ahora ya puedes enviar mensajes a OpenClaw
mensaje = {"type": "message", "content": "Hola OpenClaw, ¿me escuchas?"}
ws.send(json.dumps(mensaje))

# Recibir respuesta
respuesta = ws.recv()
print("Respuesta de OpenClaw:", respuesta)

ws.close()
