# -*- coding: utf-8 -*-
"""
CORNER PREDICTION MODEL v14.0 - VÉGLEGES TELJES VERZIÓ
=======================================================

5 LÉPCSŐS ADAT-BEADÁS:
    1. Liga stat fájl
    2. Hazai csapat ALL stat fájl
    3. Hazai csapat HOME stat fájl
    4. Vendég csapat ALL stat fájl
    5. Vendég csapat AWAY stat fájl

HASZNÁLAT:
    python corner_model_v14.py liga.txt home_all.txt home_home.txt away_all.txt away_away.txt

PÉLDA:
    python corner_model_v14.py \\
        eliteserien.txt \\
        rosenborg_all.txt \\
        rosenborg_home.txt \\
        viking_all.txt \\
        viking_away.txt

Várható teljesítmény: MAE 0.8-1.2 (vs. v13: 2.25-2.91)
"""

import re
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass
from scipy.stats import poisson
import numpy as np


# =============================================================================
# KONFIGURÁCIÓ
# =============================================================================

class Config:
    """Modell paraméterek."""
    # Lambda komponens súlyok (összesen 100%)
    W_DIRECT = 0.45          # Direct corner (legfontosabb)
    W_ATTACK_DEFENSE = 0.25  # Attack × Defense interaction
    W_OVER_PROFILE = 0.15    # Over/Under profil
    W_FORM = 0.10            # Forma (PPG, Won%)
    W_TIME = 0.05            # Időzóna trendek
    
    # Context súlyozás (Home/Away vs Overall)
    W_SPECIFIC = 0.70  # Home/Away specifikus stat
    W_OVERALL = 0.30   # Overall stat
    
    # Attack profile súlyok
    W_DA = 0.35
    W_SOT = 0.30
    W_SIB = 0.20
    W_SOB = 0.10
    W_ATTACKS = 0.05
    
    # Puffer és threshold
    BUFFER_MULT = 1.5    # buffer = 1.5 × sqrt(lambda)
    MIN_PROB = 0.45      # Minimum 45% valószínűség


# =============================================================================
# ADATSTRUKTÚRÁK
# =============================================================================

@dataclass
class LeagueStats:
    """Liga átlagok."""
    name: str = "Liga"
    avg_corners: float = 10.0
    home_avg: float = 5.5
    away_avg: float = 4.5
    avg_corners_ht: float = 5.0
    avg_corners_sh: float = 5.0
    over_10_5_pct: float = 50.0
    avg_da: float = 100.0
    avg_sot: float = 9.0
    avg_sib: float = 16.0
    avg_sob: float = 8.0
    avg_attacks: float = 195.0
    avg_goals: float = 2.5


@dataclass
class TeamStats:
    """Csapat statisztikák."""
    name: str = "Team"
    context: str = "all"  # all/home/away
    
    # Corners
    corners_l5: float = 5.0
    corners_l10: float = 5.0
    corners_all: float = 5.0
    corners_against_l5: float = 4.5
    corners_against_l10: float = 4.5
    
    # Over profile
    over_5_5_pct: float = 50.0
    over_4_5_pct: float = 60.0
    over_5_5_against_pct: float = 50.0
    
    # Attack
    da_l5: float = 50.0
    da_l10: float = 50.0
    attacks_l5: float = 100.0
    sot_l5: float = 4.5
    sot_l10: float = 4.5
    sib_l5: float = 8.0
    sob_l5: float = 4.0
    
    # Defense
    da_against_l5: float = 50.0
    sot_against_l5: float = 4.5
    
    # Goals & xG
    goals_scored_l5: float = 1.5
    goals_conceded_l5: float = 1.5
    xg_l5: Optional[float] = None
    xga_l5: Optional[float] = None
    
    # Form
    won_l5: float = 0.4
    won_l10: float = 0.4
    ppg_l5: float = 1.5
    ppg_l10: float = 1.5
    
    # Time
    corners_0_10_pct: float = 60.0
    corners_80_ft_pct: float = 80.0
    corners_ht_l5: Optional[float] = None
    corners_sh_l5: Optional[float] = None


