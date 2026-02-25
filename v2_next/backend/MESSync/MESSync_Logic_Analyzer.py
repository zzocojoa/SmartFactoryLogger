"""
MES 페이지 구조 자동 탐지기
각 페이지를 방문하여 테이블 구조, 필터 유형 등을 자동으로 분석
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

from .MESSync_Constants import (
    MES_BASE_URL, 
    LOGIN_URL, 
    LOGIN_SELECTOR_ID, 
    LOGIN_SELECTOR_PW, 
    LOGIN_SELECTOR_BTN,
    DEFAULT_TIMEOUT,
    LONG_TIMEOUT,
    IGNORE_PAGES,
    STRUCTURES_FILE
)
from .MESSync_Config import get_credentials
from .MESSync_Logger import get_logger

logger = get_logger("page_analyzer")

async def login(page, user_id: str, password: str) -> bool:
    """MES 로그인"""
    logger.info("Login started")
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


async def analyze_page(page, page_key: str, page_info: dict) -> dict:
    """단일 페이지 구조 분석"""
    url = f"{MES_BASE_URL}{page_info['url']}"
    result = {
        "key": page_key,
        "name": page_info["name"],
        "category": page_info["category"],
        "url": page_info["url"],
        "has_table": False,
        "table_id": None,
        "columns": [],
        "filter_type": "none",  # none, date_range, year, month
        "filter_fields": {},
        "has_pagination": False,
        "error": None,
    }
    
    try:
        await page.goto(url, timeout=LONG_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT)
        
        # 테이블 존재 여부 확인
        table_info = await page.evaluate("""
            () => {
                // gv_Board 테이블 찾기
                const table = document.querySelector('table[id*="gv_Board"]');
                if (!table) return null;
                
                // Use table.rows for consistency with collector
                const rows = Array.from(table.rows);
                
                // 헤더 추출
                const headers = [];
                const headerRow = rows[0]; // Assuming first row is header
                if (headerRow) {
                    headerRow.querySelectorAll('th').forEach(th => {
                        headers.push(th.innerText.trim().replace(/\\n/g, ' '));
                    });
                }
                
                return {
                    id: table.id,
                    columnCount: headers.length,
                    headers: headers,
                    rowCount: Math.max(0, rows.length - 1)  // 헤더 제외
                };
            }
        """)
        
        if table_info:
            result["has_table"] = True
            result["table_id"] = table_info["id"]
            result["columns"] = table_info["headers"]
        
        # 필터 유형 탐지
        filter_info = await page.evaluate("""
            () => {
                const filters = {};
                
                // 날짜 범위 필터 (From ~ To)
                const fDate = document.querySelector('input[id*="txt_FDate"]');
                const tDate = document.querySelector('input[id*="txt_TDate"]');
                if (fDate && tDate) {
                    filters.type = 'date_range';
                    filters.fields = {
                        from_date: fDate.id,
                        to_date: tDate.id
                    };
                    return filters;
                }
                
                // 연도 선택 필터
                const yearSelect = document.querySelector('select[id*="dd_Srch1"]');
                if (yearSelect) {
                    const options = Array.from(yearSelect.options).map(o => o.value);
                    filters.type = 'year';
                    filters.fields = {
                        year_select: yearSelect.id,
                        available_years: options
                    };
                    return filters;
                }
                
                // 월 선택 필터
                const monthSelect = document.querySelector('select[id*="dd_Srch2"]');
                if (monthSelect) {
                    filters.type = 'year_month';
                    filters.fields = {
                        month_select: monthSelect.id
                    };
                    return filters;
                }
                
                // 기타 검색 필드
                const searchBtn = document.querySelector('input[id*="btnSearch"], a[id*="btnSearch"]');
                if (searchBtn) {
                    filters.type = 'search';
                    filters.fields = {
                        search_button: searchBtn.id
                    };
                    return filters;
                }
                
                filters.type = 'none';
                return filters;
            }
        """)
        
        result["filter_type"] = filter_info.get("type", "none")
        result["filter_fields"] = filter_info.get("fields", {})
        
        # 페이지네이션 확인
        has_pagination = await page.evaluate("""
            () => {
                const pager = document.querySelector('[id*="DDLPage"], [id*="btnNext"]');
                return pager !== null;
            }
        """)
        result["has_pagination"] = has_pagination
        
        logger.info("Page analyzed", extra={
            "page": page_key,
            "has_table": result["has_table"],
            "filter": result["filter_type"],
            "cols": len(result["columns"])
        })
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Analysis failed for {page_key}", exc_info=e)
    
    return result


async def analyze_all_pages(sample_size: int = None):
    """모든 페이지 분석"""
    from backend.MESSync.MESSync_Structure import MES_PAGES
    
    user_id, password = get_credentials()
    results = []
    
    # 출력 디렉토리 생성
    STRUCTURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 로그인
        if not await login(page, user_id, password):
            return
        
        # 페이지 목록
        pages_to_analyze = list(MES_PAGES.items())
        if sample_size:
            pages_to_analyze = pages_to_analyze[:sample_size]
        
        total = len(pages_to_analyze)
        logger.info("Starting analysis", extra={"total_pages": total})
        print(f"\nLOG: {total}개 페이지 분석 시작...\n")
        
        for idx, (key, info) in enumerate(pages_to_analyze, 1):
            if key in IGNORE_PAGES:
                print(f"[{idx}/{total}] {info['name']} ({info['url']})... ⏭️ SKIP (Ignore List)")
                continue

            print(f"[{idx}/{total}] {info['name']} ({info['url']})... ", end="", flush=True)
            
            result = await analyze_page(page, key, info)
            results.append(result)
            
            if result["error"]:
                print(f"❌ {result['error'][:30]}")
            elif result["has_table"]:
                print(f"✅ 테이블 {len(result['columns'])}컬럼, 필터: {result['filter_type']}")
            else:
                print(f"⚠️ 테이블 없음, 필터: {result['filter_type']}")
            
            # 잠시 대기 (서버 부담 방지)
            await asyncio.sleep(0.5)
        
        await browser.close()
    
    # 결과 저장
    output = {
        "analyzed_at": datetime.now().isoformat(),
        "total_pages": len(results),
        "summary": {
            "with_table": sum(1 for r in results if r["has_table"]),
            "date_range_filter": sum(1 for r in results if r["filter_type"] == "date_range"),
            "year_filter": sum(1 for r in results if r["filter_type"] == "year"),
            "no_filter": sum(1 for r in results if r["filter_type"] == "none"),
        },
        "pages": results
    }
    
    with open(STRUCTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info("Analysis completed", extra=output["summary"])
    
    print(f"\n{'='*50}")
    print(f"분석 완료! 결과: {STRUCTURES_FILE}")
    print(f"  - 테이블 있는 페이지: {output['summary']['with_table']}")
    print(f"  - 날짜범위 필터: {output['summary']['date_range_filter']}")
    print(f"  - 연도 필터: {output['summary']['year_filter']}")
    print(f"  - 필터 없음: {output['summary']['no_filter']}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="MES 페이지 구조 분석")
    parser.add_argument("--sample", type=int, help="샘플 페이지 수 (기본: 전체)")
    args = parser.parse_args()
    
    await analyze_all_pages(sample_size=args.sample)


if __name__ == "__main__":
    asyncio.run(main())
