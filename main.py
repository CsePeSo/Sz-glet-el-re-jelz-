import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="MakeYourStat Parser", layout="wide")
st.title("⚽ MakeYourStat → 75 soros táblázat")
st.caption("5 lépéses adatbevitel · Automatikus kinyerés · Checksum")

# ============================================================
# SEGÉDFÜGGVÉNYEK
# ============================================================

def get_lines(text):
    return [l.strip() for l in text.split('\n') if l.strip()]

def is_number(s):
    try: float(s); return True
    except: return False

def find_3col(text, keyword, col):
    """
    Megkeresi a kulcsszót, majd a következő sorokban keresi
    a 3 számértéket (L5, L10, All sorrendben - külön sorokban).

    JAVÍTVA: korábban, ha a forrásoldal csak 2 értéket adott meg
    3 helyett (ez előfordul pl. "Avg. shots inside/outside box"
    mezőknél, ha kevés a mérkőzésminta és az L5 oszlop hiányzik),
    a függvény csendben None-t adott vissza, ami utána 0-ra
    konvertálódott - HOLOTT a valós érték nem nulla volt, csak
    hiányzott az egyik oszlop. Ez okozta a Mikkeli SIB/SOB=0 hibát.

    Mostantól 2 érték esetén (jellemzően L10 és All) ésszerű
    fallback-et alkalmazunk 0 helyett, ÉS ezt külön jelezzük is
    (lásd is_fallback visszatérési infó a hívó oldalon).
    """
    col_idx = {"L5": 0, "L10": 1, "All": 2}[col]
    lines = get_lines(text)
    for i, line in enumerate(lines):
        if line.lower() == keyword.lower():
            vals = []
            j = i + 1
            while j < len(lines) and len(vals) < 3:
                if is_number(lines[j]):
                    vals.append(float(lines[j]))
                elif lines[j] in ['L5', 'L10', 'All', 'General', 'Extra Stats']:
                    j += 1
                    continue
                else:
                    break
                j += 1

            if len(vals) >= 3:
                return vals[col_idx], False

            elif len(vals) == 2:
                # A leggyakoribb hiányos eset: csak L10 és All érkezik,
                # az L5 hiányzik. vals[0]=L10, vals[1]=All ebben az esetben.
                # - "All" kérésnél: vals[1] a pontos érték
                # - "L10" kérésnél: vals[0] a pontos érték
                # - "L5" kérésnél: nincs pontos adat -> L10-et adjuk vissza
                #   fallback-ként (jobb közelítés, mint a 0), és jelezzük
                fallback_map = {"L5": (vals[0], True), "L10": (vals[0], False), "All": (vals[1], False)}
                return fallback_map[col]

            elif len(vals) == 1:
                # Csak egyetlen érték van - minden oszlopra ugyanazt adjuk,
                # de jelezzük, hogy ez becslés
                return vals[0], True

    return None, False


def find_liga_val(text, keyword):
    """Liga egysoros értéke a kulcsszó után következő sorban."""
    lines = get_lines(text)
    for i, line in enumerate(lines):
        if line.lower() == keyword.lower():
            j = i + 1
            while j < len(lines):
                if is_number(lines[j]):
                    return float(lines[j])
                j += 1
    return None


def find_over105_liga(text):
    lines = get_lines(text)
    for i, line in enumerate(lines):
        if "over/under 10.5 corners" in line.lower():
            j = i + 1
            while j < len(lines):
                vals = re.findall(r'[\d.]+', lines[j])
                if vals:
                    return float(vals[0])
                j += 1
    return None


def find_over105_team(text, col):
    """
    Ugyanaz a hiányos-adat probléma itt is előfordulhat, ezért ugyanazt
    a 2-értékes fallback logikát alkalmazzuk, mint a find_3col-ban.
    """
    col_idx = {"L5": 0, "L10": 1, "All": 2}[col]
    lines = get_lines(text)
    for i, line in enumerate(lines):
        if line.lower() == "over 10.5 game":
            vals = []
            j = i + 1
            while j < len(lines) and len(vals) < 3:
                v = re.findall(r'[\d.]+', lines[j])
                if v:
                    vals.append(float(v[0]))
                else:
                    break
                j += 1

            if len(vals) >= 3:
                return vals[col_idx], False
            elif len(vals) == 2:
                fallback_map = {"L5": (vals[0], True), "L10": (vals[0], False), "All": (vals[1], False)}
                return fallback_map[col]
            elif len(vals) == 1:
                return vals[0], True

    return None, False


