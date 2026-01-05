import socket
import os

def check_net():
    print("--- Hostname and IPs ---")
    hostname = socket.gethostname()
    print(f"Hostname: {hostname}")
    try:
        ips = socket.gethostbyname_ex(hostname)[2]
        for ip in ips:
            print(f"Detected IP: {ip}")
    except:
        pass

    print("\n--- Port 8000 Scan ---")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Check if something is already bound to 0.0.0.0:8000
        result = s.connect_ex(('127.0.0.1', 8000))
        if result == 0:
            print("Port 8000: SOMETHING IS LISTENING (Found at 127.0.0.1)")
        else:
            print("Port 8000: NOTHING LISTENING on 127.0.0.1")
            
        result_lan = s.connect_ex(('192.168.0.115', 8000))
        if result_lan == 0:
            print("Port 8000: SOMETHING IS LISTENING (Found at 192.168.0.115)")
        else:
            print("Port 8000: NOTHING LISTENING on 192.168.0.115")
    finally:
        s.close()

if __name__ == "__main__":
    check_net()
