"""Diagnostic: run the outlook_signup renderer and dump the end-of-flow DOM state.

Answers one question: at the end of the throwaway signup walk, is a PerimeterX
press-hold gate present (iframe sized, gate text), or is the page blocked / stuck?
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, "/root/captcha-solver")

import cloakbrowser
from common.browser import browser_kwargs
from perimeterx.renderers.outlook import render_outlook_gate

PROXY = os.environ.get("PROBE_PROXY", "")

DIAG_JS = r"""() => {
  const iframes = [...document.querySelectorAll('iframe')].map(f => {
    const r = f.getBoundingClientRect();
    return {src: (f.src||'').slice(0,120), w: Math.round(r.width), h: Math.round(r.height)};
  });
  const body = (document.body.innerText || '');
  return {
    url: location.href,
    title: document.title,
    text: body.slice(0, 1200),
    iframes,
    has_press_hold: /press\s*(&|and)\s*hold|prove you're human/i.test(body),
    hsprotect_frames: iframes.filter(f => /hsprotect|perimeterx|px-captcha/i.test(f.src)).length,
  };
}"""


async def main():
    kw = browser_kwargs("TURNSTILE", proxy=PROXY or None)
    kw["headless"] = False
    async with await cloakbrowser.launch_async(**kw) as browser:
        ctx = await browser.new_context()
        page = await ctx.new_page()
        net = []
        page.on("response", lambda r: net.append(r.url) if "hsprotect" in r.url else None)
        try:
            await render_outlook_gate(page)
            err = None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        await asyncio.sleep(3)
        diag = await page.evaluate(DIAG_JS)
        cookies = await ctx.cookies()
        px = {c["name"]: c["value"][:24] for c in cookies if c["name"].startswith("_px")}
        print(json.dumps({
            "renderer_error": err,
            "diag": diag,
            "px_cookies": px,
            "cookie_names": [c["name"] for c in cookies],
            "hsprotect_requests": len(net),
            "ua": await page.evaluate("() => navigator.userAgent"),
        }, indent=2)[:6000])


asyncio.run(main())
