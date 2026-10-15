"""
Streamlit Keep-Alive & Auto Wake-Up Script
Visits https://chandramap.streamlit.app/ via headless browser to:
1. Prevent container cold-starts by generating real user traffic.
2. Maintain active WebSocket sessions with the Streamlit server.
3. Automatically detect and click the "Yes, get this app back up!" button if the app has gone to sleep.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

STREAMLIT_URL = os.environ.get("STREAMLIT_APP_URL", "https://chandramap.streamlit.app/")

def keep_alive():
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    print(f"[{timestamp}] Starting Streamlit keep-alive visit...")
    print(f"Target URL: {STREAMLIT_URL}")

    with sync_playwright() as p:
        print("Launching headless browser...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            print("Navigating to app URL...")
            response = page.goto(STREAMLIT_URL, timeout=60000, wait_until="domcontentloaded")
            http_status = response.status if response else "Unknown"
            print(f"Initial HTTP response status: {http_status}")

            # Allow client-side rendering / redirection to settle
            page.wait_for_timeout(5000)
            print(f"Current page URL: {page.url}")
            print(f"Page title: {page.title()}")

            # Selectors for Streamlit sleep/hibernation screen buttons
            wake_selectors = [
                "button:has-text('get this app back up')",
                "button:has-text('Yes, get this app back up')",
                "button:has-text('Wake up app')",
                "button:has-text('Wake up')",
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'get this app back up')]",
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'wake up')]",
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'wake')]"
            ]

            wake_button_clicked = False
            for selector in wake_selectors:
                try:
                    locator = page.locator(selector)
                    if locator.count() > 0 and locator.first.is_visible():
                        print(f"App is in sleep mode! Found wake-up button with selector: '{selector}'. Clicking...")
                        locator.first.click()
                        wake_button_clicked = True
                        print("Wake-up button clicked. Waiting 15 seconds for app container to boot...")
                        page.wait_for_timeout(15000)
                        break
                except Exception as sel_err:
                    print(f"Selector check '{selector}' note: {sel_err}")

            if not wake_button_clicked:
                print("No sleep screen detected; app is awake or actively serving.")

            # Verify that Streamlit UI container or root is active
            try:
                page.wait_for_selector('[data-testid="stApp"], [data-testid="stAppViewContainer"], #root', timeout=15000)
                print("Streamlit app container detected and responsive.")
            except PlaywrightTimeoutError:
                print("App container selector wait timed out; page is still reachable.")

            # Keep session open briefly so WebSocket connection registers active traffic
            page.wait_for_timeout(5000)
            print("Keep-alive session successfully completed. Streamlit container is warm.")

        except Exception as err:
            print(f"Error or warning during keep-alive run: {err}")
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    keep_alive()
