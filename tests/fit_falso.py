"""Gera um arquivo FIT de corrida INVENTADO (3 voltas em círculo) com a biblioteca oficial
da Garmin, só para testar. Devolve (bytes_do_fit, dados_esperados)."""
import math, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import rotas
sdk = rotas.carregar_sdk()

LAT0, LON0, RAIO_M, VOLTAS, N_GPS, N_SEM_GPS = -20.44, -54.64, 300.0, 3, 1500, 60

def criar(lat0=LAT0, lon0=LON0, raio=RAIO_M, voltas=VOLTAS, n_gps=N_GPS, n_sem=N_SEM_GPS):
    from garmin_fit_sdk import Encoder, FIT_EPOCH_S
    from garmin_fit_sdk.profile import Profile
    graus = 2 ** 31 / 180.0
    inicio = int(datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc).timestamp()) - FIT_EPOCH_S
    m = [{"mesg_num": Profile["mesg_num"]["FILE_ID"], "type": "activity", "manufacturer": "development",
          "product": 0, "time_created": inicio, "serial_number": 1}]
    kx = 111_320 * math.cos(math.radians(lat0))
    t, dist = inicio, 0.0
    for i in range(n_gps + n_sem):
        r = {"mesg_num": Profile["mesg_num"]["RECORD"], "timestamp": t, "distance": dist,
             "enhanced_speed": 3.0, "heart_rate": 150, "cadence": 85, "enhanced_altitude": 500 + (i % 20)}
        if i < n_gps:
            ang = 2 * math.pi * voltas * i / (n_gps - 1)
            r["position_lat"] = int((lat0 + raio * math.sin(ang) / 110_540) * graus)
            r["position_long"] = int((lon0 + raio * math.cos(ang) / kx) * graus)
        m.append(r)
        t += 1
        dist += 2 * math.pi * raio * voltas / n_gps
    m.append({"mesg_num": Profile["mesg_num"]["SESSION"], "message_index": 0, "timestamp": t, "start_time": inicio,
              "total_elapsed_time": t - inicio, "total_timer_time": t - inicio, "sport": "running",
              "sub_sport": "generic", "first_lap_index": 0, "num_laps": 1})
    m.append({"mesg_num": Profile["mesg_num"]["ACTIVITY"], "timestamp": t, "num_sessions": 1, "type": "manual",
              "event": "activity", "event_type": "stop"})
    e = Encoder()
    for x in m: e.write_mesg(x)
    return bytes(e.close()), {
        "com_gps": n_gps, "registros": n_gps + n_sem,
        "comprimento_m": 2 * math.pi * raio * voltas, "largura_m": 2 * raio}