def gc_val(text, col):
    fh, fb1 = find_3col(text, "Avg. game corners FH", col)
    sh, fb2 = find_3col(text, "Avg. game corners SH", col)
    if fh is not None and sh is not None:
        return f"{fh} + {sh}", (fb1 or fb2)
    return "?", False


def parse_sections(liga, h_hm, h_ovr, v_aw, v_ovr):
    d = {}
    errors = []
    fallbacks = []

    def s(key, result):
        val, is_fallback = result if isinstance(result, tuple) else (result, False)
        if val is not None:
            d[key] = val
            if is_fallback:
                fallbacks.append(f"⚡ Sor {key} ({NAMES.get(key,'')}): hiányos forrásadat, "
                                  f"becsült/közelítő érték került beírásra ({val})")
        else:
            d[key] = 0
            errors.append(f"⚠️ Sor {key} ({NAMES.get(key,'')}): NEM TALÁLTAM - 0 került beírásra! "
                           f"Ellenőrizd kézzel, mielőtt elemzésre használod!")

    # LIGA (ezek egysoros liga-átlagok, nem érintettek a 3-oszlopos hibától)
    d[1] = find_liga_val(liga, "Avg. Corners") or 0
    d[2] = find_liga_val(liga, "Home Avg. Corners") or 0
    d[3] = find_liga_val(liga, "Away Avg. Corners") or 0
    d[4] = find_liga_val(liga, "Avg. Total Shots") or 0
    d[5] = find_liga_val(liga, "Avg. Dangerous Attacks") or 0
    d[6] = find_liga_val(liga, "Avg. Shots on Target") or 0
    d[7] = find_liga_val(liga, "Avg. Shots Inside Box") or 0
    d[8] = find_liga_val(liga, "Avg. Shots Outside Box") or 0
    d[9] = find_over105_liga(liga) or 0

    for key, val in [(1, d[1]), (2, d[2]), (3, d[3]), (4, d[4]), (5, d[5]),
                      (6, d[6]), (7, d[7]), (8, d[8]), (9, d[9])]:
        if val == 0:
            errors.append(f"⚠️ Sor {key} ({NAMES.get(key,'')}): NEM TALÁLTAM (liga adat) - "
                           f"ellenőrizd kézzel!")

    # HAZAI HOME
    s(10, find_3col(h_hm, "Avg. dangerous attacks", "All"))
    s(11, find_3col(h_hm, "Avg. dangerous attacks", "L10"))
    s(12, find_3col(h_hm, "Avg. dangerous attacks", "L5"))
    s(13, find_3col(h_hm, "Avg. shots on target", "All"))
    s(14, find_3col(h_hm, "Avg. shots on target", "L10"))
    s(15, find_3col(h_hm, "Avg. shots on target", "L5"))
    s(16, find_3col(h_hm, "Avg. shots inside box", "All"))
    s(17, find_3col(h_hm, "Avg. shots inside box", "L10"))
    s(18, find_3col(h_hm, "Avg. shots inside box", "L5"))
    s(19, find_3col(h_hm, "Avg. shots outside box", "All"))
    s(20, find_3col(h_hm, "Avg. shots outside box", "L10"))
    s(21, find_3col(h_hm, "Avg. shots outside box", "L5"))
    s(22, find_3col(h_hm, "Avg. team corners against", "All"))
    s(23, find_3col(h_hm, "Avg. team corners against", "L10"))
    s(24, find_3col(h_hm, "Avg. team corners against", "L5"))
    s(25, find_3col(h_hm, "Avg. shots", "All"))
    s(26, find_3col(h_hm, "Avg. dangerous attacks", "All"))
    s(27, find_over105_team(h_hm, "All"))
    d[28], fb = gc_val(h_hm, "All")
    if fb: fallbacks.append(f"⚡ Sor 28 (Hazai GC (All)): hiányos forrásadat")
    d[29], fb = gc_val(h_hm, "L10")
    if fb: fallbacks.append(f"⚡ Sor 29 (Hazai GC (L10)): hiányos forrásadat")
    d[30], fb = gc_val(h_hm, "L5")
    if fb: fallbacks.append(f"⚡ Sor 30 (Hazai GC (L5)): hiányos forrásadat")

    # HAZAI OVERALL
    s(31, find_3col(h_ovr, "Avg. dangerous attacks", "L10"))
    s(32, find_3col(h_ovr, "Avg. dangerous attacks", "L5"))
    s(33, find_3col(h_ovr, "Avg. shots on target", "L10"))
    s(34, find_3col(h_ovr, "Avg. shots on target", "L5"))
    s(35, find_3col(h_ovr, "Avg. shots inside box", "L10"))
    s(36, find_3col(h_ovr, "Avg. shots inside box", "L5"))
    s(37, find_3col(h_ovr, "Avg. shots outside box", "L10"))
    s(38, find_3col(h_ovr, "Avg. shots outside box", "L5"))
    s(39, find_3col(h_ovr, "Avg. team corners against", "L10"))
    s(40, find_3col(h_ovr, "Avg. team corners against", "L5"))
    d[41], fb = gc_val(h_ovr, "L10")
    if fb: fallbacks.append(f"⚡ Sor 41 (Hazai OVR GC (L10)): hiányos forrásadat")
    d[42], fb = gc_val(h_ovr, "L5")
    if fb: fallbacks.append(f"⚡ Sor 42 (Hazai OVR GC (L5)): hiányos forrásadat")

    # VENDÉG AWAY
    s(43, find_3col(v_aw, "Avg. dangerous attacks", "All"))
    s(44, find_3col(v_aw, "Avg. dangerous attacks", "L10"))
    s(45, find_3col(v_aw, "Avg. dangerous attacks", "L5"))
    s(46, find_3col(v_aw, "Avg. shots on target", "All"))
    s(47, find_3col(v_aw, "Avg. shots on target", "L10"))
    s(48, find_3col(v_aw, "Avg. shots on target", "L5"))
    s(49, find_3col(v_aw, "Avg. shots inside box", "All"))
    s(50, find_3col(v_aw, "Avg. shots inside box", "L10"))
    s(51, find_3col(v_aw, "Avg. shots inside box", "L5"))
    s(52, find_3col(v_aw, "Avg. shots outside box", "All"))
    s(53, find_3col(v_aw, "Avg. shots outside box", "L10"))
    s(54, find_3col(v_aw, "Avg. shots outside box", "L5"))
    s(55, find_3col(v_aw, "Avg. team corners against", "All"))
    s(56, find_3col(v_aw, "Avg. team corners against", "L10"))
    s(57, find_3col(v_aw, "Avg. team corners against", "L5"))
    s(58, find_3col(v_aw, "Avg. shots", "All"))
    s(59, find_3col(v_aw, "Avg. dangerous attacks", "All"))
    s(60, find_over105_team(v_aw, "All"))
    d[61], fb = gc_val(v_aw, "All")
    if fb: fallbacks.append(f"⚡ Sor 61 (Vendég GC (All)): hiányos forrásadat")
    d[62], fb = gc_val(v_aw, "L10")
    if fb: fallbacks.append(f"⚡ Sor 62 (Vendég GC (L10)): hiányos forrásadat")
    d[63], fb = gc_val(v_aw, "L5")
    if fb: fallbacks.append(f"⚡ Sor 63 (Vendég GC (L5)): hiányos forrásadat")

    # VENDÉG OVERALL
    s(64, find_3col(v_ovr, "Avg. dangerous attacks", "L10"))
    s(65, find_3col(v_ovr, "Avg. dangerous attacks", "L5"))
    s(66, find_3col(v_ovr, "Avg. shots on target", "L10"))
    s(67, find_3col(v_ovr, "Avg. shots on target", "L5"))
    s(68, find_3col(v_ovr, "Avg. shots inside box", "L10"))
    s(69, find_3col(v_ovr, "Avg. shots inside box", "L5"))
    s(70, find_3col(v_ovr, "Avg. shots outside box", "L10"))
    s(71, find_3col(v_ovr, "Avg. shots outside box", "L5"))
    s(72, find_3col(v_ovr, "Avg. team corners against", "L10"))
    s(73, find_3col(v_ovr, "Avg. team corners against", "L5"))
    d[74], fb = gc_val(v_ovr, "L10")
    if fb: fallbacks.append(f"⚡ Sor 74 (Vendég OVR GC (L10)): hiányos forrásadat")
    d[75], fb = gc_val(v_ovr, "L5")
    if fb: fallbacks.append(f"⚡ Sor 75 (Vendég OVR GC (L5)): hiányos forrásadat")

    # ÉRTELMESSÉGI ELLENŐRZÉS (sanity check):
    # Ha egy csapatnak van SoT-ja (kaput találó lövése), de a SIB vagy SOB
    # mindhárom idősávban (All/L10/L5) pontosan 0, az gyanús - lövés
    # kaputalálat nélkül szinte lehetetlen, hogy 0 legyen a boxon
    # belüli/kívüli lövés is. Ez tipikusan hiányzó adatra utal.
    def sanity_check(prefix, sot_key, sib_keys, sob_keys):
        sot = d.get(sot_key, 0)
        sib_all_zero = all(d.get(k, 0) == 0 for k in sib_keys)
        sob_all_zero = all(d.get(k, 0) == 0 for k in sob_keys)
        if sot and sot > 0:
            if sib_all_zero:
                errors.append(f"🔴 GYANÚS ADAT ({prefix}): SoT={sot} de SIB mind 0 - "
                               f"valószínűleg hiányzó forrásadat, NE használd elemzésre "
                               f"ellenőrzés nélkül!")
            if sob_all_zero:
                errors.append(f"🔴 GYANÚS ADAT ({prefix}): SoT={sot} de SOB mind 0 - "
                               f"valószínűleg hiányzó forrásadat, NE használd elemzésre "
                               f"ellenőrzés nélkül!")

    sanity_check("Hazai", 13, [16, 17, 18], [19, 20, 21])
    sanity_check("Vendég", 46, [49, 50, 51], [52, 53, 54])

    return d, errors, fallbacks


