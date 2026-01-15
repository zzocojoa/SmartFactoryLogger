"""
MES 데이터 추출 엔진
페이지 구조 분석 결과를 기반으로 데이터 추출
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

from .constants import (
    MES_BASE_URL, 
    LOGIN_URL, 
    LOGIN_SELECTOR_ID, 
    LOGIN_SELECTOR_PW, 
    LOGIN_SELECTOR_BTN,
    DEFAULT_TIMEOUT,
    DATA_DIR,
    STRUCTURES_FILE,
    DATA_START_YEAR
)
from .config_manager import get_credentials
from .pages_registry import MES_PAGES
from .logger_config import get_logger

logger = get_logger("collector")

def load_page_structures() -> dict:
    """페이지 구조 정보 로드"""
    with open(STRUCTURES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


async def login(page, user_id: str, password: str) -> bool:
    """MES 로그인"""
    logger.info("Attempting login")
    print("LOG: 로그인 중...")
    await page.goto(LOGIN_URL)
    await page.fill(LOGIN_SELECTOR_ID, user_id)
    await page.fill(LOGIN_SELECTOR_PW, password)
    await page.click(LOGIN_SELECTOR_BTN)
    
    try:
        await page.wait_for_url("**/P00_DSH/**", timeout=10000)
        logger.info("Login successful")
        print("LOG: 로그인 성공!")
        return True
    except:
        logger.error("Login failed")
        print("ERROR: 로그인 실패")
        return False


async def extract_table_data(page, table_id: str) -> list[dict]:
    """테이블 데이터 추출"""
    data = await page.evaluate(f"""
        () => {{
            const table = document.getElementById('{table_id}');
            if (!table) return [];
            
            const rows = table.querySelectorAll('tr');
            const headers = [];
            const result = [];
            
            // 헤더 추출
            const headerRow = rows[0];
            if (headerRow) {{
                headerRow.querySelectorAll('th').forEach(th => {{
                    headers.push(th.innerText.trim().replace(/\\n/g, ' '));
                }});
            }}
            
            // 데이터 행 추출
            for (let i = 1; i < rows.length; i++) {{
                const row = rows[i];
                const cells = row.querySelectorAll('td');
                if (cells.length === 0) continue;
                
                // 전체 행 텍스트로 필터링할 패턴 체크
                const rowText = row.innerText.trim();
                
                // 페이지네이션 행 건너뛰기 (예: "1 2 3 ... of 36 Pages")
                if (rowText.includes(' of ') && rowText.includes('Pages')) continue;
                if (/^[\\d\\s]+of\\s+\\d+\\s+Pages?$/i.test(rowText)) continue;
                
                // 합계 행 건너뛰기
                const cellTexts = Array.from(cells).map(c => c.innerText.trim());
                if (cellTexts.includes('합계') || cellTexts.includes('소계')) continue;
                
                // 빈 행 건너뛰기
                const allEmpty = cellTexts.every(t => t === '' || t === '-');
                if (allEmpty) continue;
                
                const rowData = {{}};
                cells.forEach((cell, idx) => {{
                    if (headers[idx]) {{
                        // Check for input elements first
                        const input = cell.querySelector('input, textarea, select');
                        if (input && (input.value || input.innerText)) {{
                            // Prefer value, fallback to innerText for select/textarea if needed
                            rowData[headers[idx]] = (input.value || input.innerText).trim();
                        }} else {{
                            rowData[headers[idx]] = cell.innerText.trim();
                        }}
                    }}
                }});
                
                if (Object.keys(rowData).length > 0) {{
                    result.push(rowData);
                }}
            }}
            
            return result;
        }}
    """)
    return data



async def set_date_range(page, from_date: str, to_date: str, filter_fields: dict):
    """날짜 범위 설정"""
    f_date_id = filter_fields.get("from_date", "")
    t_date_id = filter_fields.get("to_date", "")
    
    if f_date_id and t_date_id:
        await page.evaluate(f"""
            () => {{
                document.getElementById('{f_date_id}').value = '{from_date}';
                document.getElementById('{t_date_id}').value = '{to_date}';
            }}
        """)
        
        # 검색 버튼 클릭
        search_btn = await page.query_selector('[id*="btnSearch"]')
        if search_btn:
            await search_btn.click()
            await page.wait_for_load_state("networkidle", timeout=30000)


async def set_year_filter(page, year: str, filter_fields: dict):
    """연도 필터 설정"""
    year_id = filter_fields.get("year_select", "")
    
    if year_id:
        await page.select_option(f"#{year_id}", year)
        await page.wait_for_load_state("networkidle", timeout=30000)


async def get_all_pages_data(page, table_id: str) -> list[dict]:
    """페이지네이션 포함 전체 데이터 추출"""
    all_data = []
    page_num = 1
    
    while True:
        # 현재 페이지 데이터 추출
        data = await extract_table_data(page, table_id)
        all_data.extend(data)
        
        # 다음 페이지 버튼 확인
        next_btn = await page.query_selector('[id*="btnNext"]')
        if not next_btn:
            break
        
        # 버튼이 비활성화되었는지 확인
        is_disabled = await next_btn.get_attribute("disabled")
        if is_disabled:
            break
        
        try:
            await next_btn.click()
            await page.wait_for_load_state("networkidle", timeout=10000)
            page_num += 1
            
            # 무한 루프 방지 (최대 100페이지)
            if page_num > 100:
                break
        except:
            break
    
    return all_data


async def extract_page_data(page, page_info: dict, year: int = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """단일 페이지 데이터 추출 (타임아웃 강화)"""
    url = f"{MES_BASE_URL}{page_info['url']}"
    start_ts = datetime.now()
    
    result = {
        "key": page_info["key"],
        "name": page_info["name"],
        "category": page_info["category"],
        "extracted_at": start_ts.isoformat(),
        "year": year,
        "data": [],
        "record_count": 0,
        "error": None,
    }
    
    try:
        # 타임아웃 상향 조정
        print(f" (Timeout: {timeout/1000}s)... ", end="", flush=True)
        await page.goto(url, timeout=timeout)
        await page.wait_for_load_state("networkidle", timeout=timeout)
        
        if not page_info["has_table"]:
            # 테이블이 없는 경우 다시 한 번 확인 (동적 로딩 대응)
            await asyncio.sleep(2)
            table_id = page_info.get("table_id")
            if table_id:
                exists = await page.evaluate(f"() => !!document.getElementById('{table_id}')")
                if not exists:
                    result["error"] = "테이블 없음"
                    return result
            else:
                result["error"] = "테이블 ID 미지정"
                return result
        
        # 필터 설정
        filter_type = page_info["filter_type"]
        filter_fields = page_info["filter_fields"]
        
        if filter_type == "date_range" and year:
            from_date = f"{year}-01-01"
            to_date = f"{year}-12-31"
            await set_date_range(page, from_date, to_date, filter_fields)
        elif filter_type == "year" and year:
            await set_year_filter(page, str(year), filter_fields)
        
        # 데이터 추출
        data = await get_all_pages_data(page, page_info["table_id"])
        result["data"] = data
        result["record_count"] = len(data)
        
        # 데이터 품질 지표: Null Ratio Check (간이 검사)
        if data:
            null_count = sum(1 for row in data for v in row.values() if not v)
            total_cells = sum(len(row) for row in data)
            null_ratio = null_count / total_cells if total_cells > 0 else 0
            
            logger.info("Data extracted", extra={
                "page": page_info["key"],
                "year": year,
                "rows": len(data),
                "null_ratio": round(null_ratio, 3)
            })
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Extraction failed for {page_info['key']}", exc_info=e)
    
    return result


async def extract_historical_data(
    page_key: str = None,
    from_year: int = 2016,
    to_year: int = 2026,
    filter_type: str = None
):
    """과거 데이터 추출 메인 함수"""
    user_id, password = get_credentials()
    structures = load_page_structures()
    
    # 필터링
    pages_to_extract = structures["pages"]
    
    if page_key:
        pages_to_extract = [p for p in pages_to_extract if p["key"] == page_key]
    
    if filter_type:
        pages_to_extract = [p for p in pages_to_extract if p["filter_type"] == filter_type]
    
    logger.info("Historical extraction started", extra={
        "page_count": len(pages_to_extract),
        "year_range": f"{from_year}-{to_year}"
    })
    print(f"LOG: {len(pages_to_extract)}개 페이지에서 데이터 추출 예정")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        if not await login(page, user_id, password):
            return
        
        for page_info in pages_to_extract:
            key = page_info["key"]
            name = page_info["name"]
            f_type = page_info["filter_type"]
            
            # 페이지별 폴더명 매핑 사용
            page_def = MES_PAGES.get(key, {})
            folder_name = page_def.get("folder_name", key)
            
            # 출력 디렉토리 생성
            output_dir = DATA_DIR / page_info["category"] / folder_name
            output_dir.mkdir(parents=True, exist_ok=True)
            
            if f_type in ["date_range", "year"]:
                # 연도별 추출
                for year in range(from_year, to_year + 1):
                    print(f"[{key}] {name} - {year}년... ", end="", flush=True)
                    
                    result = await extract_page_data(page, page_info, year)
                    
                    # 저장
                    output_file = output_dir / f"{year}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    
                    print(f"✅ {result['record_count']}건")
                    await asyncio.sleep(1)
            else:
                # 마스터 데이터 (1회 추출)
                print(f"[{key}] {name}... ", end="", flush=True)
                
                result = await extract_page_data(page, page_info)
                
                output_file = output_dir / "current.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                print(f"✅ {result['record_count']}건")
                await asyncio.sleep(0.5)
        
        await browser.close()
    
    logger.info("Historical extraction completed")
    print("\nLOG: 추출 완료!")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="MES 과거 데이터 추출")
    parser.add_argument("--page", type=str, help="특정 페이지 키 (예: rpt_press)")
    parser.add_argument("--filter", type=str, choices=["date_range", "year", "search"], 
                        help="필터 유형별 추출")
    parser.add_argument("--from-year", type=int, default=DATA_START_YEAR, help="시작 연도")
    # 동적으로 현재 연도 계산
    current_year = datetime.now().year
    parser.add_argument("--to-year", type=int, default=current_year, help="종료 연도")
    parser.add_argument("--year", type=int, help="단일 연도 지정")
    args = parser.parse_args()
    
    from_year = args.year if args.year else args.from_year
    to_year = args.year if args.year else args.to_year
    
    await extract_historical_data(
        page_key=args.page,
        from_year=from_year,
        to_year=to_year,
        filter_type=args.filter
    )


if __name__ == "__main__":
    asyncio.run(main())
