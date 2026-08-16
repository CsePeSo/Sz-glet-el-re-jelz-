# -*- coding: utf-8 -*-
"""
MAKEYOURSTAT STRICT EXTRACTOR v1.0
==================================

Cél:
- 5 lépcsős raw input
- explicit adatok kinyerése
- semmi becslés / találgatás
- raw-extract tábla
- model-ready tábla
- audit report

HASZNÁLAT:
    python makeyourstat_extractor_v1.py

A program 5 lépésben bekéri az 5 txt fájlt:
    1) liga raw txt
    2) hazai all raw txt
    3) hazai home raw txt
    4) vendég all raw txt
    5) vendég away raw txt

Kimenet:
    - <prefix>_league_table.csv
    - <prefix>_team_table.csv
    - <prefix>_model_ready.csv
    - <prefix>_audit.txt

Megjegyzés:
- A százalékok normalizált formában lesznek tárolva: pl. 41% -> 0.41
"""

import csv
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# =============================================================================
# 1. SEGÉDFÜGGVÉNYEK
# =============================================================================

def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))

def norm_text(text: str) -> str:
    text = strip_accents(text).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text

def clean_lines(raw: str) -> List[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]

def parse_numeric_token(token: str) -> Optional[float]:
    """
    '41%' -> 0.41
    '5.44' -> 5.44
    '5,44' -> 5.44
    '/' -> None
    """
    s = token.strip().replace(",", ".")
    if s in {"/", "-", "—"}:
        return None

    if re.fullmatch(r"-?\d+(?:\.\d+)?%", s):
        return float(s[:-1]) / 100.0

    if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        return float(s)

    return None

def first_numeric_after_label(lines: List[str], label: str, lookahead: int = 8) -> Optional[float]:
    target = norm_text(label)
    for i, line in enumerate(lines):
        if norm_text(line) == target:
            for j in range(i + 1, min(len(lines), i + 1 + lookahead)):
                v = parse_numeric_token(lines[j])
                if v is not None:
                    return v
    return None

