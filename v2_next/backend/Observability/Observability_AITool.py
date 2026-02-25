from typing import Dict, Any, List
from backend.Observability.Observability_Logic_Service import observability_service

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_system_health",
            "description": "SmartFactory 백엔드가 구동 중인 서버의 측정 지표, 리퀘스트 및 에러 스탯 등 네트워크 리소스 상태를 반환합니다.",
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
    Observability 도메인의 도구를 실행합니다.
    """
    if name == "get_system_health":
        try:
            health_data = observability_service.get_stats()
            # return as-is since get_stats returns a dict
            return health_data
        except Exception as e:
            return {"error": f"Failed to get system health: {str(e)}"}
            
    return {"error": f"Unknown tool name: {name}"}
