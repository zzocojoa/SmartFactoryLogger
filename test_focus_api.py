from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import threading
import time

PORT = 8080
current_focus = 500

class MockSpotHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global current_focus
        if self.path == "/control?p=focus":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(current_focus).encode())
        else:
            self.send_response(404)
            self.end_headers()
            
    def do_PUT(self):
        global current_focus
        if self.path == "/control?p=focus":
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            current_focus = int(body)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body) # Echo back as per API
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server = HTTPServer(('localhost', PORT), MockSpotHandler)
    print(f"Mock Server running on port {PORT}")
    server.serve_forever()

if __name__ == "__main__":
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    
    time.sleep(1)
    
    # Test Client
    import urllib.request
    
    # 1. Read
    with urllib.request.urlopen(f"http://localhost:{PORT}/control?p=focus") as f:
        print(f"Initial Focus: {f.read().decode()}")
        
    # 2. Write
    req = urllib.request.Request(f"http://localhost:{PORT}/control?p=focus", data=b"600", method='PUT')
    with urllib.request.urlopen(req) as f:
        print(f"Set Focus Response: {f.read().decode()}")
        
    # 3. Read again
    with urllib.request.urlopen(f"http://localhost:{PORT}/control?p=focus") as f:
        print(f"Updated Focus: {f.read().decode()}")
        
    print("Test Complete")
