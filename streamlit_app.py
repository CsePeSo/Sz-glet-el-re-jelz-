import streamlit as st
import io
import csv
from pathlib import Path
from datetime import datetime

# Use the console_main module (original extractor)
from console_main import MakeyourstatStrictExtractor, build_league_table, build_team_table, build_model_table_rows

st.set_page_config(page_title="MAKEYOURSTAT extractor", layout="wide")
st.title("MAKEYOURSTAT STRICT EXTRACTOR (web)")
st.markdown("Pasteeld be a raw txt-eket az alábbi mezőkbe (nem fájlt tölts fel).\n\nAz alkalmazás automatikusan ment minden mezőt, így ha összeomlik, a beírt adatok visszatöltődnek.")

# Autosave directory (container-local)
AUTOSAVE_DIR = Path("/tmp/riaszto_autosave")
AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)

FIELD_KEYS = {
    'league_text': '1_liga',
    'home_all_text': '2_home_all',
    'home_home_text': '3_home_home',
    'away_all_text': '4_away_all',
    'away_away_text': '5_away_away',
}

# Helper functions for autosave

def autosave_path(key: str) -> Path:
    name = FIELD_KEYS.get(key, key)
    return AUTOSAVE_DIR / f"{name}.txt"


def save_field_to_disk(key: str) -> None:
    try:
        val = st.session_state.get(key, "") or ""
        p = autosave_path(key)
        p.write_text(val, encoding="utf-8")
    except Exception as e:
        # show non-blocking message in Streamlit
        st.warning(f"Nem sikerült menteni a mezőt {key}: {e}")


def load_field_from_disk(key: str) -> str:
    try:
        p = autosave_path(key)
        if p.exists():
            return p.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def clear_autosaves() -> None:
    for k in FIELD_KEYS:
        p = autosave_path(k)
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


# Initialize session state from disk if present
for k in FIELD_KEYS.keys():
    if k not in st.session_state:
        st.session_state[k] = load_field_from_disk(k)

# Provide a simple top bar with buttons
col_top1, col_top2 = st.columns([1, 4])
with col_top1:
    if st.button("Clear saved drafts"):
        clear_autosaves()
        # clear session state values too
        for k in FIELD_KEYS.keys():
            st.session_state[k] = ""
        st.success("Autosave törölve")
with col_top2:
    st.write("")

st.write("---")

# Define on_change callbacks

def make_on_change(k: str):
    def _cb():
        save_field_to_disk(k)
    return _cb

# Text areas with autosave callbacks
league_text = st.text_area("1) Liga raw szöveg", value=st.session_state.get('league_text', ''), height=200, key='league_text', on_change=make_on_change('league_text'))
home_all_text = st.text_area("2) Hazai ALL raw szöveg", value=st.session_state.get('home_all_text', ''), height=200, key='home_all_text', on_change=make_on_change('home_all_text'))
home_home_text = st.text_area("3) Hazai HOME raw szöveg", value=st.session_state.get('home_home_text', ''), height=200, key='home_home_text', on_change=make_on_change('home_home_text'))
away_all_text = st.text_area("4) Vendég ALL raw szöveg", value=st.session_state.get('away_all_text', ''), height=200, key='away_all_text', on_change=make_on_change('away_all_text'))
away_away_text = st.text_area("5) Vendég AWAY raw szöveg", value=st.session_state.get('away_away_text', ''), height=200, key='away_away_text', on_change=make_on_change('away_away_text'))

out_prefix = st.text_input("Output fájl prefix (pl. mariehamn_sjk)", value=st.session_state.get('out_prefix', 'extract_output'))

# Save prefix on change
if 'out_prefix' not in st.session_state:
    st.session_state['out_prefix'] = out_prefix
else:
    if out_prefix != st.session_state.get('out_prefix'):
        st.session_state['out_prefix'] = out_prefix

run = st.button("Futtatás")