NAMES = {
    1: "Avg. Corners", 2: "Home Avg. Corners", 3: "Away Avg. Corners",
    4: "Avg. Total Shots", 5: "Dangerous Attacks", 6: "SoT", 7: "SIB", 8: "SOB",
    9: "Over 10.5 game%", 10: "Hazai DA (All)", 11: "Hazai DA (L10)", 12: "Hazai DA (L5)",
    13: "Hazai SoT (All)", 14: "Hazai SoT (L10)", 15: "Hazai SoT (L5)",
    16: "Hazai SIB (All)", 17: "Hazai SIB (L10)", 18: "Hazai SIB (L5)",
    19: "Hazai SOB (All)", 20: "Hazai SOB (L10)", 21: "Hazai SOB (L5)",
    22: "Hazai Against (All)", 23: "Hazai Against (L10)", 24: "Hazai Against (L5)",
    25: "Hazai avg lövés", 26: "Hazai avg DA", 27: "Hazai Over 10.5 game%",
    28: "Hazai GC (All)", 29: "Hazai GC (L10)", 30: "Hazai GC (L5)",
    31: "Hazai OVR DA (L10)", 32: "Hazai OVR DA (L5)",
    33: "Hazai OVR SoT (L10)", 34: "Hazai OVR SoT (L5)",
    35: "Hazai OVR SIB (L10)", 36: "Hazai OVR SIB (L5)",
    37: "Hazai OVR SOB (L10)", 38: "Hazai OVR SOB (L5)",
    39: "Hazai OVR Against (L10)", 40: "Hazai OVR Against (L5)",
    41: "Hazai OVR GC (L10)", 42: "Hazai OVR GC (L5)",
    43: "Vendég DA (All)", 44: "Vendég DA (L10)", 45: "Vendég DA (L5)",
    46: "Vendég SoT (All)", 47: "Vendég SoT (L10)", 48: "Vendég SoT (L5)",
    49: "Vendég SIB (All)", 50: "Vendég SIB (L10)", 51: "Vendég SIB (L5)",
    52: "Vendég SOB (All)", 53: "Vendég SOB (L10)", 54: "Vendég SOB (L5)",
    55: "Vendég Against (All)", 56: "Vendég Against (L10)", 57: "Vendég Against (L5)",
    58: "Vendég avg lövés", 59: "Vendég avg DA", 60: "Vendég Over 10.5 game%",
    61: "Vendég GC (All)", 62: "Vendég GC (L10)", 63: "Vendég GC (L5)",
    64: "Vendég OVR DA (L10)", 65: "Vendég OVR DA (L5)",
    66: "Vendég OVR SoT (L10)", 67: "Vendég OVR SoT (L5)",
    68: "Vendég OVR SIB (L10)", 69: "Vendég OVR SIB (L5)",
    70: "Vendég OVR SOB (L10)", 71: "Vendég OVR SOB (L5)",
    72: "Vendég OVR Against (L10)", 73: "Vendég OVR Against (L5)",
    74: "Vendég OVR GC (L10)", 75: "Vendég OVR GC (L5)",
}

