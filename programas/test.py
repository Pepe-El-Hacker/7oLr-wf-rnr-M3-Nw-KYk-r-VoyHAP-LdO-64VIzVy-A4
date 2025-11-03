import requests
import platform
import uuid

SERVER = "http://127.0.0.1:5000"  # URL del servidor Flask
PING_EP = SERVER + "/api/ping"
REQUEST_ACTIVATION_EP = SERVER + "/api/request_activation"

def get_hwid():
    """Genera un HWID basado en MAC y nombre de host"""
    return str(uuid.getnode()) + "-" + platform.node()

def ping(hwid, program_code):
    """Verifica si la licencia está activa"""
    payload = {"hwid": hwid, "program_code": program_code}
    try:
        r = requests.post(PING_EP, json=payload, timeout=6)
        if r.status_code == 200:
            resp = r.json()
            if resp.get("authorized"):
                return True
        return False
    except Exception as e:
        print("[CLIENT] Error al hacer ping:", e)
        return False

def request_activation(hwid, program_code, note="Solicitud automática"):
    """Envía una solicitud de activación al servidor"""
    payload = {"hwid": hwid, "program_code": program_code, "note": note}
    try:
        r = requests.post(REQUEST_ACTIVATION_EP, json=payload, timeout=6)
        if r.status_code == 200:
            print("[CLIENT] Solicitud enviada correctamente")
        else:
            print(f"[CLIENT] Error solicitud {r.status_code}: {r.text}")
    except Exception as e:
        print("[CLIENT] Error al enviar solicitud:", e)

if __name__ == "__main__":
    program_code = "PROG-ABC-123"
    hwid = get_hwid()
    print(f"[CLIENT] HWID detectado: {hwid}")

    if ping(hwid, program_code):
        print("✅ Licencia autorizada")
    else:
        print("❌ Licencia no autorizada")
        request_activation(hwid, program_code)
        print("[CLIENT] Solicitud de activación enviada, espera aprobación del admin")