if run:
    # Ensure latest session_state values are saved to disk
    for k in FIELD_KEYS.keys():
        save_field_to_disk(k)
    # Also save a full timestamped backup
    try:
        ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        backup_dir = AUTOSAVE_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / f"backup_{ts}.txt"
        with backup_file.open('w', encoding='utf-8') as f:
            for k in FIELD_KEYS.keys():
                f.write(f"=== {k} ===\n")
                f.write(st.session_state.get(k, '') or '')
                f.write('\n\n')
    except Exception as e:
        st.warning(f"Nem sikerült létrehozni a backup fájlt: {e}")

    # Proceed with extraction
    missing = []
    if not st.session_state.get('league_text', '').strip(): missing.append("Liga raw szöveg")
    if not st.session_state.get('home_all_text', '').strip(): missing.append("Hazai ALL raw szöveg")
    if not st.session_state.get('home_home_text', '').strip(): missing.append("Hazai HOME raw szöveg")
    if not st.session_state.get('away_all_text', '').strip(): missing.append("Vendég ALL raw szöveg")
    if not st.session_state.get('away_away_text', '').strip(): missing.append("Vendég AWAY raw szöveg")

    if missing:
        st.error("Hiányzó szövegek: " + ", ".join(missing))
    else:
        try:
            extractor = MakeyourstatStrictExtractor()

            league = extractor.parse_league(st.session_state['league_text'])
            home_all = extractor.parse_team(st.session_state['home_all_text'], "home_all")
            home_home = extractor.parse_team(st.session_state['home_home_text'], "home_home")
            away_all = extractor.parse_team(st.session_state['away_all_text'], "away_all")
            away_away = extractor.parse_team(st.session_state['away_away_text'], "away_away")

            model_rows = extractor.build_model_ready(
                league=league,
                home_all=home_all,
                home_home=home_home,
                away_all=away_all,
                away_away=away_away,
            )

            audit_text = extractor.build_audit(
                league=league,
                home_all=home_all,
                home_home=home_home,
                away_all=away_all,
                away_away=away_away,
                model_rows=model_rows,
            )

            league_table = build_league_table(league)
            team_table = []
            team_table.extend(build_team_table("home_all", home_all))
            team_table.extend(build_team_table("home_home", home_home))
            team_table.extend(build_team_table("away_all", away_all))
            team_table.extend(build_team_table("away_away", away_away))
            model_table = build_model_table_rows(model_rows)

            st.subheader("Audit")
            st.code(audit_text)

            st.subheader("League table")
            st.dataframe([{"metric": r[0], "value": r[1]} for r in league_table])

            st.subheader("Model-ready (first 200 rows)")
            st.dataframe([{"group": r[0], "feature": r[1], "value": r[2], "formula": r[3], "required_now": r[4]} for r in model_table][:200])

            def make_csv_bytes(headers, rows):
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(headers)
                writer.writerows(rows)
                return buf.getvalue().encode("utf-8")

            league_csv = make_csv_bytes(["metric", "value"], league_table)
            team_csv = make_csv_bytes(["block", "metric", "L5", "L10", "All"], team_table)
            model_csv = make_csv_bytes(["group", "feature", "value", "formula", "required_now"], model_table)

            st.download_button("Letöltés: league CSV", league_csv, file_name=f"{st.session_state.get('out_prefix','extract_output')}_league_table.csv", mime="text/csv")
            st.download_button("Letöltés: team CSV", team_csv, file_name=f"{st.session_state.get('out_prefix','extract_output')}_team_table.csv", mime="text/csv")
            st.download_button("Letöltés: model-ready CSV", model_csv, file_name=f"{st.session_state.get('out_prefix','extract_output')}_model_ready.csv", mime="text/csv")

            st.success("Kész. A bemenetek automatikusan mentve lettek a szerveren (temp).")

        except Exception as e:
            st.exception(e)
