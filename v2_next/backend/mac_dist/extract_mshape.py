"""
MShape (금형번호 등록) 추출 및 파일 다운로드 스크립트
[Feature] 상세 페이지 진입 후 PDF/파일 다운로드 추가
Usage (Mac):
    cd mac_dist
    source venv/bin/activate
    python extract_mshape.py
"""

import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright
import configparser

# =============================================================================
# Configuration
# =============================================================================
MES_BASE_URL = "https://dmc.mescloud.net"
LOGIN_URL = f"{MES_BASE_URL}/Default.aspx"
MSHAPE_URL = f"{MES_BASE_URL}/P50_QLT/MShape.aspx"

DEFAULT_TIMEOUT = 30000
LONG_TIMEOUT = 60000

OUTPUT_DIR = Path("mes_data/금형/금형번호_등록")
FILES_DIR = OUTPUT_DIR / "files"


def get_credentials():
    """Get credentials from config.ini"""
    config_path = Path("config.ini")
    if not config_path.exists():
        print("❌ config.ini 파일이 없습니다!")
        return "", ""
    
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8-sig")
    
    return config.get("MES", "userid", fallback=""), config.get("MES", "password", fallback="")


async def login(page, user_id: str, password: str) -> bool:
    """Login to MES"""
    await page.goto(LOGIN_URL, timeout=LONG_TIMEOUT)
    await page.wait_for_load_state("networkidle")
    
    # Check if already logged in
    if "LogOut" in await page.content():
        print("✅ 이미 로그인되어 있습니다.")
        return True

    await page.fill("#txt_userId", user_id)
    await page.fill("#txt_userPw", password)
    await page.click("#btnLogin")
    
    await page.wait_for_load_state("networkidle", timeout=LONG_TIMEOUT)
    
    if "Default.aspx" in page.url and "LogOut" not in await page.content():
         # Sometimes default.aspx is the login page
         if await page.query_selector("#txt_userId"):
             print("❌ 로그인 실패")
             return False
    
    print("✅ 로그인 성공")
    return True


async def download_attachment(page, mold_no):
    """Detail page: Find and download attachment"""
    downloaded_file = None
    
    try:
        # Look for typical attachment links
        # Strategy: Look for A tags with href containing 'download' or file extensions
        # Or typical 'btnDownload', 'lnKFile' IDs
        
        # Adjust selector based on common MES patterns or specific page inspection
        # Assuming there might be a file link. 
        # We will try to find a link that looks like a file.
        
        # 1. Wait for detail load
        await page.wait_for_load_state("domcontentloaded")
        
        # Potential file selectors
        file_selectors = [
            'a[href*="Download"]',
            'a[href*=".pdf"]', 
            'a[href*=".jpg"]',
            'a[id*="lnkFile"]',
            'a[id*="File"]'
        ]
        
        target_link = None
        for sel in file_selectors:
            target_link = await page.query_selector(sel)
            if target_link:
                break
        
        if target_link:
            # Setup download handler
            async with page.expect_download(timeout=10000) as download_info:
                await target_link.click()
            
            download = await download_info.value
            
            # Save file
            # Sanitize filename
            original_name = download.suggested_filename
            ext = Path(original_name).suffix
            safe_mold_no = re.sub(r'[\\/*?:"<>|]', "", mold_no)
            save_name = f"{safe_mold_no}_{original_name}"
            save_path = FILES_DIR / save_name
            
            await download.save_as(save_path)
            downloaded_file = str(save_name)
            # print(f"      📥 다운로드: {save_name}")
            
    except Exception as e:
        # print(f"      ⚠️ 파일 다운로드 실패/없음: {e}")
        pass
        
    return downloaded_file


