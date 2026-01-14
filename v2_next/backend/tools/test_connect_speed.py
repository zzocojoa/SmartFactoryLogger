
import socket
import time

EXTRUDER_IP = "192.168.10.10"
EXTRUDER_PORT = 12289

def measure_connect_speed(count=10):
    print(f"Measuring connection speed to {EXTRUDER_IP}:{EXTRUDER_PORT} ({count} times)...")
    times = []
    
    for i in range(count):
        start = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((EXTRUDER_IP, EXTRUDER_PORT))
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"[{i+1}] Connect took: {elapsed*1000:.2f} ms")
            sock.close()
        except Exception as e:
            print(f"[{i+1}] Failed: {e}")
        
    if times:
        avg = sum(times) / len(times)
        print(f"\nAverage Connect Time: {avg*1000:.2f} ms")
        print(f"Max Connect Time: {max(times)*1000:.2f} ms")
        print(f"Min Connect Time: {min(times)*1000:.2f} ms")

if __name__ == "__main__":
    measure_connect_speed(20)
