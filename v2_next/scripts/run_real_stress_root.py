import asyncio
import logging
import time
import sys
import os

# Adjust path to include backend package
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Now we can import backend services as standard packages
try:
    from backend import config
    from backend.services.plc_service import plc_service
    from backend.services.spot_service import spot_service
    from backend.services.logger_service import logger_service
    from backend.services.config_service import config_service
except ImportError:
    # If running from within backend dir, fallback
    sys.path.append(current_dir)
    import config
    from services.plc_service import plc_service
    from services.spot_service import spot_service
    from services.logger_service import logger_service
    from services.config_service import config_service

# --- CONFIG OVERRIDE FOR STRESS TEST ---
def configure_stress_mode():
    print(">>> Configuring for Real Hardware Stress Test...")
    
    # 1. Force Logging Path to Test Dir
    config.LOG_PATH = "./stress_test_logs"
    if not os.path.exists(config.LOG_PATH):
        os.makedirs(config.LOG_PATH)
    logger_service.active_log_dir = config.LOG_PATH
    
    # 2. Set Intervals to Minimum (Attempt 100Hz)
    config.PLC_INTERVAL = 0.01 
    config.SPOT_REFRESH_INTERVAL = 0.01
    
    # 3. Enable Services
    config_service.update_config("PLC_ENABLED", "true")
    config_service.update_config("SPOT_ENABLED", "true")
    config_service.update_config("AUTO_SAVE", "true")

async def run_stress_test(duration=60):
    configure_stress_mode()
    
    print(f"\n>>> Starting Services (Duration: {duration}s)...")
    
    # Start Services
    logger_service.start()
    plc_service.start()
    spot_service.start()
    
    start_time = time.time()
    
    try:
        # Monitor Loop
        while (time.time() - start_time) < duration:
            elapsed = time.time() - start_time
            print(f"Running... {elapsed:.1f}s / {duration}s", end='\r')
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("\n>>> Stopping Services...")
        plc_service.stop()
        spot_service.stop()
        logger_service.stop()
        
    print("\n>>> Test Complete.")
    print(f"Logs saved to: {os.path.abspath(config.LOG_PATH)}")

if __name__ == "__main__":
    try:
        asyncio.run(run_stress_test())
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()
    input("\nPress Enter to exit...")
