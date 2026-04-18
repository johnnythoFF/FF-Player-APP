import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict
import os
import glob

st.set_page_config(
    page_title="Player Profiler",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.6rem !important; }
</style>
""", unsafe_allow_html=True)


# ── PARSE CSV ─────────────────────────────────────────────────────────────────

def parse_csv(file):
    return pd.read_csv(file)


def aggregate_stats(df):
    players = defaultdict(lambda: {
        'passes_complete': 0, 'passes_incomplete': 0,
        'shots': 0, 'sot': 0,
        'def_actions': 0, 'interceptions': 0,
        'turnovers': 0, 'crosses': 0, 'crosses_complete': 0
    })

    for _, row in df.iterrows():
        name = str(row.get('Row', '')).strip()
        if not name or name == 'Team Actions' or name == 'nan':
            continue

        pass_outcome = str(row.get('Pass Outcome', '')).strip()
        if pass_outcome == 'Complete':
            players[name]['passes_complete'] += 1
        elif pass_outcome == 'Incomplete':
            players[name]['passes_incomplete'] += 1

        shots = str(row.get('Shots', '')).strip()
        if shots and shots != 'nan':
            players[name]['shots'] += 1
            if 'SHOT ON TARGET' in shots:
                players[name]['sot'] += 1

        def_action = str(row.get('Defending Actions', '')).strip()
        if def_action and def_action != 'nan':
            players[name]['def_actions'] += 1
            if 'INTERCEPTION' in def_action:
                players[name]['interceptions'] += 1

        turnover = str(row.get('Turnover', '')).strip()
        if turnover and turnover != 'nan':
            players[name]['turnovers'] += 1

        cross = str(row.get('Cross Outcome', '')).strip()
        if cross and cross != 'nan':
            players[name]['crosses'] += 1
            if cross == 'Teammate Found':
                players[name]['crosses_complete'] += 1

    result = {}
    for name, stats in players.items():
        total = stats['passes_complete'] + stats['passes_incomplete']
        pass_pct = round(stats['passes_complete'] / total * 100) if total else 0
        result[name] = {**stats, 'total_passes': total, 'pass_pct': pass_pct}
    return result


def merge_games(all_games):
    merged = {}
    for game_name, game_stats in all_games.items():
        for name, stats in game_stats.items():
            if name not in merged:
                merged[name] = {**stats, 'games': 1}
            else:
                for k in ['passes_complete','passes_incomplete','shots','sot','def_actions','interceptions','turnovers','crosses','crosses_complete']:
                    merged[name][k] += stats[k]
                merged[name]['games'] += 1

    for name in merged:
        total = merged[name]['passes_complete'] + merged[name]['passes_incomplete']
        merged[name]['total_passes'] = total
        merged[name]['pass_pct'] = round(merged[name]['passes_complete'] / total * 100) if total else 0

    return merged


# ── MATCH REPORT HELPERS ──────────────────────────────────────────────────────

def get_player_rows(df, player_name):
    return df[df['Row'] == player_name].copy().reset_index(drop=True)

def count_val(series, keyword):
    return series.fillna('').str.contains(keyword, case=False, na=False).sum()

def count_instances(series, keyword):
    return sum(str(v).upper().count(keyword.upper()) for v in series.fillna(''))

def parse_match_report(df, player_name):
    rows = get_player_rows(df, player_name)
    if rows.empty:
        return None

    # ── SHOOTING ──────────────────────────────────────────────────────────────
    shots_col = rows['Shots'].fillna('')
    total_shots   = count_val(shots_col, 'SHOT')
    sot           = count_val(shots_col, 'SHOT ON TARGET')
    shot_assist   = count_val(shots_col, 'SHOT ASSIST')
    scoring_col   = rows['Scoring'].fillna('') if 'Scoring' in rows.columns else pd.Series([''] * len(rows))
    goals         = count_val(scoring_col, 'GOAL')

    # Shot locations
    shot_locations = rows['Shooting Heat Graph'].dropna().tolist() if 'Shooting Heat Graph' in rows.columns else []

    # ── PASSING ───────────────────────────────────────────────────────────────
    pass_outcome = rows['Pass Outcome'].fillna('')
    passes_complete   = count_val(pass_outcome, 'Complete')
    passes_incomplete = count_val(pass_outcome, 'Incomplete')
    total_passes = passes_complete + passes_incomplete
    pass_pct     = round(passes_complete / total_passes * 100) if total_passes else 0

    pass_type_col = rows['Pass Type'].fillna('') if 'Pass Type' in rows.columns else pd.Series([''] * len(rows))
    through_total   = count_val(pass_type_col, 'Through')
    around_total    = count_val(pass_type_col, 'Around')
    backwards_total = count_val(pass_type_col, 'Backwards')
    neutral_total   = count_val(pass_type_col, 'Neutral')
    over_total      = count_val(pass_type_col, 'Over')

    # Pass completion per type (rows where that type appears + outcome)
    def type_completion(keyword):
        mask = pass_type_col.str.contains(keyword, case=False, na=False)
        subset = pass_outcome[mask]
        c = count_val(subset, 'Complete')
        i = count_val(subset, 'Incomplete')
        total = c + i
        return c, i, round(c/total*100) if total else 0

    through_c, through_i, through_pct     = type_completion('Through')
    around_c, around_i, around_pct       = type_completion('Around')
    backwards_c, backwards_i, backwards_pct = type_completion('Backwards')
    neutral_c, neutral_i, neutral_pct     = type_completion('Neutral')
    over_c, over_i, over_pct             = type_completion('Over')

    pass_dest_col = rows['Pass Destination'].fillna('') if 'Pass Destination' in rows.columns else pd.Series([''] * len(rows))
    passes_f3  = count_val(pass_dest_col, 'Pass into F3')
    passes_box = count_val(pass_dest_col, 'Pass into box')

    # Pass into F3 completion
    def dest_completion(keyword):
        mask = pass_dest_col.str.contains(keyword, case=False, na=False)
        subset = pass_outcome[mask]
        c = count_val(subset, 'Complete')
        i = count_val(subset, 'Incomplete')
        total = c + i
        return c, i, round(c/total*100) if total else 0

    f3_c, f3_i, f3_pct   = dest_completion('Pass into F3')
    box_c, box_i, box_pct = dest_completion('Pass into box')

    # Receives
    recv_col = rows['Receiving Type'].fillna('') if 'Receiving Type' in rows.columns else pd.Series([''] * len(rows))
    recv_seam1   = count_val(recv_col, 'Seam 1')
    recv_seam2   = count_val(recv_col, 'Seam 2')
    recv_seam3   = count_val(recv_col, 'Seam 3')
    recv_neutral = count_val(recv_col, 'Neutral')
    recv_below   = count_val(recv_col, 'Below')
    recv_total   = recv_seam1 + recv_seam2 + recv_seam3 + recv_neutral + recv_below

    # ── DEFENDING ─────────────────────────────────────────────────────────────
    def_col = rows['Defending Actions'].fillna('') if 'Defending Actions' in rows.columns else pd.Series([''] * len(rows))
    def_total       = count_val(def_col, 'INTERCEPTION') + count_val(def_col, 'Ground Duel') + count_val(def_col, 'Aerial Duel')
    interceptions   = count_val(def_col, 'INTERCEPTION')
    ground_duel_w   = count_val(def_col, 'Ground Duel +')
    ground_duel_l   = count_val(def_col, 'Ground Duel -') + count_val(def_col, 'Ground Duel')
    aerial_duel_w   = count_val(def_col, 'Aerial Duel +')
    aerial_duel_l   = count_val(def_col, 'Aerial Duel -') + count_val(def_col, 'Aerial Duel')

    # ── CROSSING ──────────────────────────────────────────────────────────────
    cross_outcome_col = rows['Cross Outcome'].fillna('') if 'Cross Outcome' in rows.columns else pd.Series([''] * len(rows))
    cross_type_col    = rows['Cross Type'].fillna('') if 'Cross Type' in rows.columns else pd.Series([''] * len(rows))
    cross_orig_col    = rows['Cross Origins'].fillna('') if 'Cross Origins' in rows.columns else pd.Series([''] * len(rows))
    cross_dest_col    = rows['Cross Destination'].fillna('') if 'Cross Destination' in rows.columns else pd.Series([''] * len(rows))

    cross_total     = count_val(cross_outcome_col, 'Teammate Found') + count_val(cross_outcome_col, 'Teammate Not Found')
    cross_found     = count_val(cross_outcome_col, 'Teammate Found')
    cross_not_found = count_val(cross_outcome_col, 'Teammate Not Found')
    cross_whipped   = count_val(cross_type_col, 'Whipped')
    cross_floated   = count_val(cross_type_col, 'Floated')
    cross_cutback   = count_val(cross_type_col, 'Cut Back')
    cross_hungup    = count_val(cross_type_col, 'Hung Up')

    cross_origins      = cross_orig_col[cross_orig_col != ''].tolist()
    cross_destinations = cross_dest_col[cross_dest_col != ''].tolist()

    turnovers = count_val(rows['Turnover'].fillna('') if 'Turnover' in rows.columns else pd.Series([''] * len(rows)), 'Turnover')

    return {
        'player': player_name,
        'total_shots': total_shots, 'sot': sot, 'goals': goals, 'shot_assist': shot_assist,
        'shot_locations': shot_locations,
        'total_passes': total_passes, 'passes_complete': passes_complete,
        'passes_incomplete': passes_incomplete, 'pass_pct': pass_pct,
        'through_total': through_total, 'through_pct': through_pct,
        'around_total': around_total, 'around_pct': around_pct,
        'backwards_total': backwards_total, 'backwards_pct': backwards_pct,
        'neutral_total': neutral_total, 'neutral_pct': neutral_pct,
        'over_total': over_total, 'over_pct': over_pct,
        'passes_f3': passes_f3, 'f3_pct': f3_pct,
        'passes_box': passes_box, 'box_pct': box_pct,
        'recv_total': recv_total, 'recv_seam1': recv_seam1, 'recv_seam2': recv_seam2,
        'recv_seam3': recv_seam3, 'recv_neutral': recv_neutral, 'recv_below': recv_below,
        'def_total': def_total, 'interceptions': interceptions,
        'ground_duel_w': ground_duel_w, 'ground_duel_l': ground_duel_l,
        'aerial_duel_w': aerial_duel_w, 'aerial_duel_l': aerial_duel_l,
        'cross_total': cross_total, 'cross_found': cross_found, 'cross_not_found': cross_not_found,
        'cross_whipped': cross_whipped, 'cross_floated': cross_floated,
        'cross_cutback': cross_cutback, 'cross_hungup': cross_hungup,
        'cross_origins': cross_origins, 'cross_destinations': cross_destinations,
        'turnovers': turnovers,
    }


# ── PITCH MAPS ────────────────────────────────────────────────────────────────

# Shot location zones mapped to pitch coordinates (x, y, w, h) in 0-100 space
# Pitch: attacking half, zones from image
SL_ZONES = {
    # Top row — furthest from goal
    'SL Zone FOUR C L': ( 0, 60, 20, 40),
    'SL Zone 00 L':     (20, 60, 22, 40),
    'SL Black Box':     (30, 78, 40, 22),
    'SL Zone 00 R':     (58, 60, 22, 40),
    'SL Zone XAR':      (80, 60, 20, 40),
    # Middle — Gold Zone
    'SL Gold Zone':     (20, 35, 60, 25),
    # Bottom row — closest to goal
    'SL Zone XAL':      ( 0,  0, 20, 60),
    'SL Zone THREE C':  (20,  0, 22, 35),
    'SL Zone ONE C':    (42,  0, 16, 35),
    'SL Zone TWO C':    (58,  0, 22, 35),
    'SL Zone FOUR C R': (80,  0, 20, 60),
}

CO_ZONES = {
    'CO Zone XAL':    (0,  10, 12, 40),
    'CO Zone 00 L':   (12, 10, 20, 40),
    'CO Zone THREE C':(32, 10, 20, 40),
    'CO Zone FOUR C L':(12,50, 20, 40),
    'CO Zone 00 R':   (68, 10, 20, 40),
    'CO Zone XAR':    (88, 10, 12, 40),
    'CO Zone FOUR C R':(68,50, 20, 40),
}

CD_ZONES = {
    'CD Zone XAL':    (0,  10, 12, 40),
    'CD Zone 00 L':   (12, 10, 20, 40),
    'CD Gold Zone':   (32, 10, 36, 25),
    'CD Black Box':   (32, 0,  36, 10),
    'CD Zone 00 R':   (68, 10, 20, 40),
    'CD Zone XAR':    (88, 10, 12, 40),
    'CD Zone THREE C':(12, 50, 20, 40),
    'CD Zone ONE C':  (32, 35, 18, 30),
    'CD Zone TWO C':  (50, 35, 18, 30),
    'CD Zone FOUR C L':(12,50, 20, 40),
    'CD Zone FOUR C R':(68,50, 20, 40),
}


def draw_pitch_map(zone_counts, zone_defs, title, max_count=None):
    if max_count is None:
        max_count = max(zone_counts.values()) if zone_counts else 1

    fig = go.Figure()

    # Pitch background
    fig.add_shape(type='rect', x0=0, y0=0, x1=100, y1=100,
                  fillcolor='#3a7d2c', line=dict(color='white', width=2))
    # Halfway line at top
    fig.add_shape(type='line', x0=0, y0=100, x1=100, y1=100,
                  line=dict(color='white', width=2))
    # Penalty box at bottom
    fig.add_shape(type='rect', x0=20, y0=0, x1=80, y1=35,
                  fillcolor='rgba(0,0,0,0)', line=dict(color='white', width=2))
    # Six yard box
    fig.add_shape(type='rect', x0=37, y0=0, x1=63, y1=12,
                  fillcolor='rgba(0,0,0,0)', line=dict(color='white', width=1.5))
    # Goal at bottom
    fig.add_shape(type='rect', x0=42, y0=-5, x1=58, y1=0,
                  fillcolor='rgba(255,255,255,0.1)', line=dict(color='white', width=2))

    for zone, (x, y, w, h) in zone_defs.items():
        count = zone_counts.get(zone, 0)
        intensity = count / max_count if max_count > 0 else 0
        if intensity > 0:
            r_val = int(255 * min(intensity * 1.2, 1))
            g_val = int(60 * (1 - intensity))
            color = f'rgba({r_val},{g_val},0,{0.5 + intensity * 0.45})'
        else:
            color = 'rgba(0,0,0,0.07)'

        fig.add_shape(type='rect', x0=x, y0=y, x1=x+w, y1=y+h,
                      fillcolor=color,
                      line=dict(color='rgba(255,255,255,0.7)', width=1))

        if count > 0:
            fig.add_annotation(x=x+w/2, y=y+h/2, text=f"<b>{count}</b>",
                               showarrow=False,
                               font=dict(color='white', size=18, family='Arial Black'),
                               xref='x', yref='y')
        else:
            short = (zone.replace('SL Zone ','').replace('SL ','')
                        .replace('CO Zone ','').replace('CD Zone ',''))
            fig.add_annotation(x=x+w/2, y=y+h/2, text=short,
                               showarrow=False,
                               font=dict(color='rgba(255,255,255,0.4)', size=8, family='Arial'),
                               xref='x', yref='y')

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=13, color='white'), x=0.5),
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(range=[-5, 100], showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor='x', scaleratio=1.5),
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#3a7d2c',
        margin=dict(t=35, b=5, l=5, r=5),
        height=340,
    )
    return fig


def parse_zone_counts(zone_list, zone_defs):
    counts = defaultdict(int)
    for entry in zone_list:
        for part in str(entry).split(','):
            part = part.strip()
            for zone in zone_defs.keys():
                if zone.lower() == part.lower():
                    counts[zone] += 1
    return dict(counts)


# ── RADAR + BAR CHARTS ────────────────────────────────────────────────────────

def make_radar(player, all_players, color='#00C87A', name=None):
    vals = list(all_players.values())
    maxes = {
        'total_passes': max(p['total_passes'] for p in vals) or 1,
        'shots': max(p['shots'] for p in vals) or 1,
        'def_actions': max(p['def_actions'] for p in vals) or 1,
        'interceptions': max(p['interceptions'] for p in vals) or 1,
        'crosses': max(p['crosses'] for p in vals) or 1,
    }
    scores = [
        round(player['total_passes'] / maxes['total_passes'] * 100),
        round(player['shots'] / maxes['shots'] * 100),
        round(player['def_actions'] / maxes['def_actions'] * 100),
        round(player['interceptions'] / maxes['interceptions'] * 100),
        round(player['crosses'] / maxes['crosses'] * 100),
        player['pass_pct'],
    ]
    labels = ['Passes', 'Shots', 'Def Actions', 'Interceptions', 'Crosses', 'Pass %']
    scores_closed = scores + [scores[0]]
    labels_closed = labels + [labels[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores_closed, theta=labels_closed, fill='toself',
        fillcolor=f'rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)',
        line=dict(color=color, width=2),
        marker=dict(size=6, color=color),
        name=name or '',
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=False, range=[0,100]), angularaxis=dict(tickfont=dict(size=12))),
        showlegend=False,
        margin=dict(t=20, b=20, l=40, r=40),
        height=320,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )
    return fig


def make_compare_radar(p1, p2, all_players, name1, name2):
    vals = list(all_players.values())
    maxes = {
        'total_passes': max(p['total_passes'] for p in vals) or 1,
        'shots': max(p['shots'] for p in vals) or 1,
        'def_actions': max(p['def_actions'] for p in vals) or 1,
        'interceptions': max(p['interceptions'] for p in vals) or 1,
        'crosses': max(p['crosses'] for p in vals) or 1,
    }

    def scores(player):
        return [
            round(player['total_passes'] / maxes['total_passes'] * 100),
            round(player['shots'] / maxes['shots'] * 100),
            round(player['def_actions'] / maxes['def_actions'] * 100),
            round(player['interceptions'] / maxes['interceptions'] * 100),
            round(player['crosses'] / maxes['crosses'] * 100),
            player['pass_pct'],
        ]

    labels = ['Passes', 'Shots', 'Def Actions', 'Interceptions', 'Crosses', 'Pass %']
    s1 = scores(p1) + [scores(p1)[0]]
    s2 = scores(p2) + [scores(p2)[0]]
    labels_closed = labels + [labels[0]]

    fig = go.Figure()
    for s, color, name in [(s1, '#00C87A', name1), (s2, '#F5A623', name2)]:
        fig.add_trace(go.Scatterpolar(
            r=s, theta=labels_closed, fill='toself',
            fillcolor=f'rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12)',
            line=dict(color=color, width=2),
            marker=dict(size=5, color=color),
            name=name,
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=False, range=[0,100]), angularaxis=dict(tickfont=dict(size=12))),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, font=dict(size=12)),
        margin=dict(t=20, b=40, l=40, r=40),
        height=360,
        paper_bgcolor='rgba(0,0,0,0)',
    )
    return fig


# ── LOAD DATA ─────────────────────────────────────────────────────────────────
all_games = {}
data_folder = "data"
repo_csvs = sorted(glob.glob(os.path.join(data_folder, "*.csv")))

if repo_csvs:
    for path in repo_csvs:
        game_name = os.path.basename(path).replace('.csv', '')
        try:
            df = pd.read_csv(path)
            all_games[game_name] = aggregate_stats(df)
        except Exception as e:
            st.warning(f"Could not load {game_name}: {e}")

# ── PASSWORD GATE ─────────────────────────────────────────────────────────────
pwd = st.text_input("Enter password", type="password")
if pwd != st.secrets.get("APP_PASSWORD", "footballferns"):
    st.warning("Please enter the password to access this app.")
    st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ Player Profiler")
    st.markdown("---")

    if repo_csvs:
        st.success(f"{len(repo_csvs)} game(s) auto-loaded from repo")
        for path in repo_csvs:
            st.markdown(f"- `{os.path.basename(path)}`")
        st.markdown("---")

    uploaded = st.file_uploader(
        "Upload additional CSVs",
        type="csv",
        accept_multiple_files=True,
    )

    raw_dfs = {}
    if uploaded:
        for f in uploaded:
            game_name = f.name.replace('.csv', '')
            try:
                df = pd.read_csv(f)
                if game_name not in all_games:
                    all_games[game_name] = aggregate_stats(df)
                raw_dfs[game_name] = df
            except Exception as e:
                st.warning(f"Could not load {game_name}: {e}")

    # Load repo CSVs as raw dfs too for match report
    for path in repo_csvs:
        game_name = os.path.basename(path).replace('.csv', '')
        if game_name not in raw_dfs:
            try:
                raw_dfs[game_name] = pd.read_csv(path)
            except:
                pass

    st.markdown("---")
    mode = st.radio("View mode", ["Single Player", "Compare Players", "Squad Table", "Match Report"])

# ── NO DATA ───────────────────────────────────────────────────────────────────
if not all_games:
    st.title("⚽ Player Profiler")
    st.info("No CSV files found. Add CSVs to the `data/` folder or upload via sidebar.")
    st.stop()

players = merge_games(all_games)
player_names = sorted(players.keys())

if not player_names:
    st.error("No player data found. Check your CSV format.")
    st.stop()

game_names = list(all_games.keys())
st.markdown(f"**Games loaded:** {' · '.join([f'`{g}`' for g in game_names])}")
st.markdown("---")


# ── SINGLE PLAYER ─────────────────────────────────────────────────────────────
if mode == "Single Player":
    selected = st.selectbox("Select player", player_names)
    p = players[selected]

    st.markdown(f"### {selected}")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Passes", p['total_passes'], f"{p['pass_pct']}% complete")
    c2.metric("Shots", p['shots'], f"{p['sot']} on target")
    c3.metric("Def Actions", p['def_actions'], f"{p['interceptions']} interceptions")
    c4.metric("Turnovers", p['turnovers'])
    c5.metric("Crosses", p['crosses'], f"{p['crosses_complete']} successful")
    c6.metric("Games", p.get('games', 1))

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Action profile**")
        st.plotly_chart(make_radar(p, players), use_container_width=True)

    with col2:
        st.markdown("**Stats vs squad average**")
        avg_passes = sum(x['total_passes'] for x in players.values()) / len(players)
        avg_shots  = sum(x['shots'] for x in players.values()) / len(players)
        avg_def    = sum(x['def_actions'] for x in players.values()) / len(players)
        avg_int    = sum(x['interceptions'] for x in players.values()) / len(players)
        avg_to     = sum(x['turnovers'] for x in players.values()) / len(players)
        avg_pct    = sum(x['pass_pct'] for x in players.values()) / len(players)

        bar_data = pd.DataFrame({
            'Metric': ['Passes', 'Pass %', 'Shots', 'Def Actions', 'Interceptions', 'Turnovers'],
            'Player': [p['total_passes'], p['pass_pct'], p['shots'], p['def_actions'], p['interceptions'], p['turnovers']],
            'Squad Avg': [round(avg_passes,1), round(avg_pct,1), round(avg_shots,1), round(avg_def,1), round(avg_int,1), round(avg_to,1)]
        })

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name=selected, x=bar_data['Metric'], y=bar_data['Player'], marker_color='#00C87A'))
        fig2.add_trace(go.Bar(name='Squad Avg', x=bar_data['Metric'], y=bar_data['Squad Avg'], marker_color='#d0d0d0'))
        fig2.update_layout(
            barmode='group', height=320,
            margin=dict(t=10,b=10,l=10,r=10),
            legend=dict(orientation='h', yanchor='bottom', y=-0.3),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(gridcolor='rgba(0,0,0,0.05)'),
        )
        st.plotly_chart(fig2, use_container_width=True)


# ── COMPARE ───────────────────────────────────────────────────────────────────
elif mode == "Compare Players":
    col1, col2 = st.columns(2)
    with col1:
        p1_name = st.selectbox("Player 1", player_names, index=0)
    with col2:
        p2_name = st.selectbox("Player 2", player_names, index=min(1, len(player_names)-1))

    p1 = players[p1_name]
    p2 = players[p2_name]

    st.markdown("---")
    c1, c2 = st.columns(2)

    metrics = [
        ('Passes', 'total_passes'), ('Pass %', 'pass_pct'),
        ('Shots', 'shots'), ('On Target', 'sot'),
        ('Def Actions', 'def_actions'), ('Interceptions', 'interceptions'),
        ('Turnovers', 'turnovers'), ('Crosses', 'crosses'),
    ]

    with c1:
        st.markdown(f"#### 🟢 {p1_name}")
        for label, key in metrics:
            delta = p1[key] - p2[key]
            st.metric(label, p1[key], f"+{delta}" if delta > 0 else str(delta))

    with c2:
        st.markdown(f"#### 🟡 {p2_name}")
        for label, key in metrics:
            delta = p2[key] - p1[key]
            st.metric(label, p2[key], f"+{delta}" if delta > 0 else str(delta))

    st.markdown("---")
    st.markdown("**Head to head radar**")
    st.plotly_chart(make_compare_radar(p1, p2, players, p1_name, p2_name), use_container_width=True)


# ── SQUAD TABLE ───────────────────────────────────────────────────────────────
elif mode == "Squad Table":
    st.markdown("### Squad overview")

    rows = []
    for name, p in players.items():
        rows.append({
            'Player': name,
            'Games': p.get('games', 1),
            'Passes': p['total_passes'],
            'Pass %': f"{p['pass_pct']}%",
            'Shots': p['shots'],
            'On Target': p['sot'],
            'Def Actions': p['def_actions'],
            'Interceptions': p['interceptions'],
            'Turnovers': p['turnovers'],
            'Crosses': p['crosses'],
        })

    df_squad = pd.DataFrame(rows).sort_values('Passes', ascending=False).reset_index(drop=True)
    st.dataframe(df_squad, use_container_width=True, height=500)

    st.markdown("---")
    st.markdown("**Top performers**")
    t1, t2, t3, t4 = st.columns(4)
    top_passes = max(players.items(), key=lambda x: x[1]['total_passes'])
    top_shots  = max(players.items(), key=lambda x: x[1]['shots'])
    top_def    = max(players.items(), key=lambda x: x[1]['def_actions'])
    top_pct    = max(players.items(), key=lambda x: x[1]['pass_pct'])
    t1.metric("Most passes", top_passes[0], f"{top_passes[1]['total_passes']} passes")
    t2.metric("Most shots", top_shots[0], f"{top_shots[1]['shots']} shots")
    t3.metric("Most def actions", top_def[0], f"{top_def[1]['def_actions']} actions")
    t4.metric("Best pass %", top_pct[0], f"{top_pct[1]['pass_pct']}%")


# ── MATCH REPORT ──────────────────────────────────────────────────────────────
elif mode == "Match Report":

    col1, col2 = st.columns(2)
    with col1:
        selected_player = st.selectbox("Select player", player_names)
    with col2:
        game_options = list(raw_dfs.keys())
        if not game_options:
            st.warning("No raw game data available for match report.")
            st.stop()
        selected_game = st.selectbox("Select game", game_options)

    df_game = raw_dfs[selected_game]
    r = parse_match_report(df_game, selected_player)

    if r is None:
        st.warning(f"No data found for {selected_player} in {selected_game}")
        st.stop()

    st.markdown(f"### {selected_player} — {selected_game}")
    st.markdown("---")

    # ── SHOOTING ──────────────────────────────────────────────────────────────
    st.markdown("#### Shooting")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Goals", r['goals'])
    c2.metric("Shots", r['total_shots'])
    c3.metric("On Target", r['sot'])
    c4.metric("Shot Assist", r['shot_assist'])

    st.markdown("**Shot breakdown**")
    off_target = r['total_shots'] - r['sot']
    fig_shoot = go.Figure(go.Bar(
        x=['Shots', 'On Target', 'Off Target', 'Assists'],
        y=[r['total_shots'], r['sot'], off_target, r['shot_assist']],
        marker_color=['#4d9fff', '#00C87A', '#ff5252', '#ffb74d'],
        text=[r['total_shots'], r['sot'], off_target, r['shot_assist']],
        textposition='auto',
    ))
    fig_shoot.update_layout(
        height=240, margin=dict(t=10,b=10,l=10,r=10),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showticklabels=False),
        showlegend=False,
    )
    st.plotly_chart(fig_shoot, use_container_width=True)

    st.markdown("---")

    # ── PASSING ───────────────────────────────────────────────────────────────
    st.markdown("#### Passing")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total passes", r['total_passes'])
    c2.metric("Complete", r['passes_complete'])
    c3.metric("Incomplete", r['passes_incomplete'])
    c4.metric("Pass %", f"{r['pass_pct']}%")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Pass types**")
        types = ['Through', 'Around', 'Backwards', 'Neutral', 'Over']
        totals = [r['through_total'], r['around_total'], r['backwards_total'], r['neutral_total'], r['over_total']]
        pcts   = [r['through_pct'], r['around_pct'], r['backwards_pct'], r['neutral_pct'], r['over_pct']]

        fig_pt = go.Figure()
        fig_pt.add_trace(go.Bar(
            name='Total', x=types, y=totals,
            marker_color='#4d9fff',
            text=totals, textposition='auto',
        ))
        fig_pt.update_layout(
            height=240, margin=dict(t=10,b=10,l=10,r=10),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showticklabels=False),
            showlegend=False,
        )
        st.plotly_chart(fig_pt, use_container_width=True)

        # Completion % per type
        comp_data = pd.DataFrame({
            'Type': [t for t, tot in zip(types, totals) if tot > 0],
            'Completion %': [p for t, p in zip(totals, pcts) if t > 0],
        })
        if not comp_data.empty:
            fig_cp = go.Figure(go.Bar(
                x=comp_data['Type'], y=comp_data['Completion %'],
                marker_color=['#00C87A' if v >= 80 else '#ffb74d' if v >= 60 else '#ff5252' for v in comp_data['Completion %']],
                text=[f"{v}%" for v in comp_data['Completion %']],
                textposition='auto',
            ))
            fig_cp.update_layout(
                height=180, margin=dict(t=10,b=10,l=10,r=10),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[0,100], gridcolor='rgba(0,0,0,0.05)', showticklabels=False),
                showlegend=False,
                title=dict(text='Completion % by type', font=dict(size=12), x=0),
            )
            st.plotly_chart(fig_cp, use_container_width=True)

    with col2:
        st.markdown("**Receives**")
        recv_labels = ['Seam 1', 'Seam 2', 'Seam 3', 'Neutral', 'Below']
        recv_vals   = [r['recv_seam1'], r['recv_seam2'], r['recv_seam3'], r['recv_neutral'], r['recv_below']]
        fig_recv = go.Figure(go.Bar(
            x=recv_labels, y=recv_vals,
            marker_color=['#00C87A','#00C87A','#00C87A','#4d9fff','#ffb74d'],
            text=recv_vals, textposition='auto',
        ))
        fig_recv.update_layout(
            height=240, margin=dict(t=10,b=10,l=10,r=10),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showticklabels=False),
            showlegend=False,
        )
        st.plotly_chart(fig_recv, use_container_width=True)

        st.markdown("**Key passes**")
        kc1, kc2 = st.columns(2)
        kc1.metric("Passes into F3", r['passes_f3'], f"{r['f3_pct']}% complete")
        kc2.metric("Passes into box", r['passes_box'], f"{r['box_pct']}% complete")

    st.markdown("---")

    # ── DEFENDING ─────────────────────────────────────────────────────────────
    st.markdown("#### Defending")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Interceptions", r['interceptions'])
    c2.metric("Ground duels W", r['ground_duel_w'])
    c3.metric("Ground duels L", r['ground_duel_l'])
    c4.metric("Turnovers", r['turnovers'])

    st.markdown("---")

    # ── CROSSING ──────────────────────────────────────────────────────────────
    st.markdown("#### Crossing")

    if r['cross_total'] > 0:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total crosses", r['cross_total'])
        c2.metric("Teammate found", r['cross_found'])
        c3.metric("Not found", r['cross_not_found'])
        c4.metric("Success %", f"{round(r['cross_found']/r['cross_total']*100) if r['cross_total'] else 0}%")

        st.markdown("**Cross types**")
        col1, col2 = st.columns(2)
        with col1:
            ct_labels = ['Whipped', 'Floated', 'Cut Back', 'Hung Up']
            ct_vals   = [r['cross_whipped'], r['cross_floated'], r['cross_cutback'], r['cross_hungup']]
            fig_ct = go.Figure(go.Bar(
                x=ct_labels, y=ct_vals,
                marker_color='#4d9fff',
                text=ct_vals, textposition='auto',
            ))
            fig_ct.update_layout(
                height=220, margin=dict(t=10,b=10,l=10,r=10),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showticklabels=False),
                showlegend=False,
            )
            st.plotly_chart(fig_ct, use_container_width=True)
        with col2:
            st.markdown("**Cross origins**")
            origin_counts = {}
            for entry in r['cross_origins']:
                for part in str(entry).split(','):
                    part = part.strip()
                    if part:
                        origin_counts[part] = origin_counts.get(part, 0) + 1
            if origin_counts:
                fig_co = go.Figure(go.Bar(
                    x=list(origin_counts.keys()), y=list(origin_counts.values()),
                    marker_color='#00C87A',
                    text=list(origin_counts.values()), textposition='auto',
                ))
                fig_co.update_layout(
                    height=220, margin=dict(t=10,b=10,l=10,r=10),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(gridcolor='rgba(0,0,0,0.05)', showticklabels=False),
                    xaxis=dict(tickfont=dict(size=10)),
                    showlegend=False,
                )
                st.plotly_chart(fig_co, use_container_width=True)
    else:
        st.info("No crossing data for this player in this game")
