from typing import Dict, Any, List
from backend.Observability.service import observability_service

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
    },
    {
        "type": "function",
        "function": {
            "name": "search_system_logs",
            "description": "시스템 내부의 JSONL 로그 파일들을 검색합니다. 에러 추적이나 통신 지연 확인 등에 유용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "log_type": {
                        "type": "string",
                        "enum": ["app", "crash", "comm", "mes"],
                        "description": "검색할 로그의 종류"
                    },
                    "level": {
                        "type": "string",
                        "description": "로그 레벨 필터링 (예: ERROR, WARNING, INFO)"
                    },
                    "trace_id": {
                        "type": "string",
                        "description": "특정 요청의 Trace ID 필터링"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "가져올 최대 로그 개수 (기본 50)",
                        "default": 50
                    }
                },
                "required": ["log_type"]
            }
        }
    }
]

import os
import json
from backend import config

def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """
    Observability 도메인의 도구를 실행합니다.
    """
    if name == "get_system_health":
        try:
            health_data = observability_service.get_stats()
            return health_data
        except Exception as e:
            return {"error": f"Failed to get system health: {str(e)}"}
            
    if name == "search_system_logs":
        try:
            log_type = args.get("log_type", "app")
            level = args.get("level")
            trace_id = args.get("trace_id")
            limit = args.get("limit", 50)
            
            # Determine path
            from pathlib import Path
            if log_type == "app":
                # Fallback location search logic can be refined
                log_path = Path(config.APP_DATA_DIR) / "logs" / "system" / "system.log"
            elif log_type == "crash":
                log_path = Path(config.APP_DATA_DIR) / "logs" / "system" / "crash.log"
            elif log_type == "comm":
                log_path = Path(config.APP_DATA_DIR) / "logs" / "comm" / "comm_metrics.log"
            elif log_type == "mes":
                log_path = Path(config.APP_DATA_DIR) / "logs" / "system" / "mes_application.log"
            else:
                return {"error": f"Unknown log type: {log_type}"}
                
            if not log_path.exists():
                return {"error": f"Log file not found at {log_path}"}
                
            results = []
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if level and record.get("levelname", record.get("level")) != level:
                        continue
                    if trace_id and record.get("trace_id") != trace_id:
                        continue
                    results.append(record)
                    if len(results) >= limit:
                        break
                except json.JSONDecodeError:
                    # Ignore non-JSON lines during transition
                    continue
                    
            return {"logs": results}
        except Exception as e:
            return {"error": f"Failed to search logs: {str(e)}"}
            
    return {"error": f"Unknown tool name: {name}"}
