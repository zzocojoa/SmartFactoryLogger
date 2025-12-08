# modules/spot.py
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import URL_SPOT

# 세션 설정
http_session = requests.Session()
retries = Retry(total=1, backoff_factor=0, status_forcelist=[500, 502, 503, 504])
http_session.mount('http://', HTTPAdapter(max_retries=retries))

def get_spot_temp():
    try:
        r = http_session.get(URL_SPOT, timeout=0.15)
        if r.status_code == 200: 
            val = float(r.text.strip())
            if val > 2000.0: return 0.0
            return val
    except: pass
    return None
