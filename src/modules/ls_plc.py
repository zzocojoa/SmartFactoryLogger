# modules/ls_plc.py
import socket
import struct
import time
from config import LS_TARGETS
from modules.schemas import LSPLCData

from modules.logger import sys_logger

class LSPLCClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.last_connect_time = 0
        self.base_retry = 1.0
        self.max_retry = 8.0
        self.retry_interval = self.base_retry
        self.connect()

    def _reset_backoff(self):
        self.retry_interval = self.base_retry

    def _increase_backoff(self):
        self.retry_interval = min(self.max_retry, max(self.base_retry, self.retry_interval * 2))
        self.last_connect_time = time.time()

    def connect(self):
        now = time.time()
        if now - self.last_connect_time < self.retry_interval: return False
        self.last_connect_time = now
        try:
            if self.sock:
                try: self.sock.close()
                except: pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(0.5)
            self.sock.connect((self.ip, self.port))
            self._reset_backoff()
            sys_logger.info(f"[PLC] Connected to {self.ip}:{self.port}")
            return True
        except Exception as e:
            self.sock = None
            self._increase_backoff()
            sys_logger.debug(f"[PLC] Connection failed: {e}")
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

    def _recv_exact(self, size):
        if not self.sock:
            return None
        data = bytearray()
        try:
            while len(data) < size:
                chunk = self.sock.recv(size - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
        except Exception:
            return None
        return bytes(data)

    def _parse_response(self, data):
        # 1. Header Validation (20 bytes)
        if len(data) < 20: 
            return None
        
        # Check 'LSIS-XGT' signature
        if data[:8] != b'LSIS-XGT':
            sys_logger.error(f"[PLC] Invalid Header Signature: {data[:8]}")
            return None
            
        # Get Body Length (Offset 16, 2 bytes)
        body_len = struct.unpack('<H', data[16:18])[0]
        
        # Validate Total Length
        if len(data) < 20 + body_len:
            sys_logger.warning(f"[PLC] Incomplete Packet: Exp {20+body_len}, Act {len(data)}")
            return None
            
        # 2. Body Parsing (Starts at offset 20)
        # Body Header: Cmd(2) + Type(2) + Res(2) + Err(2) + BlkCnt(2) = 10 bytes minimum
        body = data[20:]
        
        if len(body) < 10: return None
        
        # Error Check (Offset 6 in Body)
        error_status = struct.unpack('<H', body[6:8])[0]
        if error_status != 0:
            sys_logger.error(f"[PLC] Response Error Code: {error_status}")
            return None
            
        block_count = struct.unpack('<H', body[8:10])[0]
        
        values = []
        offset = 10 # Start of data blocks in Body
        
        for _ in range(block_count):
            if offset + 2 > len(body): break
            
            # Data Length (2 bytes)
            data_len = struct.unpack('<H', body[offset:offset+2])[0]
            offset += 2
            
            # Data Value
            if offset + data_len > len(body): break
            raw_val = body[offset:offset+data_len]
            
            # Assuming Word (2 bytes) for now as per current logic
            # Future improvement: Handle different types based on request
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
            self.sock.sendall(req)

            header = self._recv_exact(20)
            if not header:
                sys_logger.warning("[PLC] Incomplete header response.")
                self._increase_backoff()
                self.close()
                return data

            body_len = struct.unpack('<H', header[16:18])[0]
            if body_len <= 0 or body_len > 8192:
                sys_logger.warning(f"[PLC] Invalid body length: {body_len}")
                self._increase_backoff()
                self.close()
                return data

            body = self._recv_exact(body_len)
            if not body:
                sys_logger.warning("[PLC] Incomplete body response.")
                self._increase_backoff()
                self.close()
                return data

            res = header + body
            
            # 3. 응답 파싱 (값 리스트 반환)
            values = self._parse_response(res)
            if values is None:
                self._increase_backoff()
                self.close()
                return data
            
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
            
            # [Fix] Validation Logic moved INSIDE try block
            # This ensures that if validation fails (even with soft validation), exception handling runs.
            return LSPLCData(**data).dict()
                            
        except Exception as e:
            sys_logger.error(f"[PLC] Data/Validation Error: {e}")
            self._increase_backoff()
            self.close() # Reset Connection
            return data # Return default dict on error (Fail Safe)
