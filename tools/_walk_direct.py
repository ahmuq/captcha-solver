"""Walk the Outlook signup form from a DIRECT signup URL and report the final state.

The shipped renderer enters via go.microsoft.com/fwlink?linkid=2125440, which now lands
on outlook.live.com/mail/?prompt=create_account instead of opening the signup form.
This probe walks the same steps from https://signup.live.com/signup to see whether the
form completes and whether the PerimeterX gate renders there.
"""
import asyncio
import json
import os
import random
import string
import sys

sys.path.insert(0, "/root/captcha-solver")

import cloakbrowser
from common.browser import browser_kwargs
from perimeterx.renderers.outlook import _fill, _next, _pick_fluent

PROXY = os.environ.get("PROBE_PROXY", "")
ENTRY = "https://signup.live.com/signup?lic=1"

FIRST = ["Nathan", "Cherly", "Galuh", "Rendy", "Sinta", "Bagas", "Dinda", "Fajar"]
LAST = ["Kusumo", "Halimah", "Pratama", "Wijaya", "Santoso", "Nugroho", "Saputra"]

JS = r"""() => {
  const q = s => document.querySelector(s) !== null;
  const t = (document.body.innerText || '');
  const f = [...document.querySelectorAll('iframe')].find(f =>
    /hsprotect|perimeterx|px-captcha/i.test(f.src||'') && f.getBoundingClientRect().width > 50);
  return {
    title: document.title,
    headings: [...document.querySelectorAll('h1,h2,[role="heading"]')]
                .map(h => h.innerText.trim()).filter(Boolean).slice(0, 4),
    membername: q('input[name="MemberName"]'),
    password: q('input[name="Password"]'),
    birthyear: q('input[name="BirthYear"]') || q('#BirthYear'),
    firstname: q('#firstNameInput') || q('input[name="FirstName"]'),
    email_placeholder: (document.querySelector('input[name="MemberName"]') || {}).placeholder
                       || (document.querySelector('input[type="email"]') || {}).placeholder || null,
    gate_iframe: !!f,
    press_hold: /press\s*(&|and)\s*hold|prove you're human/i.test(t),
    blocked: t.toLowerCase().includes('been blocked'),
    text: t.slice(0, 300),
  };
}"""


async def snap(page, label, steps):
    st = await page.evaluate(JS)
    st["at"] = label
    steps.append(st)
    print(json.dumps(st, indent=1)[:700])
    print("-" * 60)


async def main():
    tag = "".join(random.choices(string.ascii_lowercase, k=6)) + str(random.randint(100, 999))
    pw = "Zx" + "".join(random.choices(string.ascii_letters + string.digits, k=12)) + "!7"

    kw = browser_kwargs("TURNSTILE", proxy=PROXY or None)
    kw["headless"] = False
    steps = []
    async with await cloakbrowser.launch_async(**kw) as browser:
        ctx = await browser.new_context()
        page = await ctx.new_page()
        net = []
        page.on("response", lambda r: net.append(r.url) if "hsprotect" in r.url else None)

        await page.goto(ENTRY, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(6)
        await snap(page, "entry", steps)

        # username — form ini minta EMAIL LENGKAP sekarang, bukan username telanjang
        email = f"{tag}@outlook.com"
        ok = await _fill(page, ['input[name="MemberName"]', 'input[type="email"]'], email)
        print(f"[walk] fill MemberName({email}) -> {ok}")
        await _next(page)
        await asyncio.sleep(4)
        await snap(page, "after_username", steps)

        # password
        ok = await _fill(page, ['input[name="Password"]', 'input[type="password"]'], pw)
        print(f"[walk] fill Password -> {ok}")
        await _next(page)
        await asyncio.sleep(4)
        await snap(page, "after_password", steps)

        # birthdate
        m = await _pick_fluent(page, ['#BirthMonthDropdown', '[aria-label="Birth month"]'], random.randint(0, 11))
        d = await _pick_fluent(page, ['#BirthDayDropdown', '[aria-label="Birth day"]'], random.randint(0, 27))
        y = await _fill(page, ['input[name="BirthYear"]', '[aria-label="Birth year"]', '#BirthYear'],
                        str(random.randint(1988, 2002)))
        print(f"[walk] birthdate month={m} day={d} year={y}")
        await _next(page)
        await asyncio.sleep(4)
        await snap(page, "after_birthdate", steps)

        # name
        f1 = await _fill(page, ['#firstNameInput', 'input[name="FirstName"]'], random.choice(FIRST))
        l1 = await _fill(page, ['#lastNameInput', 'input[name="LastName"]'], random.choice(LAST))
        print(f"[walk] name first={f1} last={l1}")
        await _next(page)
        await asyncio.sleep(8)
        await snap(page, "after_name_GATE_STEP", steps)

        cookies = await ctx.cookies()
        print("PX cookies:", [c["name"] for c in cookies if c["name"].startswith("_px")] or "kosong")
        print("hsprotect requests:", len(net))

    with open("/tmp/walk_direct.json", "w") as fh:
        json.dump(steps, fh, indent=1)
    print("\nsaved /tmp/walk_direct.json")


asyncio.run(main())
