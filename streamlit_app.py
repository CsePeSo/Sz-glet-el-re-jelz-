import streamlit as st
import io
import csv

# Import specific symbols from console_main to avoid circular imports (main <-> streamlit_app)
from console_main import MakeyourstatStrictExtractor, build_league_table, build_team_table, build_model_table_rows

st.set_page_config(page_title="MAKEYOURSTAT extractor", layout="wide")

st.title("MAKEYOURSTAT STRICT EXTRACTOR (web)")
st.markdown("Töltsd fel az 5 raw txt fájlt. Ez a felület helyettesíti a konzolos input() hívásokat.")

col1, col2 = st.columns(2)

with col1:
    league_file = st.file_uploader("1) Liga raw txt", type=["txt"])
    home_all_file = st.file_uploader("2) Hazai ALL raw txt", type=["txt"])
    home_home_file = st.file_uploader("3) Hazai HOME raw txt", type=["txt"])

with col2:
    away_all_file = st.file_uploader("4) Vendég ALL raw txt", type=["txt"])
    away_away_file = st.file_uploader("5) Vendég AWAY raw txt", type=["txt"])
    out_prefix = st.text_input("Output fájl prefix (pl. mariehamn_sjk)", value="extract_output")

run = st.button("Futtatás")


def read_uploaded_text(f) -> str:
    if f is None:
        return ""
    data = f.read()
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return str(data)


if run:
    missing = []
    if league_file is None: missing.append("Liga raw txt")
    if home_all_file is None: missing.append("Hazai ALL raw txt")
    if home_home_file is None: missing.append("Hazai HOME raw txt")
    if away_all_file is None: missing.append("Vendég ALL raw txt")
    if away_away_file is None: missing.append("Vendég AWAY raw txt")

    if missing:
        st.error("Hiányzó fájlok: " + ", ".join(missing))
    else:
        try:
            league_raw = read_uploaded_text(league_file)
            home_all_raw = read_uploaded_text(home_all_file)
            home_home_raw = read_uploaded_text(home_home_file)
            away_all_raw = read_uploaded_text(away_all_file)
            away_away_raw = read_uploaded_text(away_away_file)

            extractor = MakeyourstatStrictExtractor()

            league = extractor.parse_league(league_raw)
            home_all = extractor.parse_team(home_all_raw, "home_all")
            home_home = extractor.parse_team(home_home_raw, "home_home")
            away_all = extractor.parse_team(away_all_raw, "away_all")
            away_away = extractor.parse_team(away_away_raw, "away_away")

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

            # Táblák építése (a console_main modulból importált helper függvényeket használjuk)
            league_table = build_league_table(league)
            team_table = []
            team_table.extend(build_team_table("home_all", home_all))
            team_table.extend(build_team_table("home_home", home_home))
            team_table.extend(build_team_table("away_all", away_all))
            team_table.extend(build_team_table("away_away", away_away))
            model_table = build_model_table_rows(model_rows)

            # Megjelenítés
            st.subheader("Audit")
            st.code(audit_text)

            st.subheader("League table")
            st.dataframe([{ "metric": r[0], "value": r[1]} for r in league_table])

            st.subheader("Model-ready (first 200 rows)")
            st.dataframe([{"group": r[0], "feature": r[1], "value": r[2], "formula": r[3], "required_now": r[4]} for r in model_table][:200])

            # CSV-k generálása letöltésre
            def make_csv_bytes(headers, rows):
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(headers)
                writer.writerows(rows)
                return buf.getvalue().encode("utf-8")

            league_csv = make_csv_bytes(["metric", "value"], league_table)
            team_csv = make_csv_bytes(["block", "metric", "L5", "L10", "All"], team_table)
            model_csv = make_csv_bytes(["group", "feature", "value", "formula", "required_now"], model_table)

            st.download_button("Letöltés: league CSV", league_csv, file_name=f"{out_prefix}_league_table.csv", mime="text/csv")
            st.download_button("Letöltés: team CSV", team_csv, file_name=f"{out_prefix}_team_table.csv", mime="text/csv")
            st.download_button("Letöltés: model-ready CSV", model_csv, file_name=f"{out_prefix}_model_ready.csv", mime="text/csv")

            st.success("Kész. Nézd meg a letöltés gombokat, és a naplókat ha bármi hiba van.")

        except Exception as e:
            st.exception(e)
