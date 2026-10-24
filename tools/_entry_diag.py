"""Diagnostic: is the block flow-specific? Test several entry paths at step 1.

The renderer enters via go.microsoft.com/fwlink?linkid=2125440 (the new-mailbox
flow). If OTHER entry paths load the signup form normally, the block belongs to
that flow rather than to the client identity or the browser build.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, "/root/captcha-solver")

import cloakbrowser
from common.browser import browser_kwargs

PROXY = os.environ.get("PROBE_PROXY", "")

ENTRIES = [
    ("fwlink_2125440", "https://go.microsoft.com/fwlink/p/?linkid=2125440&clcid=0x409&culture=en-us&country=us"),
    ("signup_direct", "https://signup.live.com/signup"),
    ("signup_lcid", "https://signup.live.com/signup?lcid=1033&lic=1"),
    ("outlook_home", "https://outlook.live.com/mail/0/"),
]

JS = r"""() => {
  const q = s => document.querySelector(s) !== null;
  return {
    url: location.href.slice(0, 120),
    title: document.title,
    membername: q('input[name="MemberName"]') || q('input[type="email"]'),
    password: q('input[name="Password"]') || q('input[type="password"]'),
    blocked: (document.body.innerText || '').toLowerCase().includes('been blocked'),
    headings: [...document.querySelectorAll('h1,h2,[role="heading"]')]
                .map(h => h.innerText.trim()).filter(Boolean).slice(0, 4),
    text: (document.body.innerText || '').slice(0, 200),
  };
}"""


async def main():
    kw = browser_kwargs("TURNSTILE", proxy=PROXY or None)
    kw["headless"] = False
    async with await cloakbrowser.launch_async(**kw) as browser:
        for name, url in ENTRIES:
            ctx = await browser.new_context()
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(6)
                st = await page.evaluate(JS)
            except Exception as e:
                st = {"error": f"{type(e).__name__}: {str(e)[:110]}"}
            st["entry"] = name
            print(json.dumps(st, indent=1)[:900])
            print("-" * 60)
            await ctx.close()


asyncio.run(main())
