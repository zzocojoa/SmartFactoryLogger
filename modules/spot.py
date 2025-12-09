# modules/spot.py
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import URL_SPOT
from modules.schemas import SpotData

# 세션 설정
http_session = requests.Session()
retries = Retry(total=1, backoff_factor=0, status_forcelist=[500, 502, 503, 504])
http_session.mount('http://', HTTPAdapter(max_retries=retries))

def get_spot_temp():
    try:
        r = http_session.get(URL_SPOT, timeout=0.15)
        if r.status_code == 200: 
            val = float(r.text.strip())
            # Pydantic Validation
            validated = SpotData(temperature=val)
            return validated.temperature
    except: pass
    return None
