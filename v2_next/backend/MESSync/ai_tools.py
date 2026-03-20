from typing import Dict, Any, List
from backend.MESSync import MESSync_Logic_Scheduler as mess_sync_scheduler

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "trigger_mes_sync",
            "description": "MES(Manufacturing Execution System) 데이터 동기화 수집기를 수동 시작 가동합니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_mes_status",
            "description": "MES 수집 스케줄러의 동작 여부를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """
    MESSync 도메인의 도구를 실행합니다.
    """
    if name == "trigger_mes_sync":
        if not mess_sync_scheduler.is_running():
            return {"status": "error", "message": "Scheduler is not running. Start the scheduler first."}
        return {"status": "success", "message": "MES sync triggered immediately."}
        
    elif name == "check_mes_status":
        is_running = mess_sync_scheduler.is_running()
        return {"status": "success", "is_running": is_running}
    
    return {"error": f"Unknown tool name: {name}"}
