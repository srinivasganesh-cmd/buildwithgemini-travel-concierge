import asyncio
import os
import glob
from playwright.async_api import async_playwright

async def record_demo():
    output_dir = "demo_video"
    os.makedirs(output_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=output_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        
        page = await context.new_page()
        url = "https://travel-concierge-frontend-826243101344.us-east1.run.app"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)
        
        # 1. Click first example prompt: "✨ Find top destinations in Paris"
        print("Clicking first example prompt...")
        prompt_btn = page.locator(".prompt-btn", has_text="Find top destinations in Paris")
        if await prompt_btn.count() > 0:
            await prompt_btn.click()
        else:
            await page.fill("#input", "Find top destinations in Paris")
            await page.click("button.send-btn")
            
        print("Waiting for response to first query...")
        await page.wait_for_selector(".msg-wrapper.agent", timeout=30000)
        await asyncio.sleep(4)
        
        # 2. Ask second richer prompt showing tool calls, currency conversion & image generation
        print("Sending second prompt...")
        second_prompt = "Convert 150 EUR to USD and show me details with a scenic image of Kyoto."
        await page.fill("#input", second_prompt)
        await asyncio.sleep(1)
        await page.click("button.send-btn")
        
        print("Waiting for response to second query...")
        await asyncio.sleep(12)
        
        await context.close()
        await browser.close()
        print("Browser closed and video recorded.")

if __name__ == "__main__":
    asyncio.run(record_demo())
