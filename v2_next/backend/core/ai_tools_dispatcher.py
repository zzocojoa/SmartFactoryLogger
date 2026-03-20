from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List

# 도메인별 AITool 임포트
from backend.FacilityData import ai_tools as FacilityData_AITool
from backend.MESSync import ai_tools as MESSync_AITool
from backend.Configuration import ai_tools as Configuration_AITool
from backend.Observability import ai_tools as Observability_AITool

router = APIRouter(prefix="/ai", tags=["AI_Tool_Calling"])

class ToolInvokeRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the AI tool to invoke, e.g., 'get_factory_status'")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="JSON arguments required by the specific tool schema")

@router.get(
    "/tools",
    summary="List available AI Tools",
    description="Returns a collection of JSON Schema objects describing all available backend tools for AI Agent (LLM) integration. Used by MCP servers to discover capabilities."
)
async def get_all_tools():
    """
    AI 에이전트(LLM)에게 제공할 수 있는 전체 백엔드 도구(JSON Schema) 목록을 반환합니다.
    """
    all_schemas = []
    all_schemas.extend(FacilityData_AITool.TOOLS_SCHEMA)
    all_schemas.extend(MESSync_AITool.TOOLS_SCHEMA)
    all_schemas.extend(Configuration_AITool.TOOLS_SCHEMA)
    all_schemas.extend(Observability_AITool.TOOLS_SCHEMA)
    
    return JSONResponse(content={"tools": all_schemas}, media_type="application/json; charset=utf-8")

@router.post(
    "/invoke",
    summary="Invoke an AI Tool",
    description="Executes a specific AI tool by name and arguments. Acts as a unified dispatcher across all backend domains (FacilityData, MESSync, Configuration, Observability) for Agentic workflows (Model Context Protocol)."
)
async def invoke_tool(request: ToolInvokeRequest):
    """
    AI 에이전트(LLM)가 특정 도구의 실행을 요청할 때 사용합니다.
    요청된 tool_name을 기반으로 적절한 도메인의 execute_tool을 찾아(Dispatch) 실행합니다.
    """
    name = request.tool_name
    args = request.arguments
    
    # 1. FacilityData
    for schema in FacilityData_AITool.TOOLS_SCHEMA:
        if schema["function"]["name"] == name:
            # PLC Service를 글로벌하게 주입받는 경우 여기에서 넘겨주거나 개별 모듈 내부에서 싱글톤을 씁니다.
            from backend.app import plc_service
            return {"result": FacilityData_AITool.execute_tool(name, args, plc_service)}
            
    # 2. MESSync
    for schema in MESSync_AITool.TOOLS_SCHEMA:
        if schema["function"]["name"] == name:
            return {"result": MESSync_AITool.execute_tool(name, args)}
            
    # 3. Configuration
    for schema in Configuration_AITool.TOOLS_SCHEMA:
        if schema["function"]["name"] == name:
            return {"result": Configuration_AITool.execute_tool(name, args)}
            
    # 4. Observability
    for schema in Observability_AITool.TOOLS_SCHEMA:
        if schema["function"]["name"] == name:
            return {"result": Observability_AITool.execute_tool(name, args)}
            
    raise HTTPException(status_code=404, detail=f"Tool '{name}' not found or unrecognized in any domain.")
