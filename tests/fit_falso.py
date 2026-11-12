"""Gera um arquivo FIT de corrida INVENTADO (3 voltas em círculo) com a biblioteca oficial
da Garmin, só para testar. Devolve (bytes_do_fit, dados_esperados)."""
import math, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import rotas
sdk = rotas.carregar_sdk()

LAT0, LON0, RAIO_M, VOLTAS, N_GPS, N_SEM_GPS = -20.44, -54.64, 300.0, 3, 1500, 60

def criar():
    from garmin_fit_sdk import Encoder, FIT_EPOCH_S
    from garmin_fit_sdk.profile import Profile
    graus = 2 ** 31 / 180.0
    inicio = int(datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc).timestamp()) - FIT_EPOCH_S
    m = [{"mesg_num": Profile["mesg_num"]["FILE_ID"], "type": "activity", "manufacturer": "development",
          "product": 0, "time_created": inicio, "serial_number": 1}]
    kx = 111_320 * math.cos(math.radians(LAT0))
    t, dist = inicio, 0.0
    for i in range(N_GPS + N_SEM_GPS):
        r = {"mesg_num": Profile["mesg_num"]["RECORD"], "timestamp": t, "distance": dist,
             "enhanced_speed": 3.0, "heart_rate": 150, "cadence": 85, "enhanced_altitude": 500 + (i % 20)}
        if i < N_GPS:
            ang = 2 * math.pi * VOLTAS * i / (N_GPS - 1)
            r["position_lat"] = int((LAT0 + RAIO_M * math.sin(ang) / 110_540) * graus)
            r["position_long"] = int((LON0 + RAIO_M * math.cos(ang) / kx) * graus)
        m.append(r)
        t += 1
        dist += 2 * math.pi * RAIO_M * VOLTAS / N_GPS
    m.append({"mesg_num": Profile["mesg_num"]["SESSION"], "message_index": 0, "timestamp": t, "start_time": inicio,
              "total_elapsed_time": t - inicio, "total_timer_time": t - inicio, "sport": "running",
              "sub_sport": "generic", "first_lap_index": 0, "num_laps": 1})
    m.append({"mesg_num": Profile["mesg_num"]["ACTIVITY"], "timestamp": t, "num_sessions": 1, "type": "manual",
              "event": "activity", "event_type": "stop"})
    e = Encoder()
    for x in m: e.on_mesg(x["mesg_num"], x) if False else e.write_mesg(x)
    return bytes(e.close()), {
        "com_gps": N_GPS, "registros": N_GPS + N_SEM_GPS,
        "comprimento_m": 2 * math.pi * RAIO_M * VOLTAS, "largura_m": 2 * RAIO_M}
