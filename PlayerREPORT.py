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


# ── Auto-load CSVs from data/ folder ─────────────────────────────────────────
all_games = {}
data_folder = "data"
repo_csvs = sorted(glob.glob(os.path.join(data_folder, "*.csv")))

if repo_csvs:
    for path in repo_csvs:
        game_name = os.path.basename(path).replace('.csv', '')
        df = pd.read_csv(path)
        all_games[game_name] = aggregate_stats(df)

# ── Sidebar ───────────────────────────────────────────────────────────────────
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
        help="Add extra match CSVs on top of the repo data"
    )

    if uploaded:
        for f in uploaded:
            game_name = f.name.replace('.csv', '')
            if game_name not in all_games:
                all_games[game_name] = aggregate_stats(parse_csv(f))

    st.markdown("---")
    mode = st.radio("View mode", ["Single Player", "Compare Players", "Squad Table"])

# ── No data at all ────────────────────────────────────────────────────────────
if not all_games:
    st.title("⚽ Player Profiler")
    st.info("No CSV files found in the `data/` folder and none uploaded. Add CSVs to the `data/` folder in the GitHub repo or upload them via the sidebar.")
    st.stop()

# ── Merge all games ───────────────────────────────────────────────────────────
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
        fig = make_radar(p, players)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Stats vs squad average**")
        avg_passes = sum(x['total_passes'] for x in players.values()) / len(players)
        avg_shots = sum(x['shots'] for x in players.values()) / len(players)
        avg_def = sum(x['def_actions'] for x in players.values()) / len(players)
        avg_int = sum(x['interceptions'] for x in players.values()) / len(players)
        avg_to = sum(x['turnovers'] for x in players.values()) / len(players)
        avg_pct = sum(x['pass_pct'] for x in players.values()) / len(players)

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
    fig = make_compare_radar(p1, p2, players, p1_name, p2_name)
    st.plotly_chart(fig, use_container_width=True)

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
    top_shots = max(players.items(), key=lambda x: x[1]['shots'])
    top_def = max(players.items(), key=lambda x: x[1]['def_actions'])
    top_pct = max(players.items(), key=lambda x: x[1]['pass_pct'])
    t1.metric("Most passes", top_passes[0], f"{top_passes[1]['total_passes']} passes")
    t2.metric("Most shots", top_shots[0], f"{top_shots[1]['shots']} shots")
    t3.metric("Most def actions", top_def[0], f"{top_def[1]['def_actions']} actions")
    t4.metric("Best pass %", top_pct[0], f"{top_pct[1]['pass_pct']}%")
