"""Diagnostic: walk the outlook_signup renderer and report WHICH STEP the form is on.

_gate_diag.py answers "is the gate there"; this answers "did the walk even get to the
gate step". Distinguishes three outcomes that all look like solved:false:

  - blocked by Microsoft's risk engine before the gate
  - stuck mid-form (birthdate Fluent dropdown failed -> never reaches the name step)
  - reached the name step with no PX escalation (genuine silent-pass)
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

STEP_JS = r"""() => {
  const q = s => document.querySelector(s) !== null;
  const txt = (document.body.innerText || '');
  return {
    url: location.href,
    title: document.title,
    // which form controls exist right now -> which step we are on
    has_membername: q('input[name="MemberName"]'),
    has_password: q('input[name="Password"]'),
    has_birthyear: q('input[name="BirthYear"]') || q('#BirthYear'),
    has_birthmonth: q('#BirthMonthDropdown') || q('[aria-label="Birth month"]'),
    has_firstname: q('#firstNameInput') || q('input[name="FirstName"]'),
    // a value stuck in the birth fields means the dropdown click failed
    birthmonth_value: (document.querySelector('#BirthMonthDropdown') || {}).value
                      || (document.querySelector('[aria-label="Birth month"]') || {}).value || null,
    birthday_value: (document.querySelector('#BirthDayDropdown') || {}).value
                    || (document.querySelector('[aria-label="Birth day"]') || {}).value || null,
    birthyear_value: (document.querySelector('input[name="BirthYear"]') || {}).value || null,
    firstname_value: (document.querySelector('#firstNameInput') || {}).value || null,
    visible_headings: [...document.querySelectorAll('h1,h2,[role="heading"]')]
                        .map(h => h.innerText.trim()).filter(Boolean).slice(0, 6),
    body_text: txt.slice(0, 600),
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
        st = await page.evaluate(STEP_JS)
        st["renderer_error"] = err
        st["hsprotect_requests"] = len(net)
        st["px_cookies"] = [c["name"] for c in await ctx.cookies() if c["name"].startswith("_px")]
        print(json.dumps(st, indent=2)[:5000])


asyncio.run(main())