STEPS = {
    1: ("🏆 1. Liga adatok", "A liga stat oldalát másold be (pl. Liga Profesional → Stats → Overview)."),
    2: ("🏠 2. Hazai csapat — HOME tab", "Hazai csapat → Stats → **Home stats** nézet → másold be az egészet."),
    3: ("📊 3. Hazai csapat — OVERALL tab", "Ugyanott → kattints az **Overall** (alapértelmezett) nézetre → másold be."),
    4: ("✈️ 4. Vendég csapat — AWAY tab", "Vendég csapat → Stats → **Away stats** nézet → másold be."),
    5: ("📊 5. Vendég csapat — OVERALL tab", "Ugyanott → kattints az **Overall** nézetre → másold be."),
}

if "step" not in st.session_state:
    st.session_state.step = 1
if "sections" not in st.session_state:
    st.session_state.sections = {}

# Progress
st.progress((st.session_state.step - 1) / 5, text=f"Lépés {min(st.session_state.step,5)}/5")

if st.session_state.step <= 5:
    step = st.session_state.step
    title, instruction = STEPS[step]
    st.subheader(title)
    st.info(f"ℹ️ {instruction}")

    text = st.text_area("Másold be a szöveget:", height=250, key=f"input_{step}")

    col1, col2 = st.columns([1, 4])
    with col1:
        if step > 1:
            if st.button("⬅️ Vissza"):
                st.session_state.step -= 1
                st.rerun()
    with col2:
        btn = "➡️ Következő" if step < 5 else "✅ Feldolgozás!"
        if st.button(btn, type="primary"):
            if not text.strip():
                st.error("Üres szöveg!")
            else:
                keys = ["liga", "h_hm", "h_ovr", "v_aw", "v_ovr"]
                st.session_state.sections[keys[step - 1]] = text
                st.session_state.step += 1
                st.rerun()