async def extract_mshape(page) -> dict:
    """Extract MShape data with pagination and Detail Page visiting"""
    print(f"\n📄 MShape.aspx 페이지 추출 및 파일 다운로드 시작...")
    print(f"   저장 경로: {FILES_DIR}")
    
    # Create files dir
    FILES_DIR.mkdir(parents=True, exist_ok=True)

    result = {
        "key": "m_shape",
        "name": "금형번호 등록",
        "category": "금형",
        "collected_at": datetime.now().isoformat(),
        "data": [],
        "record_count": 0,
        "total_count": 0,
        "error": None,
    }
    
    try:
        # 1. Navigate to MShape
        await page.goto(MSHAPE_URL, timeout=LONG_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=20000)
        
        # 2. Extract total count
        try:
            total_count = await page.evaluate("""() => {
                const span = document.getElementById('ctl00_BodyHolder_lbl_ListCnt');
                if (!span) return 0;
                const match = span.innerText.match(/([\\d,]+)/);
                return match ? parseInt(match[1].replace(/,/g, '')) : 0;
            }""")
            result["total_count"] = total_count
            print(f"   총 건수: {total_count:,}건 (상세 방문으로 인해 시간이 소요됩니다)")
        except:
            print("   총 건수 추출 실패")

        # 3. Set page rows to 100
        has_100 = await page.evaluate("""() => {
            const select = document.getElementById('ctl00_BodyHolder_ddl_PageRow');
            if (!select) return false;
            return Array.from(select.options).some(opt => opt.value === '100');
        }""")
        
        if has_100:
            print("   페이지 행 수: 100으로 설정...")
            await page.select_option('#ctl00_BodyHolder_ddl_PageRow', value="100")
            search_btn = await page.query_selector('[id*="btnSearch"]')
            if search_btn:
                await search_btn.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(2)
        
        # 4. Extract data
        all_data = []
        page_num = 1
        last_raw_data = None
        
        while True:
            print(f"   [Page {page_num}] 처리 중...", end="", flush=True)
            
            # 4-1. Get Row Count First
            rows = await page.query_selector_all('#ctl00_BodyHolder_gv_Board tr')
            # Skip header and pager
            valid_rows = []
            for i, tr in enumerate(rows):
                # Simple heuristic: skip first row (header)
                if i == 0: continue
                # Skip pager
                text = await tr.inner_text()
                if "Pages" in text and "of" in text: continue
                
                valid_rows.append(tr)
            
            print(f" {len(valid_rows)}개 항목")
            
            # 4-2. Iterate Rows for Detail
            page_data = []
            
            # We need to re-query rows in loop because DOM updates on back? 
            # Actually, if we go back, we need to ensure we are on the same page.
            # Going 'Back' handling in SPA/ASP.NET can be tricky.
            # Safer way: Open detail in NEW TAB if possible, or Handle Back carefully.
            # ASP.NET links often use 'javascript:__doPostBack' which fails in new tab.
            # So we must use Single Tab + Back.
            
            # Issue: 'Back' might reset pagination or page size?
            # ASP.NET ViewState usually keeps it, but not guaranteed.
            # Let's verify: If we click item, then back, are we still on Page X with 100 items?
            # Usually yes.
            
            for i in range(len(valid_rows)):
                # Re-select row to avoid stale element
                # Note: valid_rows indices map to (i+1) in actual table typically
                # Using nth-child logic
                
                # Careful: The row index might shift if we don't exclude header correctly in selector
                # selector: #ctl00_BodyHolder_gv_Board tr:nth-child(i + 2)  (1-based, +1 for header)
                
                row_idx = i + 2 
                row_sel = f'#ctl00_BodyHolder_gv_Board tr:nth-child({row_idx})'
                
                # Extract basic data first
                # We can do this with evaluate for speed for the whole table, but we need to mix it.
                # Let's just grab text here.
                try:
                    mold_no_el = await page.query_selector(f'{row_sel} td:nth-child(1)') # Adjust index if needed
                    # Actually, let's look for the link "hl_코드"
                    link_el = await page.query_selector(f'{row_sel} [id*="hl_코드"]')
                    
                    if not link_el:
                        # Maybe no link, just data
                        continue
                        
                    mold_no = await link_el.inner_text()
                    mold_no = mold_no.strip()
                    
                    # Click to enter detail
                    # print(f"      🔗 {mold_no} 상세 진입...", end="")
                    await link_el.click()
                    
                    # Wait for detail
                    await page.wait_for_load_state("domcontentloaded")
                    
                    # Download File
                    file_name = await download_attachment(page, mold_no)
                    
                    # Go Back
                    await page.go_back()
                    await page.wait_for_load_state("domcontentloaded")
                    # Ensure we are back on the list (check table existence)
                    await page.wait_for_selector('#ctl00_BodyHolder_gv_Board')
                    
                    row_data = {
                        "금형번호": mold_no,
                        "attached_file": file_name if file_name else ""
                    }
                    # We might want to scrape other columns too, but for now focusing on file
                    # To do full scrape + file, we should have scraped the grid first.
                    
                    page_data.append(row_data)
                    # if file_name:
                    #     print(f" -> 📄 {file_name}")
                    # else:
                    #     print(" -> (파일 없음)")
                        
                except Exception as e:
                    print(f"      ❌ Row {i} Error: {e}")
                    # Try to recover: go to MShape URL directly if stuck
                    if "MShape" not in page.url:
                        await page.goto(MSHAPE_URL)
                        await page.wait_for_load_state("networkidle")
            
            # --- End of Row Loop ---
            
            # Full Grid Scrape for this page to match with files
            # (We do this after to ensure we capture everything, or before?)
            # Since we visited details, we need to re-scrape the grid TEXT data 
            # because we have the page loaded now.
            
            current_grid_data = await page.evaluate("""(tableId) => {
                const table = document.getElementById(tableId);
                if (!table) return [];
                const rows = Array.from(table.rows);
                if (rows.length === 0) return [];
                const headers = Array.from(rows[0].querySelectorAll('th')).map(th => th.innerText.trim());
                const result = [];
                for (let i = 1; i < rows.length; i++) {
                    const row = rows[i];
                    if (row.innerText.includes(' of ') && row.innerText.includes('Pages')) continue;
                    const rowData = {};
                    row.querySelectorAll('td').forEach((cell, idx) => {
                        if (headers[idx]) rowData[headers[idx]] = cell.innerText.trim();
                    });
                    if (Object.keys(rowData).length > 0) result.push(rowData);
                }
                return result;
            }""", "ctl00_BodyHolder_gv_Board")
            
            # Merge file info into grid data
            # Assumes order is preserved (it should be)
            if len(current_grid_data) == len(page_data):
                for grid_row, file_row in zip(current_grid_data, page_data):
                    grid_row["attached_file"] = file_row["attached_file"]
            
            all_data.extend(current_grid_data)
            
            # Duplicate check
            data_str = json.dumps(current_grid_data, sort_keys=True)
            if page_num > 1 and last_raw_data == data_str:
                print("(중복 감지, 종료)")
                break
            last_raw_data = data_str
            
            print(f" -> 누적 {len(all_data)}건")

            # Next Page
            next_btn = await page.query_selector('input[type="image"][id*="btnNext"]')
            if not next_btn:
                print("   ✅ 마지막 페이지 도달")
                break
                
            is_disabled = await next_btn.get_attribute("disabled")
            if is_disabled:
                print("   ✅ 마지막 페이지 도달")
                break
                
            await next_btn.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(1)
            page_num += 1
            
            if page_num > 500:
                print("   ⚠️ 최대 페이지 도달")
                break
        
        result["data"] = all_data
        result["record_count"] = len(all_data)
        
    except Exception as e:
        result["error"] = str(e)
        print(f"   ❌ 오류: {e}")
    
    return result


async def main():
    print("=" * 60)
    print("MShape 상세 파일 다운로드 스크립트")
    print("=" * 60)
    
    user_id, password = get_credentials()
    if not user_id or not password:
        return
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Grant download permissions
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        # Login
        if not await login(page, user_id, password):
            await browser.close()
            return
        
        # Extract
        result = await extract_mshape(page)
        
        # Save JSON
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / "m_shape.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        await browser.close()
    
    print("\n" + "=" * 60)
    print(f"✅ 완료!")
    print(f"   데이터: {result['record_count']:,}건")
    print(f"   파일 저장: {FILES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