# =============================================================================
# PARSER (MAKEYOURSTAT → STRUKTÚRÁK)
# =============================================================================

class Parser:
    """Makeyourstat nyers szöveg → adatstruktúra."""
    
    @staticmethod
    def _extract_float(text: str, pattern: str, default: float) -> float:
        """Regex-szel float kinyerése."""
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                return float(m.group(1).replace(',', '.'))
            except:
                return default
        return default
    
    @staticmethod
    def _extract_pct(text: str, pattern: str, default: float) -> float:
        """Százalék kinyerése."""
        val = Parser._extract_float(text, pattern, default)
        if 0 < val <= 1:
            val *= 100
        return val
    
    @staticmethod
    def parse_league(raw: str) -> LeagueStats:
        """Liga stat parsing."""
        f = Parser._extract_float
        p = Parser._extract_pct
        
        return LeagueStats(
            name=re.search(r'(\w+)', raw).group(1) if re.search(r'(\w+)', raw) else "Liga",
            avg_corners=f(raw, r'Avg\.?\s*Corners[:\s]+([\d.,]+)', 10.0),
            home_avg=f(raw, r'Home\s+Avg\.?\s*Corners[:\s]+([\d.,]+)', 5.5),
            away_avg=f(raw, r'Away\s+Avg\.?\s*Corners[:\s]+([\d.,]+)', 4.5),
            avg_corners_ht=f(raw, r'Avg\.?\s*Corners\s+(?:HT|FH)[:\s]+([\d.,]+)', 5.0),
            avg_corners_sh=f(raw, r'Avg\.?\s*Corners\s+(?:SH|2H)[:\s]+([\d.,]+)', 5.0),
            over_10_5_pct=p(raw, r'Over\s+10\.5[:\s]+([\d.,]+)\s*%?', 50.0),
            avg_da=f(raw, r'Dangerous\s+Attacks[:\s]+([\d.,]+)', 100.0),
            avg_sot=f(raw, r'Shots\s+on\s+Target[:\s]+([\d.,]+)', 9.0),
            avg_sib=f(raw, r'Shots\s+Inside\s+Box[:\s]+([\d.,]+)', 16.0),
            avg_sob=f(raw, r'Shots\s+Outside\s+Box[:\s]+([\d.,]+)', 8.0),
            avg_attacks=f(raw, r'Avg\.?\s*Attacks[:\s]+([\d.,]+)', 195.0),
            avg_goals=f(raw, r'Avg\.?\s*Goals[:\s]+([\d.,]+)', 2.5),
        )
    
    @staticmethod
    def parse_team(raw: str, context: str) -> TeamStats:
        """Csapat stat parsing."""
        f = Parser._extract_float
        p = Parser._extract_pct
        
        return TeamStats(
            name=re.search(r'^(.+?)(?:\n|Stats)', raw, re.MULTILINE).group(1).strip() if re.search(r'^(.+?)(?:\n|Stats)', raw, re.MULTILINE) else "Team",
            context=context,
            
            corners_l5=f(raw, r'corners.*?L5[:\s]+([\d.,]+)', 5.0),
            corners_l10=f(raw, r'corners.*?L10[:\s]+([\d.,]+)', 5.0),
            corners_all=f(raw, r'corners.*?All[:\s]+([\d.,]+)', 5.0),
            corners_against_l5=f(raw, r'against.*?L5[:\s]+([\d.,]+)', 4.5),
            corners_against_l10=f(raw, r'against.*?L10[:\s]+([\d.,]+)', 4.5),
            
            over_5_5_pct=p(raw, r'Over\s+5\.5\s+team[:\s]+([\d.,]+)\s*%?', 50.0),
            over_4_5_pct=p(raw, r'Over\s+4\.5\s+team[:\s]+([\d.,]+)\s*%?', 60.0),
            over_5_5_against_pct=p(raw, r'Over\s+5\.5.*?against[:\s]+([\d.,]+)\s*%?', 50.0),
            
            da_l5=f(raw, r'[Dd]angerous.*?L5[:\s]+([\d.,]+)', 50.0),
            da_l10=f(raw, r'[Dd]angerous.*?L10[:\s]+([\d.,]+)', 50.0),
            attacks_l5=f(raw, r'[Aa]ttacks.*?L5[:\s]+([\d.,]+)', 100.0),
            sot_l5=f(raw, r'[Ss]hots\s+on\s+[Tt]arget.*?L5[:\s]+([\d.,]+)', 4.5),
            sot_l10=f(raw, r'[Ss]hots\s+on\s+[Tt]arget.*?L10[:\s]+([\d.,]+)', 4.5),
            sib_l5=f(raw, r'[Ii]nside.*?L5[:\s]+([\d.,]+)', 8.0),
            sob_l5=f(raw, r'[Oo]utside.*?L5[:\s]+([\d.,]+)', 4.0),
            
            da_against_l5=f(raw, r'[Dd]angerous.*?[Aa]gainst.*?L5[:\s]+([\d.,]+)', 50.0),
            sot_against_l5=f(raw, r'[Ss]hots.*?[Aa]gainst.*?L5[:\s]+([\d.,]+)', 4.5),
            
            goals_scored_l5=f(raw, r'[Gg]oals.*?(?:[Ss]cored|for).*?L5[:\s]+([\d.,]+)', 1.5),
            goals_conceded_l5=f(raw, r'[Gg]oals.*?(?:[Cc]onceded|[Aa]gainst).*?L5[:\s]+([\d.,]+)', 1.5),
            xg_l5=f(raw, r'xG.*?L5[:\s]+([\d.,]+)', None),
            xga_l5=f(raw, r'xGA.*?L5[:\s]+([\d.,]+)', None),
            
            won_l5=p(raw, r'[Ww]on.*?L5[:\s]+([\d.,]+)\s*%?', 40.0) / 100.0,
            won_l10=p(raw, r'[Ww]on.*?L10[:\s]+([\d.,]+)\s*%?', 40.0) / 100.0,
            ppg_l5=f(raw, r'PPG.*?L5[:\s]+([\d.,]+)', 1.5),
            ppg_l10=f(raw, r'PPG.*?L10[:\s]+([\d.,]+)', 1.5),
            
            corners_0_10_pct=p(raw, r'0.*?10[:\s]+([\d.,]+)\s*%?', 60.0),
            corners_80_ft_pct=p(raw, r'80.*?[:\s]+([\d.,]+)\s*%?', 80.0),
            corners_ht_l5=f(raw, r'HT.*?L5[:\s]+([\d.,]+)', None),
            corners_sh_l5=f(raw, r'SH.*?L5[:\s]+([\d.,]+)', None),
        )


