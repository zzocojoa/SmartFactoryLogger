from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Import Service Layer
from .services.plc_service import plc_service
from .services import spot_control
from .models.data_model import FactoryData
from . import config

# Lifecycle Manager (Startup/Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[Main] Starting PLC Service...")
    plc_service.start()
    yield
    # Shutdown
    print("[Main] Stopping PLC Service...")
    plc_service.stop()

# --- App Definition ---
app = FastAPI(
    title="Smart Factory Logger V2 API",
    description="Backend API for Smart Factory Logger V2 (Web Tech)",
    version="2.1.0",
    lifespan=lifespan
)

# CORS (Allow Frontend Access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "system": "Smart Factory Logger V2",
        "status": "Online",
        "backend": "FastAPI with Service Layer"
    }

@app.get("/api/data", response_model=FactoryData)
def get_data():
    """Get latest snapshot from PLC Service (Memory)"""
    return plc_service.get_latest_data()

@app.get("/health")
def health():
    return plc_service.get_health()

@app.get("/api/spot/config")
def spot_config():
    return {
        "image_url": config.SPOT_IMAGE_URL,
        "refresh_interval": config.SPOT_REFRESH_INTERVAL,
        "crosshair_x": config.SPOT_CROSSHAIR_X,
        "crosshair_y": config.SPOT_CROSSHAIR_Y,
        "crosshair_color": config.SPOT_CROSSHAIR_COLOR,
        "crosshair_thickness": config.SPOT_CROSSHAIR_THICKNESS,
        "crosshair_size": config.SPOT_CROSSHAIR_SIZE,
        "crosshair_gap": config.SPOT_CROSSHAIR_GAP,
        "widget_width": config.SPOT_WIDGET_WIDTH,
        "widget_height": config.SPOT_WIDGET_HEIGHT,
        "focus_step": config.SPOT_ACTUATOR_STEP,
        "focus_enabled": bool(config.SPOT_ACTUATOR_URL),
    }

@app.post("/api/spot/focus")
def spot_focus(steps: int = 0):
    try:
        return spot_control.move_focus(steps)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)

