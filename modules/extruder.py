# modules/extruder.py
import socket
import time

class ExtruderClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.last_connect_time = 0
        self.retry_interval = 1.0
        self.connect()

    def connect(self):
        now = time.time()
        if now - self.last_connect_time < self.retry_interval: return False
        self.last_connect_time = now
        try:
            if self.sock:
                try: self.sock.close()
                except: pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(0.15) 
            self.sock.connect((self.ip, self.port))
            self.retry_interval = 1.0
            return True
        except:
            self.sock = None
            self.retry_interval = 3.0 # [수정] 60초 -> 3초 (빠른 재연결)
            return False

    def close(self):
        if self.sock:
            try: self.sock.close()
            except: pass
            self.sock = None

    def _read_block(self, addr_str, count):
        """ 
        주소 문자열(D0020, B1502 등)을 그대로 명령어에 사용 
        명령어: 01 + WRD + 주소 + 개수
        """
        if not self.sock: return []
        
        cmd = f"01WRD{addr_str} {count:02}\r\n".encode()
        
        try:
            self.sock.sendall(cmd)
            response = self.sock.recv(4096)
            resp_str = response.decode("ascii", errors="replace").strip()
            
            if "OK" in resp_str:
                data_part = resp_str.split("OK")[1]
                values = []
                for i in range(0, len(data_part), 4):
                    hex_val = data_part[i:i+4]
                    if len(hex_val) == 4:
                        try: values.append(int(hex_val, 16))
                        except: values.append(0)
                return values
        except Exception:
            self.close()
        return []

    def get_data(self):
        data = {"Press": None, "Temp_F": None, "Temp_B": None, "Speed": None, "EndPos": None, "Count": None, "Billet": None}
        if self.sock is None:
            if not self.connect(): return data

        try:
            # 1. [D0020~] 압력, 온도 (20개 읽기)
            # D23=idx3(압력), D31=idx11(온도앞), D32=idx12(온도뒤)
            b1 = self._read_block("D0020", 20)
            if len(b1) > 14:
                data["Press"]  = b1[3] / 10.0
                data["Temp_F"] = b1[11]
                data["Temp_B"] = b1[12]
            elif self.sock is None: return data

            # 2. [B1502~] 속도 (B영역 읽기)
            b_speed = self._read_block("B1502", 1)
            if len(b_speed) > 0:
                data["Speed"] = b_speed[0] / 10.0

            # 3. [D0420~] 종료위치
            b2 = self._read_block("D0420", 10)
            if len(b2) > 1: data["EndPos"] = b2[1] / 10.0

            # 4. [D1500~] 카운터
            b3 = self._read_block("D1500", 20)
            if len(b3) > 10: data["Count"] = b3[10]

            # 5. [D1900~] 빌렛길이
            b4 = self._read_block("D1900", 20)
            if len(b4) > 10: data["Billet"] = b4[11]

        except Exception:
            self.close()
        return data