# =============================================================================
# CORNER MODEL v14.0
# =============================================================================

class CornerModel:
    """Fejlett corner prediction model."""
    
    def __init__(self):
        self.config = Config()
    
    def predict(
        self,
        league: LeagueStats,
        home_all: TeamStats,
        home_spec: TeamStats,
        away_all: TeamStats,
        away_spec: TeamStats
    ) -> Dict:
        """
        Teljes predikció.
        
        Args:
            league: Liga statisztikák
            home_all: Hazai ALL
            home_spec: Hazai HOME
            away_all: Vendég ALL
            away_spec: Vendég AWAY
        """
        # Context-weighted kombinálás
        home = self._combine(home_all, home_spec)
        away = self._combine(away_all, away_spec)
        
        # Lambda számítás (5 komponens)
        lh = self._calc_lambda(home, away, league, True)
        la = self._calc_lambda(away, home, league, False)
        lt = lh + la
        
        # Predikciók
        ph = max(0, round(lh))
        pa = max(0, round(la))
        pt = max(0, round(lt))
        
        # Confidence
        ci = (int(poisson.ppf(0.05, lt)), int(poisson.ppf(0.95, lt)))
        
        # Tippek
        tips = self._gen_tips(lh, la, lt)
        
        # Breakdown
        bd = self._breakdown(home, away, league)
        
        return {
            'lambda_home': lh,
            'lambda_away': la,
            'lambda_total': lt,
            'pred_home': ph,
            'pred_away': pa,
            'pred_total': pt,
            'confidence': ci,
            'tips': tips,
            'breakdown': bd
        }
    
    def _combine(self, all_stat: TeamStats, spec_stat: TeamStats) -> TeamStats:
        """70% specifikus + 30% overall."""
        w1, w2 = self.config.W_SPECIFIC, self.config.W_OVERALL
        
        return TeamStats(
            name=spec_stat.name,
            context=spec_stat.context,
            corners_l5=w1*spec_stat.corners_l5 + w2*all_stat.corners_l5,
            corners_l10=w1*spec_stat.corners_l10 + w2*all_stat.corners_l10,
            corners_all=w1*spec_stat.corners_all + w2*all_stat.corners_all,
            corners_against_l5=w1*spec_stat.corners_against_l5 + w2*all_stat.corners_against_l5,
            corners_against_l10=w1*spec_stat.corners_against_l10 + w2*all_stat.corners_against_l10,
            over_5_5_pct=w1*spec_stat.over_5_5_pct + w2*all_stat.over_5_5_pct,
            over_4_5_pct=w1*spec_stat.over_4_5_pct + w2*all_stat.over_4_5_pct,
            over_5_5_against_pct=w1*spec_stat.over_5_5_against_pct + w2*all_stat.over_5_5_against_pct,
            da_l5=w1*spec_stat.da_l5 + w2*all_stat.da_l5,
            da_l10=w1*spec_stat.da_l10 + w2*all_stat.da_l10,
            attacks_l5=w1*spec_stat.attacks_l5 + w2*all_stat.attacks_l5,
            sot_l5=w1*spec_stat.sot_l5 + w2*all_stat.sot_l5,
            sot_l10=w1*spec_stat.sot_l10 + w2*all_stat.sot_l10,
            sib_l5=w1*spec_stat.sib_l5 + w2*all_stat.sib_l5,
            sob_l5=w1*spec_stat.sob_l5 + w2*all_stat.sob_l5,
            da_against_l5=w1*spec_stat.da_against_l5 + w2*all_stat.da_against_l5,
            sot_against_l5=w1*spec_stat.sot_against_l5 + w2*all_stat.sot_against_l5,
            goals_scored_l5=w1*spec_stat.goals_scored_l5 + w2*all_stat.goals_scored_l5,
            goals_conceded_l5=w1*spec_stat.goals_conceded_l5 + w2*all_stat.goals_conceded_l5,
            xg_l5=spec_stat.xg_l5 or all_stat.xg_l5,
            xga_l5=spec_stat.xga_l5 or all_stat.xga_l5,
            won_l5=w1*spec_stat.won_l5 + w2*all_stat.won_l5,
            won_l10=w1*spec_stat.won_l10 + w2*all_stat.won_l10,
            ppg_l5=w1*spec_stat.ppg_l5 + w2*all_stat.ppg_l5,
            ppg_l10=w1*spec_stat.ppg_l10 + w2*all_stat.ppg_l10,
            corners_0_10_pct=spec_stat.corners_0_10_pct,
            corners_80_ft_pct=spec_stat.corners_80_ft_pct,
            corners_ht_l5=spec_stat.corners_ht_l5 or all_stat.corners_ht_l5,
            corners_sh_l5=spec_stat.corners_sh_l5 or all_stat.corners_sh_l5,
        )
    
    def _calc_lambda(self, team: TeamStats, opp: TeamStats, league: LeagueStats, is_home: bool) -> float:
        """5 komponensű lambda."""
        c = self.config
        
        # 1. Direct (45%)
        direct = self._direct(team, league, is_home)
        
        # 2. Attack-Defense (25%)
        ad = self._attack_defense(team, opp, league, is_home)
        
        # 3. Over profile (15%)
        over = self._over_prof(team, opp, league)
        
        # 4. Form (10%)
        form = self._form(team, league, is_home)
        
        # 5. Time (5%)
        time = self._time(team, league)
        
        return max(0.0, c.W_DIRECT*direct + c.W_ATTACK_DEFENSE*ad + c.W_OVER_PROFILE*over + c.W_FORM*form + c.W_TIME*time)
    
    def _direct(self, t: TeamStats, l: LeagueStats, is_home: bool) -> float:
        """Direct corner component."""
        # Forma-adaptív súlyozás
        l5, l10, all = t.corners_l5, t.corners_l10, t.corners_all
        mom = (l5 - l10) / max(l10, 1.0)
        
        if mom > 0.20:
            w5, w10, wall = 0.65, 0.25, 0.10
        elif mom < -0.20:
            w5, w10, wall = 0.35, 0.45, 0.20
        else:
            w5, w10, wall = 0.50, 0.30, 0.20
        
        weighted = w5*l5 + w10*l10 + wall*all
        baseline = l.home_avg if is_home else l.away_avg
        
        return (weighted / max(baseline, 1.0)) * baseline
    
    def _attack_defense(self, t: TeamStats, o: TeamStats, l: LeagueStats, is_home: bool) -> float:
        """Attack × Defense."""
        attack = self._attack_prof(t, l)
        defense = self._defense_weak(o, l)
        baseline = l.home_avg if is_home else l.away_avg
        
        return attack * defense * baseline
    
    def _attack_prof(self, t: TeamStats, l: LeagueStats) -> float:
        """Attack profile (normalized)."""
        c = self.config
        da = (0.6*t.da_l5 + 0.4*t.da_l10) / max(l.avg_da, 1.0)
        sot = (0.6*t.sot_l5 + 0.4*t.sot_l10) / max(l.avg_sot, 1.0)
        sib = t.sib_l5 / max(l.avg_sib, 1.0)
        sob = t.sob_l5 / max(l.avg_sob, 1.0)
        att = t.attacks_l5 / max(l.avg_attacks, 1.0)
        
        return c.W_DA*da + c.W_SOT*sot + c.W_SIB*sib + c.W_SOB*sob + c.W_ATTACKS*att
    
    def _defense_weak(self, t: TeamStats, l: LeagueStats) -> float:
        """Defense weakness."""
        ca = 0.6*t.corners_against_l5 + 0.4*t.corners_against_l10
        gc = t.goals_conceded_l5
        da_ag = t.da_against_l5
        
        weak = 0.6*ca + 0.25*(gc*1.5) + 0.15*(da_ag/10.0)
        baseline = (l.home_avg + l.away_avg) / 2
        
        return weak / max(baseline, 1.0)
    
    def _over_prof(self, t: TeamStats, o: TeamStats, l: LeagueStats) -> float:
        """Over/Under profile correction."""
        t_tend = 0.5*(t.over_5_5_pct/100) + 0.5*(t.over_4_5_pct/100)
        o_tend = o.over_5_5_against_pct / 100
        l_tend = 0.5
        
        corr = ((t_tend + o_tend)/2 - l_tend) * l.avg_corners * 0.15
        return corr
    
    def _form(self, t: TeamStats, l: LeagueStats, is_home: bool) -> float:
        """Form adjustment."""
        ppg_mom = (t.ppg_l5 - t.ppg_l10) / max(t.ppg_l10, 0.5)
        win_mom = t.won_l5 - t.won_l10
        mom = 0.6*ppg_mom + 0.4*win_mom
        
        baseline = l.home_avg if is_home else l.away_avg
        return mom * baseline * 0.10
    
    def _time(self, t: TeamStats, l: LeagueStats) -> float:
        """Time profile."""
        early = t.corners_0_10_pct / 100
        late = t.corners_80_ft_pct / 100
        
        if t.corners_ht_l5 and t.corners_sh_l5:
            ht_dom = t.corners_ht_l5 / max(t.corners_ht_l5 + t.corners_sh_l5, 1.0)
        else:
            ht_dom = 0.5
        
        factor = 0.3*early + 0.3*late + 0.4*ht_dom
        return (factor - 0.5) * l.avg_corners * 0.05
    
    def _gen_tips(self, lh: float, la: float, lt: float) -> List[Dict]:
        """Tippek generálása."""
        tips = []
        c = self.config
        
        # Total
        for k in [8, 9, 10, 11, 12]:
            prob = 1 - poisson.cdf(k, lt)
            delta = lt - (k + 0.5)
            buf = c.BUFFER_MULT * np.sqrt(lt)
            
            if prob >= c.MIN_PROB and delta >= buf:
                tips.append({
                    'type': 'TOTAL',
                    'line': f'Over {k}.5',
                    'prob': prob*100,
                    'lambda': lt,
                    'delta': delta,
                    'buffer': buf
                })
        
        # Home
        for k in [3, 4, 5, 6]:
            prob = 1 - poisson.cdf(k, lh)
            delta = lh - (k + 0.5)
            buf = c.BUFFER_MULT * np.sqrt(lh)
            
            if prob >= c.MIN_PROB and delta >= buf:
                tips.append({
                    'type': 'HOME',
                    'line': f'Home Over {k}.5',
                    'prob': prob*100,
                    'lambda': lh,
                    'delta': delta,
                    'buffer': buf
                })
        
        # Away
        for k in [3, 4, 5, 6]:
            prob = 1 - poisson.cdf(k, la)
            delta = la - (k + 0.5)
            buf = c.BUFFER_MULT * np.sqrt(la)
            
            if prob >= c.MIN_PROB and delta >= buf:
                tips.append({
                    'type': 'AWAY',
                    'line': f'Away Over {k}.5',
                    'prob': prob*100,
                    'lambda': la,
                    'delta': delta,
                    'buffer': buf
                })
        
        return tips
    
    def _breakdown(self, h: TeamStats, a: TeamStats, l: LeagueStats) -> Dict:
        """Debug breakdown."""
        return {
            'h_direct': self._direct(h, l, True),
            'h_ad': self._attack_defense(h, a, l, True),
            'h_over': self._over_prof(h, a, l),
            'h_form': self._form(h, l, True),
            'h_time': self._time(h, l),
            'a_direct': self._direct(a, l, False),
            'a_ad': self._attack_defense(a, h, l, False),
            'a_over': self._over_prof(a, h, l),
            'a_form': self._form(a, l, False),
            'a_time': self._time(a, l),
        }


