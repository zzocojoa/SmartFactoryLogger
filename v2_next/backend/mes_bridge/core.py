"""
MES Core Data Collector
"MES 수집 -> JSON 저장"의 핵심 로직만 정제한 모듈입니다.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

from .constants import (
    MES_BASE_URL, 
    LOGIN_URL, 
    LOGIN_SELECTOR_ID, 
    LOGIN_SELECTOR_PW, 
    LOGIN_SELECTOR_BTN,
    DEFAULT_TIMEOUT,
    LONG_TIMEOUT,
    DATA_DIR
)
from .config_manager import get_credentials

class MESCollector:
    def __init__(self, output_dir=None):
        self.base_url = MES_BASE_URL
        user_id, password = get_credentials()
        self.user_id = user_id
        self.password = password
        self.output_dir = Path(output_dir) if output_dir else DATA_DIR
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        """브라우저 시작 및 로그인"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        
        # 로그인
        await self.page.goto(LOGIN_URL)
        await self.page.fill(LOGIN_SELECTOR_ID, self.user_id)
        await self.page.fill(LOGIN_SELECTOR_PW, self.password)
        await self.page.click(LOGIN_SELECTOR_BTN)
        await self.page.wait_for_url("**/P00_DSH/**", timeout=DEFAULT_TIMEOUT)
        print("Logged in successfully")

    async def stop(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def collect(self, page_info, year=None):
        """특정 페이지 수집 및 저장"""
        key = page_info['key']
        cat = page_info['category']
        # Use folder_name from registry if available, else key (fallback)
        folder_name = page_info.get('folder_name', key)
        table_id = page_info.get('table_id') # Handle missing table_id gracefully if needed
        
        if not table_id:
             print(f"Skipping {key}: No table_id defined")
             return 0
        
        # 1. 페이지 이동
        await self.page.goto(f"{self.base_url}{page_info['url']}", timeout=LONG_TIMEOUT)
        await self.page.wait_for_load_state("networkidle")

        # 2. 필터 설정 (날짜/연도)
        if page_info['filter_type'] == "date_range" and year:
            await self.page.evaluate(f"""() => {{
                document.getElementById('{page_info['filter_fields']['from_date']}').value = '{year}-01-01';
                document.getElementById('{page_info['filter_fields']['to_date']}').value = '{year}-12-31';
            }}""")
            await self.page.click('[id*="btnSearch"]')
            await self.page.wait_for_load_state("networkidle")
        elif page_info['filter_type'] == "year" and year:
            await self.page.select_option(f"#{page_info['filter_fields']['year_select']}", str(year))
            await self.page.wait_for_load_state("networkidle")

        # 3. 데이터 추출 (페이지네이션 포함)
        all_data = []
        while True:
            # 현재 테이블 파싱 (JS Evaluate)
            page_data = await self.page.evaluate(f"""(tid) => {{
                const table = document.getElementById(tid);
                if (!table) return [];
                const rows = Array.from(table.querySelectorAll('tr'));
                const headers = Array.from(rows[0].querySelectorAll('th')).map(th => th.innerText.trim());
                return rows.slice(1).map(row => {{
                    const cells = Array.from(row.querySelectorAll('td'));
                    if (cells.some(c => c.innerText.includes('합계') || c.innerText.includes('소계'))) return null;
                    const d = {{}};
                    cells.forEach((c, i) => {{ if(headers[i]) d[headers[i]] = c.innerText.trim(); }});
                    return d;
                }}).filter(x => x !== null);
            }}""", table_id)
            all_data.extend(page_data)

            # 다음 페이지 이동
            next_btn = await self.page.query_selector('[id*="btnNext"]')
            if next_btn and not await next_btn.get_attribute("disabled"):
                await next_btn.click()
                await self.page.wait_for_load_state("networkidle")
            else:
                break

        # 4. JSON 저장
        result = {
            "metadata": {
                "collected_at": datetime.now().isoformat(),
                "year": year,
                "page": page_info['name']
            },
            "record_count": len(all_data),
            "data": all_data
        }
        
        # Use centralized folder naming logic
        save_dir = self.output_dir / cat / folder_name
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{year if year else 'current'}.json"
        
        with open(save_dir / filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        return len(all_data)
