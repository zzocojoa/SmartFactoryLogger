# modules/ls_plc.py
import socket
import struct
import time
from config import LS_TARGETS
from modules.schemas import LSPLCData

class LSPLCClient:
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
            self.sock.settimeout(0.5)
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

    def _create_packet(self, var_names):
        # [수정] 다중 변수 읽기 (Multi-variable Read)
        # var_names: list of strings (e.g., ["%DW250", "%DW256", ...])
        
        body = bytearray()
        body += b'\x54\x00'             # Command: 0x0054 (개별 읽기)
        body += b'\x02\x00'             # DataType: Word (0x0002)
        body += b'\x00\x00'             # Reserved
        body += struct.pack('<H', len(var_names)) # Block Count: N개
        
        for name in var_names:
            var_bytes = name.encode('ascii')
            body += struct.pack('<H', len(var_bytes))
            body += var_bytes
        
        body_len = len(body)
        header = bytearray()
        header += b'LSIS-XGT'
        header += b'\x00\x00' * 2
        header += b'\xA0\x33\x00\x01'
        header += struct.pack('<H', body_len)
        header += b'\x00\x00'
        
        return header + body

    def _parse_response(self, data):
        # Header(20) + Cmd(2) + Type(2) + Res(2) + Err(2) + BlkCnt(2) = 30 bytes minimum
        if len(data) < 30: return None
        
        error_status = struct.unpack('<H', data[26:28])[0]
        if error_status != 0: return None
        
        block_count = struct.unpack('<H', data[28:30])[0]
        
        values = []
        offset = 30
        
        for _ in range(block_count):
            if offset + 2 > len(data): break
            data_len = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            
            if offset + data_len > len(data): break
            raw_val = data[offset:offset+data_len]
            
            if len(raw_val) == 2:
                val = struct.unpack('<H', raw_val)[0]
                values.append(val)
            else:
                values.append(None)
                
            offset += data_len
            
        return values

    def get_data(self):
        # 초기화
        data = {name: None for _, name in LS_TARGETS}
        
        if self.sock is None:
            if not self.connect(): return data

        try:
            # 1. 모든 주소를 리스트로 추출
            addr_list = [addr for addr, _ in LS_TARGETS]
            
            # 2. 한 번의 패킷으로 모든 데이터 요청 (Multi-read)
            req = self._create_packet(addr_list)
            self.sock.send(req)
            res = self.sock.recv(4096)
            
            # 3. 응답 파싱 (값 리스트 반환)
            values = self._parse_response(res)
            
            # 4. 결과 매핑
            if values and len(values) == len(LS_TARGETS):
                for i, (addr, name) in enumerate(LS_TARGETS):
                    val = values[i]
                    if val is not None:
                        # 단위 변환 (온도/습도 값은 1/100)
                        if name in ["At_Temp", "At_Pre"]:
                            data[name] = val / 100.0
                        else:
                            data[name] = val
                            
        except Exception:
            self.close()
            
        return LSPLCData(**data).dict()