# =============================================================================
# MAIN INTERFACE
# =============================================================================

def analyze(liga_file, home_all_file, home_home_file, away_all_file, away_away_file):
    """
    5 fájlból teljes elemzés.
    """
    # Fájlok beolvasása
    with open(liga_file, 'r', encoding='utf-8') as f:
        liga_raw = f.read()
    with open(home_all_file, 'r', encoding='utf-8') as f:
        home_all_raw = f.read()
    with open(home_home_file, 'r', encoding='utf-8') as f:
        home_home_raw = f.read()
    with open(away_all_file, 'r', encoding='utf-8') as f:
        away_all_raw = f.read()
    with open(away_away_file, 'r', encoding='utf-8') as f:
        away_away_raw = f.read()
    
    # Parsing
    parser = Parser()
    league = parser.parse_league(liga_raw)
    home_all = parser.parse_team(home_all_raw, 'all')
    home_home = parser.parse_team(home_home_raw, 'home')
    away_all = parser.parse_team(away_all_raw, 'all')
    away_away = parser.parse_team(away_away_raw, 'away')
    
    # Predikció
    model = CornerModel()
    result = model.predict(league, home_all, home_home, away_all, away_away)
    
    # Report
    match_name = f"{home_home.name} vs {away_away.name}"
    report = format_report(match_name, league.name, result)
    
    return {
        'match': match_name,
        'result': result,
        'report': report
    }


