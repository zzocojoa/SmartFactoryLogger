
import asyncio
from playwright.async_api import async_playwright
import sys
from pathlib import Path

# Fix import path for module
sys.path.append(str(Path(__file__).parent.parent.parent))

from v2_next.backend.mes_bridge.config_manager import get_credentials
from v2_next.backend.mes_bridge.constants import LOGIN_URL, LOGIN_SELECTOR_ID, LOGIN_SELECTOR_PW, LOGIN_SELECTOR_BTN, MES_BASE_URL, DEFAULT_TIMEOUT

async def probe_excel_button(page_key="rpt_press"):
    user_id, password = get_credentials()
    
    # URL for rpt_press (Hardcoded or imported, better hardcode for probe)
    # Check pages_registry first? I recall it's /P60_SUM/RptPress.aspx
    target_url = f"{MES_BASE_URL}/P60_SUM/RptPress.aspx"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Login
        print("Logging in...")
        await page.goto(LOGIN_URL)
        await page.fill(LOGIN_SELECTOR_ID, user_id)
        await page.fill(LOGIN_SELECTOR_PW, password)
        await page.click(LOGIN_SELECTOR_BTN)
        await page.wait_for_url("**/P00_DSH/**", timeout=30000)
        print("Login Success.")
        
        # Go to Target
        print(f"Navigating to {target_url}...")
        await page.goto(target_url)
        await page.wait_for_load_state("networkidle")
        
        # Probe for Excel Button
        # Common IDs: btnExcel, btnDown, btnExport
        selectors = [
            '#ctl00_ContentPlaceHolder1_btnExcel', # Standard ASP.NET pattern
            '#btnExcel',
            '#btnDown',
            'input[type="image"][src*="excel"]',
            'img[alt*="Excel"]',
            'a:has-text("Excel")',
            'button:has-text("Excel")'
        ]
        
        found_selector = None
        for sel in selectors:
            try:
                cnt = await page.locator(sel).count()
                if cnt > 0:
                    print(f"FOUND Excel Button! Selector: {sel}")
                    found_selector = sel
                    # Check visibility
                    if await page.is_visible(sel):
                        print(" - Visible: Yes")
                        break
                    else:
                        print(" - Visible: No")
            except:
                pass
                
        if found_selector:
            print("Excel Download is AVAILABLE.")
        else:
            print("Excel Download button NOT found.")
            await page.screenshot(path="excel_probe_fail.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(probe_excel_button())
