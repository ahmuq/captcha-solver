"""Render trigger for the PerimeterX/HUMAN gate on Outlook signup.

The @outlook.com new-mailbox flow (go.microsoft.com/fwlink linkid=2125440) only
surfaces the HUMAN 'Press & Hold' gate AFTER the whole form is walked: username ->
password -> birthdate -> name. Empirically the gate first appears at the name step
(gate_trigger_probe.py: 0..3 = no, 4_after_name = YES). There is NO standalone URL
that renders the gate (iframe.hsprotect.net returns an empty body; captcha.hsprotect
.net returns 403), so this navigation is unavoidable to reach a harvestable gate.

CRITICAL: every value typed here is a THROWAWAY trigger — its only purpose is to make
the challenge render so the solver can harvest _px3. This is NOT account creation:
the solver never submits the final CreateAccount. The real auto-register script owns
the actual account values and reuses the harvested _px3 (+ same proxy/UA) later.

ENTRY: enter the signup form DIRECTLY. The old go.microsoft.com/fwlink?linkid=2125440
link no longer opens the form — it now redirects to
outlook.live.com/mail/?prompt=create_account, which renders an empty page, so the walk
never fills anything and the gate can never appear. Measured: fwlink -> empty title
"Outlook"/no fields; signup.live.com/signup?lic=1 -> "Create your Microsoft account"
with input[name=MemberName] present.
"""
import asyncio
import random
import string

# Direct entry. The fwlink redirect target (outlook.live.com/mail/?prompt=create_account)
# renders an empty shell with no form fields, so the walk could never start.
ENTRY_URL = "https://signup.live.com/signup?lic=1"


def _dummy_email(prefix: str) -> str:
    """The current signup form wants a FULL email address, not a bare username.

    Measured: typing a bare `tag` leaves the form on step 1 with
    "Enter your email address in the format: someone@example.com." and the walk never
    advances (so no gate ever renders). NOTE: this address is unverified and may be
    taken; as a throwaway gate trigger that is acceptable — the form does not check
    availability before the gate step.
    """
    return f"{prefix}@outlook.com"

_FIRST = ["Nathan", "Cherly", "Galuh", "Rendy", "Sinta", "Bagas", "Dinda", "Fajar"]
_LAST = ["Kusumo", "Halimah", "Pratama", "Wijaya", "Santoso", "Nugroho", "Saputra"]


async def _fill(page, sels, val):
    for s in sels:
        try:
            await page.fill(s, val, timeout=3000)
            return True
        except Exception:
            continue
    return False


async def _next(page):
    for s in ['#iSignupAction', 'button:has-text("Next")', 'button[type=submit]',
              '#nextButton']:
        try:
            await page.click(s, timeout=2500)
            return True
        except Exception:
            continue
    return False


async def _pick_fluent(page, trigger_sels, option_index):
    """Fluent UI Dropdown (role=combobox -> listbox, not native <select>).

    The signup page keeps a permanently-mounted Country listbox in the DOM, so a
    bare `[role="option"]` locator resolves against Country's options (Afghanistan,
    Albania, ...) and the birthdate step silently never advances. Scope the option
    lookup to the listbox the clicked combobox actually controls (aria-controls /
    aria-owns), and click with force=True because Fluent triggers fail Playwright's
    pointer-events hit test.
    """
    for ts in trigger_sels:
        try:
            await page.click(ts, timeout=4000, force=True)
        except Exception:
            continue
        lb_id = await page.evaluate(
            """(sel) => {
                 const el = document.querySelector(sel);
                 if (!el) return null;
                 return el.getAttribute('aria-controls')
                     || el.getAttribute('aria-owns') || null;
               }""", ts)
        try:
            if lb_id:
                scoped = f"#{lb_id}"
                await page.wait_for_selector(f"{scoped} [role='option']",
                                             state="visible", timeout=4000)
                opts = page.locator(f"{scoped} [role='option']")
            else:
                opts = page.locator("[role='listbox']:visible [role='option']")
                await opts.first.wait_for(state="visible", timeout=4000)
            n = await opts.count()
            if n:
                await opts.nth(min(option_index, n - 1)).click(timeout=3000)
                await asyncio.sleep(0.4)
                return True
        except Exception:
            continue
    return False


async def render_outlook_gate(page) -> None:
    """Walk the throwaway Outlook signup form far enough that the PerimeterX gate
    renders. Navigates to ENTRY_URL itself. Types disposable values only. Stops
    right after the name step — does NOT submit CreateAccount."""
    tag = "".join(random.choices(string.ascii_lowercase, k=6)) + str(random.randint(100, 999))
    pw = "Zx" + "".join(random.choices(string.ascii_letters + string.digits, k=12)) + "!7"

    await page.goto(ENTRY_URL, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(6)  # signup.live.com OAuth redirect settles
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    # FULL email address — a bare username is rejected by this form (see _dummy_email)
    await _fill(page, ['input[name="MemberName"]', 'input[type="email"]'],
                _dummy_email(tag))
    await _next(page)
    await asyncio.sleep(3)
    # password
    await _fill(page, ['input[name="Password"]', 'input[type="password"]'], pw)
    await _next(page)
    await asyncio.sleep(3)
    # "Add some details": birthdate (Fluent month/day + year input)
    await _pick_fluent(page, ['#BirthMonthDropdown', '[aria-label="Birth month"]'],
                       random.randint(0, 11))
    await _pick_fluent(page, ['#BirthDayDropdown', '[aria-label="Birth day"]'],
                       random.randint(0, 27))
    await _fill(page, ['input[name="BirthYear"]', '[aria-label="Birth year"]', '#BirthYear'],
                str(random.randint(1988, 2002)))
    await _next(page)
    await asyncio.sleep(3)
    # name step — the gate renders after this
    await _fill(page, ['#firstNameInput', 'input[name="FirstName"]'], random.choice(_FIRST))
    await _fill(page, ['#lastNameInput', 'input[name="LastName"]'], random.choice(_LAST))
    await _next(page)
    await asyncio.sleep(6)