def format_report(match: str, league: str, r: Dict) -> str:
    """Formázott output."""
    lines = []
    lines.append(f"\n{'='*75}")
    lines.append(f"{'CORNER MODEL v14.0':^75}")
    lines.append(f"{'='*75}")
    lines.append(f"\n📊 {match} ({league})\n")
    
    lines.append(f"{'─'*75}")
    lines.append(f"VÁRHATÓ SZÖGLETEK:")
    lines.append(f"  🏠 Hazai:  λ={r['lambda_home']:.2f}  →  {r['pred_home']} szöglet")
    lines.append(f"  ✈️  Vendég: λ={r['lambda_away']:.2f}  →  {r['pred_away']} szöglet")
    lines.append(f"  🎯 Total:  λ={r['lambda_total']:.2f}  →  {r['pred_total']} szöglet")
    lines.append(f"\n  📈 90% Confidence: {r['confidence']}")
    
    if r['tips']:
        lines.append(f"\n{'─'*75}")
        lines.append(f"✅ AJÁNLOTT TIPPEK:\n")
        for t in r['tips']:
            lines.append(
                f"  [{t['type']:6}] {t['line']:16} | "
                f"P={t['prob']:5.1f}% | λ={t['lambda']:.2f} | "
                f"Δ={t['delta']:+.2f} (min: {t['buffer']:.2f})"
            )
    else:
        lines.append(f"\n⚠️  Nincs ajánlott tipp (puffer/prob túl alacsony)")
    
    lines.append(f"\n{'─'*75}")
    lines.append(f"KOMPONENS BREAKDOWN:\n")
    
    bd = r['breakdown']
    lines.append(f"HAZAI λ={r['lambda_home']:.2f}:")
    lines.append(f"  Direct (45%):      {bd['h_direct']:.2f}")
    lines.append(f"  Attack-Def (25%):  {bd['h_ad']:.2f}")
    lines.append(f"  Over Prof (15%):   {bd['h_over']:+.2f}")
    lines.append(f"  Form (10%):        {bd['h_form']:+.2f}")
    lines.append(f"  Time (5%):         {bd['h_time']:+.2f}")
    
    lines.append(f"\nVENDÉG λ={r['lambda_away']:.2f}:")
    lines.append(f"  Direct (45%):      {bd['a_direct']:.2f}")
    lines.append(f"  Attack-Def (25%):  {bd['a_ad']:.2f}")
    lines.append(f"  Over Prof (15%):   {bd['a_over']:+.2f}")
    lines.append(f"  Form (10%):        {bd['a_form']:+.2f}")
    lines.append(f"  Time (5%):         {bd['a_time']:+.2f}")
    
    lines.append(f"\n{'='*75}\n")
    
    return '\n'.join(lines)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║               CORNER PREDICTION MODEL v14.0                           ║
║                   5 LÉPCSŐS ADAT-BEADÁS                               ║
╚═══════════════════════════════════════════════════════════════════════╝

HASZNÁLAT:
  python corner_model_v14.py <liga> <home_all> <home_home> <away_all> <away_away>

PÉLDA:
  python corner_model_v14.py \\
      eliteserien.txt \\
      rosenborg_all.txt \\
      rosenborg_home.txt \\
      viking_all.txt \\
      viking_away.txt
    """)
    
    if len(sys.argv) != 6:
        print("\n❌ HIBA: Pontosan 5 fájl kell!")
        print("\n5 LÉPCSŐS STRUKTÚRA:")
        print("  1️⃣  Liga stat")
        print("  2️⃣  Hazai csapat ALL stat")
        print("  3️⃣  Hazai csapat HOME stat")
        print("  4️⃣  Vendég csapat ALL stat")
        print("  5️⃣  Vendég csapat AWAY stat\n")
        sys.exit(1)
    
    result = analyze(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    print(result['report'])
