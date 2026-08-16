import streamlit as st
import io
import csv

# Use the console_main module (original extractor) to avoid circular imports
from console_main import MakeyourstatStrictExtractor, build_league_table, build_team_table, build_model_table_rows

st.set_page_config(page_title="MAKEYOURSTAT extractor", layout="wide")
st.title("MAKEYOURSTAT STRICT EXTRACTOR (web)")
st.markdown("Pasteeld be a raw txt-eket az alábbi mezőkbe (ne tölts fel fájlt).\n\nHasználat: illeszd be a 5 raw fájl tartalmát és nyomd meg a Futtatás gombot.")

league_text = st.text_area("1) Liga raw szöveg", height=200)
home_all_text = st.text_area("2) Hazai ALL raw szöveg", height=200)
home_home_text = st.text_area("3) Hazai HOME raw szöveg", height=200)
away_all_text = st.text_area("4) Vendég ALL raw szöveg", height=200)
away_away_text = st.text_area("5) Vendég AWAY raw szöveg", height=200)

out_prefix = st.text_input("Output fájl prefix (pl. mariehamn_sjk)", value="extract_output")
run = st.button("Futtatás")

if run:
    missing = []
    if not league_text or not league_text.strip(): missing.append("Liga raw szöveg")
    if not home_all_text or not home_all_text.strip(): missing.append("Hazai ALL raw szöveg")
    if not home_home_text or not home_home_text.strip(): missing.append("Hazai HOME raw szöveg")
    if not away_all_text or not away_all_text.strip(): missing.append("Vendég ALL raw szöveg")
    if not away_away_text or not away_away_text.strip(): missing.append("Vendég AWAY raw szöveg")

    if missing:
        st.error("Hiányzó szövegek: " + ", ".join(missing))
    else:
        try:
            extractor = MakeyourstatStrictExtractor()

            league = extractor.parse_league(league_text)
            home_all = extractor.parse_team(home_all_text, "home_all")
            home_home = extractor.parse_team(home_home_text, "home_home")
            away_all = extractor.parse_team(away_all_text, "away_all")
            away_away = extractor.parse_team(away_away_text, "away_away")

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

            st.download_button("Letöltés: league CSV", league_csv, file_name=f"{out_prefix}_league_table.csv", mime="text/csv")
            st.download_button("Letöltés: team CSV", team_csv, file_name=f"{out_prefix}_team_table.csv", mime="text/csv")
            st.download_button("Letöltés: model-ready CSV", model_csv, file_name=f"{out_prefix}_model_ready.csv", mime="text/csv")

            st.success("Kész. Nézd meg a letöltés gombokat, és a naplókat ha bármi hiba van.")

        except Exception as e:
            st.exception(e)