else:
    s_data = st.session_state.sections
    d, errors, fallbacks = parse_sections(
        s_data.get("liga", ""), s_data.get("h_hm", ""),
        s_data.get("h_ovr", ""), s_data.get("v_aw", ""), s_data.get("v_ovr", "")
    )

    checksum = 0
    for i in range(1, 76):
        val = d.get(i, 0)
        if isinstance(val, (int, float)):
            checksum += val
        elif isinstance(val, str) and '+' in val:
            try:
                checksum += sum(float(p.strip()) for p in val.split('+'))
            except Exception:
                pass

    # JAVÍTVA: a hibajelzés most már NEM tűnhet el egy be nem nyitott
    # expander mögött - ha van bármilyen probléma, azonnal, feltűnően
    # jelezzük a lap tetején, nem csak egy elrejthető panelben.
    if errors:
        st.error(f"🔴 {len(errors)} KRITIKUS PROBLÉMA TALÁLHATÓ AZ ADATBAN - "
                 f"NE HASZNÁLD ELEMZÉSRE ELLENŐRZÉS NÉLKÜL!")
        with st.expander(f"⚠️ Részletek ({len(errors)} hiba)", expanded=True):
            for e in errors:
                st.write(e)
    else:
        st.success("✅ Mind a 75 sor sikeresen kinyerve, nincs gyanús 0-érték!")

    if fallbacks:
        st.warning(f"⚡ {len(fallbacks)} mezőnél a forrásoldal hiányos volt, "
                    f"közelítő/becsült érték került beírásra (nem 0, de nem is "
                    f"garantáltan pontos)")
        with st.expander(f"Részletek ({len(fallbacks)} becslés)"):
            for fb in fallbacks:
                st.write(fb)

    st.metric("📊 Checksum", f"{checksum:.4f}")

    rows = [{"#": i, "Megnevezés": NAMES.get(i, ""), "Érték": d.get(i, "?")} for i in range(1, 76)]
    st.dataframe(pd.DataFrame(rows), height=500, use_container_width=True)

    st.subheader("📋 Másolható formátum → Elemző appba")
    out = "Sorszám Megnevezés Érték\n"
    for i in range(1, 76):
        out += f"{i} {NAMES.get(i,'')} {d.get(i,'?')}\n"
    out += f"Checksum {checksum:.4f}"
    st.text_area("", value=out, height=300)

    if st.button("🔄 Új meccs"):
        st.session_state.step = 1
        st.session_state.sections = {}
        st.rerun()
