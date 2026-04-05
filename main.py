import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import math
import re

# --- OKOSABB ADATGYŰJTŐ (KEZELI A MATEKOT) ---
def safe_parse_75(text):
    results = {}
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Keressük a sort: Sorszám az elején
        first_num_match = re.match(r'^(\d+)', line)
        if first_num_match:
            idx = int(first_num_match.group(1))
            
            # Kikeressük az összes számot és a plusz jelet a sor végéről
            # Ez megtalálja a "4.2 + 5.1" formátumot is
            math_part = re.findall(r"[\d.]+\s*\+\s*[\d.]+|[\d.]+", line)
            if math_part:
                val_str = math_part[-1] # Az utolsó matematikai kifejezés a sorban
                if '+' in val_str:
                    # Ha van benne plusz jel, összeadjuk a részeket
                    parts = val_str.split('+')
                    val = sum(float(p.strip()) for p in parts)
                else:
                    val = float(val_str)
                
                if 1 <= idx <= 75:
                    results[idx] = val
    return results

# --- UI ---
st.set_page_config(page_title="Modell 2.1 - Smart Calc", layout="wide")
st.title("🛡️ Modell 2.1 - Automata Matek Verzió")

st.info("Itt már nem kell az AI-nak számolnia. Ha beírod, hogy '4.2 + 5.1', az app összeadja!")

summary_text = st.text_area("Másold be a 75 soros listát:", height=300)

if st.button("📊 ELEMZÉS ÉS MATEK INDÍTÁSA"):
    d = safe_parse_75(summary_text)
    
    if len(d) < 75:
        missing = [i for i in range(1, 76) if i not in d]
        st.error(f"❌ HIBA: Hiányzó sorszámok: {missing}")
        st.stop()
    
    # Checksum ellenőrzés
    current_checksum = sum(d.values())
    st.metric(label="📊 App által számolt Checksum", value=f"{current_checksum:.4f}")

    # --- MATEK (Alkotmány szerint) ---
    h_da_sa = (d[12] * 0.3) + (d[32] * 0.7)
    h_sot_sa = (d[15] * 0.3) + (d[34] * 0.7)
    h_sib_sa = (d[18] * 0.3) + (d[36] * 0.7)
    h_sob_sa = (d[21] * 0.3) + (d[38] * 0.7)
    h_against_sa = (d[24] * 0.3) + (d[40] * 0.7)
    
    a_da_sa = (d[45] * 0.3) + (d[65] * 0.7)
    a_sot_sa = (d[48] * 0.3) + (d[67] * 0.7)
    a_sib_sa = (d[51] * 0.3) + (d[69] * 0.7)
    a_sob_sa = (d[54] * 0.3) + (d[71] * 0.7)
    a_against_sa = (d[57] * 0.3) + (d[73] * 0.7)

    l_da_h, l_sot_h, l_sib_h, l_sob_h, l_ct_h = d[5]/2, d[6]/2, d[7]/2, d[8]/2, d[1]/2

    def calc_ai(da, sot, sib, sob):
        return (da/l_da_h)*0.35 + (sot/l_sot_h)*0.25 + (sib/l_sib_h)*0.25 + (sob/l_sob_h)*0.15

    h_ai = calc_ai(h_da_sa, h_sot_sa, h_sib_sa, h_sob_sa)
    a_ai = calc_ai(a_da_sa, a_sot_sa, a_sib_sa, a_sob_sa)

    h_szorzo = np.clip(a_against_sa / l_ct_h, 0.85, 1.15)
    a_szorzo = np.clip(h_against_sa / l_ct_h, 0.85, 1.15)
    
    mu_h, mu_a = (l_ct_h * h_ai) * h_szorzo, (l_ct_h * a_ai) * a_szorzo

    da_rel = ((d[26] + d[59]) / 2) / l_da_h
    da_boost = max(0, (pow(da_rel, 1.5) - 1) * 0.12)
    over_rel = ((d[27] + d[60]) / 2) / d[9]
    vol_boost = max(0, (over_rel - 1) * 0.20)
    isz = np.clip(1.0 + da_boost + vol_boost, 1.0, 1.3)

    final_h, final_a = mu_h * isz, mu_a * isz

    # --- EREDMÉNYEK ---
    st.subheader("🏁 Tippek (Arany Zóna 80-96%)")
    def get_tips(m):
        return [f"Több mint {k} ({1-poisson.cdf(k, m):.1%})" for k in range(0, 15) if 0.80 <= (1-poisson.cdf(k, m)) <= 0.96]

    res = []
    for t in get_tips(final_h + final_a): res.append(["Összesített", t])
    for t in get_tips(final_h): res.append(["Hazai", t])
    for t in get_tips(final_a): res.append(["Vendég", t])

    if res:
        st.table(pd.DataFrame(res, columns=["Kategória", "Tipp"]))
    else:
        st.info("Nincs tipp az Arany Zónában.")

    with st.expander("🔍 Adatellenőrzés (Itt látod az összeadott értékeket)"):
        check_df = pd.DataFrame([{"Sorszám": i, "Érték": d[i]} for i in range(1, 76)])
        st.dataframe(check_df, height=300)
              
