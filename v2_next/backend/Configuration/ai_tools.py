from typing import Dict, Any, List
from backend.Configuration.service import get_config_snapshot, update_config
from backend.Configuration.Configuration_Structure import ConfigUpdate

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_system_config",
            "description": "서버의 현재 시스템 설정(수집 주기, 로그 회전 주기, 백오프 정책 등)을 조회합니다.",
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
            "name": "update_system_config",
            "description": "서버의 시스템 설정을 변경합니다. 변경 후 재시작이 필요할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "setting_key": {
                        "type": "string",
                        "description": "변경할 설정 키 (예: 'plc_target_ip', 'collect_interval_ms')"
                    },
                    "setting_value": {
                        "type": "string",
                        "description": "변경할 새로운 값 (숫자 타입이더라도 문자로 전달)"
                    }
                },
                "required": ["setting_key", "setting_value"]
            }
        }
    }
]

def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """
    Configuration 도메인의 도구를 실행합니다.
    """
    if name == "get_system_config":
        return get_config_snapshot().model_dump()
        
    elif name == "update_system_config":
        key = args.get("setting_key")
        val = args.get("setting_value")
        # For AI tool calling, we might only allow updating certain easy parameters or returning an info statement
        return {"status": "info", "message": f"Requested config update {key}={val}. Central Config overriding is managed via UI currently. API support for direct updates is limited."}
    
    return {"error": f"Unknown tool name: {name}"}