def triplet_after_label(lines: List[str], label: str, lookahead: int = 12) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Egy label után a következő 3 numerikus érték = L5, L10, All
    """
    target = norm_text(label)
    for i, line in enumerate(lines):
        if norm_text(line) == target:
            vals = []
            for j in range(i + 1, min(len(lines), i + 1 + lookahead)):
                v = parse_numeric_token(lines[j])
                if v is not None:
                    vals.append(v)
                if len(vals) == 3:
                    return vals[0], vals[1], vals[2]
    return None, None, None

def add_if_present(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a + b

def sub_if_present(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b

def div_if_present(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b in (None, 0):
        return None
    return a / b

def fmt(v: Any) -> str:
    if v is None:
        return "MISSING"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)

def write_csv(path: Path, headers: List[str], rows: List[List[Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def pretty_print_table(title: str, headers: List[str], rows: List[List[Any]], max_rows: Optional[int] = None) -> None:
    print(f"\n{title}")
    print("=" * len(title))

    if max_rows is not None:
        rows = rows[:max_rows]

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "-+-".join("-" * widths[i] for i in range(len(headers)))

    print(header_line)
    print(sep)

    for row in rows:
        print(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))))


# =============================================================================
# 2. KINYERENDŐ MEZŐK
# =============================================================================

LEAGUE_LABELS = {
    "league_avg_corners": "Avg. Corners",
    "league_home_avg_corners": "Home Avg. Corners",
    "league_away_avg_corners": "Away Avg. Corners",
    "league_over_8_5": "Over/Under 8.5 Corners",
    "league_over_9_5": "Over/Under 9.5 Corners",
    "league_over_10_5": "Over/Under 10.5 Corners",
    "league_avg_attacks": "Avg. Attacks",
    "league_avg_dangerous_attacks": "Avg. Dangerous Attacks",
    "league_avg_sot": "Avg. Shots on Target",
    "league_avg_sib": "Avg. Shots Inside Box",
    "league_avg_sob": "Avg. Shots Outside Box",
    "league_avg_goals": "Avg. Goals",
    "league_avg_xg": "Avg. Expected Goals",
    "league_avg_xga": "Avg. Expected Goals Against",
}

TEAM_LABELS = {
    # Direct Cornerhez
    "game_over_9_5": "Over 9.5 game",
    "game_over_10_5": "Over 10.5 game",
    "avg_game_corners_fh": "Avg. game corners FH",
    "avg_game_corners_sh": "Avg. game corners SH",
    "team_over_4_5": "Over 4.5 team",
    "team_over_5_5": "Over 5.5 team",
    "avg_team_corners_against": "Avg. team corners against",
    "team_against_over_4_5": "Over 4.5 team against",
    "team_against_over_5_5": "Over 5.5 team against",

    # Attack-Defensehez
    "avg_dangerous_attacks": "Avg. dangerous attacks",
    "avg_dangerous_attacks_against": "Avg. dangerous attacks against",
    "avg_sot": "Avg. shots on target",
    "avg_sot_against": "Avg. shots on target against",

    # xG opcionális támogató adatok
    "xg": "Expected goals (xG)",
    "xga": "Expected goals against (xGA)",
}


# =============================================================================
# 3. EXTRACTOR
# =============================================================================

class MakeyourstatStrictExtractor:
    def parse_league(self, raw: str) -> Dict[str, Optional[float]]:
        lines = clean_lines(raw)
        out: Dict[str, Optional[float]] = {}

        out["league_name"] = lines[0] if lines else "Unknown League"

        for key, label in LEAGUE_LABELS.items():
            out[key] = first_numeric_after_label(lines, label)

        return out

    def parse_team(self, raw: str, prefix: str) -> Dict[str, Optional[float]]:
        lines = clean_lines(raw)
        out: Dict[str, Optional[float]] = {}

        out[f"{prefix}_team_name"] = lines[0] if lines else "Unknown Team"

        for key, label in TEAM_LABELS.items():
            l5, l10, allv = triplet_after_label(lines, label)
            out[f"{prefix}_{key}_l5"] = l5
            out[f"{prefix}_{key}_l10"] = l10
            out[f"{prefix}_{key}_all"] = allv

        return out

    def build_model_ready(self,
                          league: Dict[str, Optional[float]],
                          home_all: Dict[str, Optional[float]],
                          home_home: Dict[str, Optional[float]],
                          away_all: Dict[str, Optional[float]],
                          away_away: Dict[str, Optional[float]]) -> List[Dict[str, Any]]:

        model_rows: List[Dict[str, Any]] = []

        # --- League raw rows ---
        for key in LEAGUE_LABELS.keys():
            model_rows.append({
                "group": "league",
                "feature": key,
                "value": league.get(key),
                "formula": "explicit raw",
                "required_now": "YES"
            })

        # --- Team derived exact rows ---
        for prefix, block in [
            ("home_all", home_all),
            ("home_home", home_home),
            ("away_all", away_all),
            ("away_away", away_away),
        ]:
            # Exact total game corners = FH + SH
            for horizon in ("l5", "l10", "all"):
                fh = block.get(f"{prefix}_avg_game_corners_fh_{horizon}")
                sh = block.get(f"{prefix}_avg_game_corners_sh_{horizon}")
                total_game = add_if_present(fh, sh)

                against = block.get(f"{prefix}_avg_team_corners_against_{horizon}")
                own = sub_if_present(total_game, against)

                model_rows.append({
                    "group": prefix,
                    "feature": f"{prefix}_avg_game_corners_total_{horizon}",
                    "value": total_game,
                    "formula": f"{prefix}_avg_game_corners_fh_{horizon} + {prefix}_avg_game_corners_sh_{horizon}",
                    "required_now": "YES"
                })

                model_rows.append({
                    "group": prefix,
                    "feature": f"{prefix}_own_team_corners_{horizon}",
                    "value": own,
                    "formula": f"{prefix}_avg_game_corners_total_{horizon} - {prefix}_avg_team_corners_against_{horizon}",
                    "required_now": "YES"
                })

            # Validated attack = SoT / DA (L10, All)
            for horizon in ("l10", "all"):
                sot = block.get(f"{prefix}_avg_sot_{horizon}")
                da = block.get(f"{prefix}_avg_dangerous_attacks_{horizon}")
                att_val = div_if_present(sot, da)

                sot_ag = block.get(f"{prefix}_avg_sot_against_{horizon}")
                da_ag = block.get(f"{prefix}_avg_dangerous_attacks_against_{horizon}")
                def_val = div_if_present(sot_ag, da_ag)

                model_rows.append({
                    "group": prefix,
                    "feature": f"{prefix}_attack_validation_{horizon}",
                    "value": att_val,
                    "formula": f"{prefix}_avg_sot_{horizon} / {prefix}_avg_dangerous_attacks_{horizon}",
                    "required_now": "YES"
                })

                model_rows.append({
                    "group": prefix,
                    "feature": f"{prefix}_defense_validation_{horizon}",
                    "value": def_val,
                    "formula": f"{prefix}_avg_sot_against_{horizon} / {prefix}_avg_dangerous_attacks_against_{horizon}",
                    "required_now": "YES"
                })

            # Explicit over profile rows we will use later
            for base in [
                "game_over_9_5",
                "game_over_10_5",
                "team_over_4_5",
                "team_over_5_5",
                "team_against_over_4_5",
                "team_against_over_5_5",
                "xg",
                "xga",
            ]:
                for horizon in ("l10", "all"):
                    model_rows.append({
                        "group": prefix,
                        "feature": f"{prefix}_{base}_{horizon}",
                        "value": block.get(f"{prefix}_{base}_{horizon}"),
                        "formula": "explicit raw",
                        "required_now": "YES" if base != "xg" and base != "xga" else "OPTIONAL"
                    })

        return model_rows

    def build_audit(self,
                    league: Dict[str, Optional[float]],
                    home_all: Dict[str, Optional[float]],
                    home_home: Dict[str, Optional[float]],
                    away_all: Dict[str, Optional[float]],
                    away_away: Dict[str, Optional[float]],
                    model_rows: List[Dict[str, Any]]) -> str:

        def block_stats(block_name: str, dct: Dict[str, Any]) -> str:
            keys = [k for k in dct.keys() if not k.endswith("_team_name") and k != "league_name"]
            found = [k for k in keys if dct[k] is not None]
            missing = [k for k in keys if dct[k] is None]
            txt = []
            txt.append(f"[{block_name}] found={len(found)} missing={len(missing)}")
            if missing:
                txt.append("  MISSING:")
                for m in missing:
                    txt.append(f"    - {m}")
            return "\n".join(txt)

        required_rows = [r for r in model_rows if r["required_now"] == "YES"]
        required_found = [r for r in required_rows if r["value"] is not None]
        required_missing = [r for r in required_rows if r["value"] is None]

        lines = []
        lines.append("=== AUDIT REPORT ===")
        lines.append("")
        lines.append(block_stats("league", league))
        lines.append("")
        lines.append(block_stats("home_all", home_all))
        lines.append("")
        lines.append(block_stats("home_home", home_home))
        lines.append("")
        lines.append(block_stats("away_all", away_all))
        lines.append("")
        lines.append(block_stats("away_away", away_away))
        lines.append("")
        lines.append(f"[model_ready_required] found={len(required_found)} missing={len(required_missing)}")
        if required_missing:
            lines.append("  MISSING MODEL-READY FEATURES:")
            for r in required_missing:
                lines.append(f"    - {r['feature']}  ({r['formula']})")

        return "\n".join(lines)


# =============================================================================
# 4. TÁBLÁK ÉPÍTÉSE
# =============================================================================

def build_league_table(league: Dict[str, Optional[float]]) -> List[List[Any]]:
    rows = []
    for key in LEAGUE_LABELS.keys():
        rows.append([key, fmt(league.get(key))])
    return rows

def build_team_table(block_name: str, block: Dict[str, Optional[float]]) -> List[List[Any]]:
    rows = []
    for key in TEAM_LABELS.keys():
        rows.append([
            block_name,
            key,
            fmt(block.get(f"{block_name}_{key}_l5")),
            fmt(block.get(f"{block_name}_{key}_l10")),
            fmt(block.get(f"{block_name}_{key}_all")),
        ])
    return rows

def build_model_table_rows(model_rows: List[Dict[str, Any]]) -> List[List[Any]]:
    rows = []
    for r in model_rows:
        rows.append([
            r["group"],
            r["feature"],
            fmt(r["value"]),
            r["formula"],
            r["required_now"],
        ])
    return rows


# =============================================================================
# 5. MAIN
# =============================================================================

def read_text_file(path_str: str) -> str:
    path = Path(path_str.strip())
    return path.read_text(encoding="utf-8")

def main():
    print("\nMAKEYOURSTAT STRICT EXTRACTOR v1.0")
    print("5 lépcsős input - explicit adatkinyerés, becslés nélkül\n")

    league_path = input("1/5 - Liga raw txt fájl elérési útja: ").strip()
    home_all_path = input("2/5 - Hazai ALL raw txt fájl elérési útja: ").strip()
    home_home_path = input("3/5 - Hazai HOME raw txt fájl elérési útja: ").strip()
    away_all_path = input("4/5 - Vendég ALL raw txt fájl elérési útja: ").strip()
    away_away_path = input("5/5 - Vendég AWAY raw txt fájl elérési útja: ").strip()

    out_prefix = input("\nOutput fájl prefix (pl. mariehamn_sjk): ").strip()
    if not out_prefix:
        out_prefix = "extract_output"

    league_raw = read_text_file(league_path)
    home_all_raw = read_text_file(home_all_path)
    home_home_raw = read_text_file(home_home_path)
    away_all_raw = read_text_file(away_all_path)
    away_away_raw = read_text_file(away_away_path)

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

    # --- táblák ---
    league_table = build_league_table(league)
    team_table = []
    team_table.extend(build_team_table("home_all", home_all))
    team_table.extend(build_team_table("home_home", home_home))
    team_table.extend(build_team_table("away_all", away_all))
    team_table.extend(build_team_table("away_away", away_away))
    model_table = build_model_table_rows(model_rows)

    # --- mentés ---
    league_csv = Path(f"{out_prefix}_league_table.csv")
    team_csv = Path(f"{out_prefix}_team_table.csv")
    model_csv = Path(f"{out_prefix}_model_ready.csv")
    audit_txt = Path(f"{out_prefix}_audit.txt")

    write_csv(league_csv, ["metric", "value"], league_table)
    write_csv(team_csv, ["block", "metric", "L5", "L10", "All"], team_table)
    write_csv(model_csv, ["group", "feature", "value", "formula", "required_now"], model_table)

    with open(audit_txt, "w", encoding="utf-8") as f:
        f.write(audit_text)

    # --- képernyőre is ---
    pretty_print_table("LEAGUE TABLE", ["metric", "value"], league_table)
    pretty_print_table("TEAM TABLE (first 40 rows)", ["block", "metric", "L5", "L10", "All"], team_table, max_rows=40)
    pretty_print_table("MODEL-READY TABLE", ["group", "feature", "value", "formula", "required_now"], model_table)

    print("\nAUDIT REPORT")
    print("============")
    print(audit_text)

    print("\nKész.")
    print(f"- {league_csv}")
    print(f"- {team_csv}")
    print(f"- {model_csv}")
    print(f"- {audit_txt}")
    print("\nFONTOS: a százalékok 0-1 skálán vannak tárolva (pl. 41% -> 0.41).")


# If Streamlit runs this file (streamlit run main.py), prefer to import the Streamlit UI wrapper
# so the web UI shows instead of waiting on console input(). If the wrapper is absent or import fails,
# fall back to the original console main().
if __name__ == "__main__":
    try:
        import streamlit  # type: ignore
        # If streamlit is available in the environment, try to load the web wrapper.
        try:
            import streamlit_app  # noqa: F401
        except Exception:
            # If wrapper missing or failing, fall back to console behavior
            main()
    except Exception:
        # No streamlit in environment -> run console main
        main()
