import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import json
import os
from pathlib import Path

# Mock/Import constants
MES_BASE_URL = "https://dmc.mescloud.net"
LOGIN_URL = f"{MES_BASE_URL}/Default.aspx"
LOGIN_SELECTOR_ID = "#txt_userId"
LOGIN_SELECTOR_PW = "#txt_userPw"
LOGIN_SELECTOR_BTN = "#btnLogin"

# Credentials from config (mock or read)
import configparser

def get_credentials():
    appdata = os.getenv("APPDATA")
    config_path = Path(appdata) / "SmartFactoryLogger" / "config.ini"
    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8-sig")
    return parser.get("MES", "userid"), parser.get("MES", "password")


async def debug_all_sign():
    user_id, password = get_credentials()
    print(f"Debug: Logging in with {user_id}")
    
    async with async_playwright() as p:
        # headless=True for environment
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Login
        await page.goto(LOGIN_URL)
        await page.fill(LOGIN_SELECTOR_ID, user_id)
        await page.fill(LOGIN_SELECTOR_PW, password)
        await page.click(LOGIN_SELECTOR_BTN)
        await page.wait_for_url("**/P00_DSH/**", timeout=20000)
        print("Login Successful")
        
        # 2. Go to AllSign
        target_url = f"{MES_BASE_URL}/P75_ETC/AllSign.aspx"
        print(f"Navigating to {target_url}")
        await page.goto(target_url)
        await page.wait_for_load_state("networkidle")
        
        # 3. Set Date Range (2025)
        print("Setting Date Range: 2025-01-01 ~ 2025-12-31")
        await page.evaluate("""
            () => {
                document.getElementById('ctl00_BodyHolder_txt_FDate').value = '2025-01-01';
                document.getElementById('ctl00_BodyHolder_txt_TDate').value = '2025-12-31';
            }
        """)
        
        # 4. Click Search
        print("Clicking Search...")
        await page.click('[id*="btnSearch"]')
        
        # Wait for loading/network
        # Sometimes ASP.NET uses UpdatePanel, networkidle might be enough or wait for specific element change
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(5) 
        
        # 5. Screenshot
        screenshot_path = os.path.join(os.getcwd(), "debug_all_sign_2025.png")
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        
        # 6. Check Alert? 
        # (If alert appeared, dialog handler needed, otherwise code might hang or capture it)
        # Check rows
        rows = await page.locator("#ctl00_BodyHolder_gv_Board tr").count()
        print(f"Row count found: {rows}")
        
        # Debug: Print first data row HTML
        if rows > 1:
            first_row_html = await page.evaluate("""
                () => {
                    const row = document.querySelector('#ctl00_BodyHolder_gv_Board tr:nth-child(2)');
                    return row ? row.innerHTML : 'No Row';
                }
            """)
            print(f"First Row HTML: {first_row_html}")
        
        # Debug: Extract Table Data using logic from collector.py
        data = await page.evaluate(f"""
            () => {{
                const table = document.getElementById('ctl00_BodyHolder_gv_Board');
                if (!table) return [];
                
                const rows = table.querySelectorAll('tr');
                const headers = [];
                const result = [];
                
                // Header
                const headerRow = rows[0];
                if (headerRow) {{
                    headerRow.querySelectorAll('th').forEach(th => {{
                        headers.push(th.innerText.trim().replace(/\\n/g, ' '));
                    }});
                }}
                
                // Rows
                for (let i = 1; i < rows.length; i++) {{
                    const row = rows[i];
                    const cells = row.querySelectorAll('td');
                    if (cells.length === 0) continue;
                    
                    const rowData = {{}};
                    cells.forEach((cell, idx) => {{
                        if (headers[idx]) {{
                            // Check for input
                            const input = cell.querySelector('input, textarea, select');
                            if (input && (input.value || input.innerText)) {{
                                rowData[headers[idx]] = (input.value || input.innerText).trim();
                            }} else {{
                                rowData[headers[idx]] = cell.innerText.trim();
                            }}
                        }}
                    }});
                    
                    if (Object.keys(rowData).length > 0) result.push(rowData);
                }}
                return result;
            }}
        """)
        
        print(f"Extracted Records: {len(data)}")
        if len(data) > 0:
            print(f"Sample First Record: {data[0]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_all_sign())
