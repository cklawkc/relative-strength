import pandas as pd
import yfinance as yf
import json
from time import sleep
import requests
import os
from pathlib import Path
from io import StringIO
import random

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def get_browser_cookies(url):
    """用 headless browser 拉 cookie"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    # 等下 JS 設定 cookie（可按需要 sleep 1-2 秒）
    sleep(2)
    cookies = driver.get_cookies()
    cookie_str = '; '.join([f'{c["name"]}={c["value"]}' for c in cookies])
    driver.quit()
    return cookie_str

def get_nasdaq_symbols_with_browser_headers():
    """拉 nasdaqtraded.txt，完整仿 browser header + cookie（自動selenium獲取）"""
    url = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqtraded.txt"
    cookie_str = get_browser_cookies(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Dnt": "1",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Connection": "keep-alive",
        "Cookie": cookie_str,
    }
    print("Getting nasdaqtraded.txt with browser headers + Selenium cookie ...")
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    if not response.text.startswith("Symbol|Security Name"):
        raise RuntimeError("Downloaded content not as expected (可能WAF block)")
    df = pd.read_csv(StringIO(response.text), delimiter='|')
    print(f"Retrieved {len(df)} symbols from NASDAQ")
    return df

def get_ticker_info(symbol, max_retries=3):
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or 'symbol' not in info:
                raise ValueError(f"No data found for {symbol}")
            sector = info.get('sector')
            industry = info.get('industry')
            if sector and industry and sector != 'Unknown' and industry != 'Unknown':
                return sector, industry
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed for {symbol} (no sector/industry), retrying in 2s...")
                sleep(2)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Error for {symbol} (attempt {attempt + 1}): {e}, retrying in {wait_time:.1f}s...")
                sleep(wait_time)
            else:
                print(f"Final failure for {symbol}: {e}")
    return None, None

def process_nasdaq_file():
    result = {}
    script_dir = Path(__file__).parent if "__file__" in globals() else Path(os.getcwd())
    output_file = script_dir / 'ticker_info.json'

    if output_file.exists():
        try:
            with open(output_file, 'r') as f:
                result = json.load(f)
            print(f"Loaded existing data with {len(result)} entries")
        except Exception as e:
            print(f"Error loading existing file: {e}")

    df = get_nasdaq_symbols_with_browser_headers()

    processed_count = 0
    for _, row in df.iterrows():
        symbol = row['Symbol']
        if not symbol or '.' in symbol or '-' in symbol or len(symbol) > 5:
            continue
        if symbol not in result:
            sector, industry = get_ticker_info(symbol)
            if sector and industry:
                result[symbol] = {
                    "info": {
                        "industry": industry,
                        "sector": sector
                    }
                }
                print(f"Added: {symbol} - {sector}/{industry}")
                processed_count += 1
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
            else:
                print(f"Skipped (missing data after retries): {symbol}")
            sleep(random.uniform(1, 3))
            if processed_count and processed_count % 10 == 0:
                print(f"Processed {processed_count} symbols, taking a longer break...")
                sleep(5)

    print(f"Final dataset contains {len(result)} symbols")
    return result

if __name__ == "__main__":
    process_nasdaq_file()
