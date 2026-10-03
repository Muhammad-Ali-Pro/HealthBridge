"""HealthBridge design tokens and global CSS.

Colours are derived from the logo: deep navy wordmark, teal/green leaves,
coral/orange accents (reserved for warnings), on soft mint surfaces.
"""

import streamlit as st

TOKENS = {
    "navy": "#0F2A43",
    "navy-600": "#1F3B5C",
    "muted": "#5E7186",
    "subtle": "#94A3B3",
    "teal": "#12917F",
    "teal-600": "#0E7A6B",
    "teal-50": "#E8F6F3",
    "teal-100": "#CDEEE6",
    "mint": "#F4F8F7",
    "surface": "#FFFFFF",
    "border": "#E2EAE7",
    "border-strong": "#CBD9D5",
    "coral": "#E5604D",
    "coral-50": "#FDEEEB",
    "amber": "#C97A1E",
    "amber-50": "#FDF4E7",
    "blue": "#2F6BC7",
    "blue-50": "#EAF1FC",
    "violet": "#6A55C9",
    "violet-50": "#F1EEFC",
}

_ROOT = ";".join(f"--hb-{k}:{v}" for k, v in TOKENS.items())

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,300..600,0..1,0&display=block');

:root { ROOT_TOKENS;
  --hb-radius: 14px; --hb-radius-sm: 10px;
  --hb-shadow: 0 1px 2px rgba(15,42,67,.04), 0 1px 3px rgba(15,42,67,.05);
  --hb-shadow-lg: 0 8px 24px rgba(15,42,67,.08);
}

html, body, .stApp, [class*="css"] { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
.stApp { background: var(--hb-mint); color: var(--hb-navy); }

/* ---------- Chrome cleanup ---------- */
[data-testid="stDecoration"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu { display: none !important; }
header[data-testid="stHeader"] { background: transparent; height: 2.5rem; }
[data-testid="stMainBlockContainer"], .block-container { padding: 1.25rem 2.25rem 3rem; max-width: 1400px; }
h1, h2, h3, h4 { color: var(--hb-navy); letter-spacing: -0.015em; }
/* Our HTML blocks own their spacing; cancel Streamlit's markdown negative margin. */
[data-testid="stMarkdownContainer"]:has(> .hb-html) { margin-bottom: 0 !important; }

/* ---------- Icons ---------- */
.hb-icon { font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1;
  letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; direction: ltr;
  -webkit-font-smoothing: antialiased; font-feature-settings: 'liga'; font-variation-settings: 'FILL' 0, 'wght' 450;
  vertical-align: middle; font-size: 20px; }
.hb-icon.fill { font-variation-settings: 'FILL' 1, 'wght' 500; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] { background: var(--hb-surface); border-right: 1px solid var(--hb-border); }
section[data-testid="stSidebar"] > div { padding-top: 0; }
[data-testid="stSidebarHeader"] { height: 2.25rem; padding: .5rem 1rem 0; }
[data-testid="stSidebarUserContent"] { padding: 0 .9rem 1rem; }
.st-key-hb_sidebar { min-height: calc(100vh - 3.5rem); gap: 2px !important; }
.st-key-hb_sidebar > :has(.st-key-hb_sidebar_profile) { margin-top: auto; padding-top: 1.25rem; }
.hb-demo { display: flex; align-items: center; justify-content: center; gap: .35rem; margin-top: .6rem; padding: .35rem .6rem;
  border-radius: 999px; background: var(--hb-amber-50); color: var(--hb-amber); font-size: .68rem; font-weight: 700;
  letter-spacing: .01em; text-align: center; line-height: 1.3; }
.hb-demo .hb-icon { font-size: 14px; }
.hb-brand { display: flex; align-items: center; gap: .6rem; padding: .1rem .35rem .5rem; }
.hb-brand img { width: 44px; height: 44px; }
.st-key-hb_back_home { margin-bottom: .6rem; }
.st-key-hb_back_home button { justify-content: flex-start; width: 100%; padding: .4rem .65rem !important; border-radius: 10px;
  background: var(--hb-mint) !important; border: 1px solid var(--hb-border) !important; }
.st-key-hb_back_home button:hover { border-color: var(--hb-teal) !important; }
.st-key-hb_back_home button p { font-size: .84rem; font-weight: 600; color: var(--hb-navy-600); }
.st-key-hb_topbar [data-testid="stBaseButton-tertiary"] p { font-weight: 600; color: var(--hb-navy-600); }
.hb-brand .wordmark { font-weight: 800; font-size: 1.22rem; letter-spacing: -0.02em; color: var(--hb-navy); }
.hb-brand .wordmark span { color: var(--hb-teal); }
.hb-brand-tag { font-size: .66rem; color: var(--hb-subtle); font-weight: 600; letter-spacing: .01em; margin-top: -.1rem; }
.hb-nav-label { font-size: .68rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: var(--hb-subtle); padding: .9rem .6rem .35rem; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
.hb-nav-active { display: flex; align-items: center; gap: .65rem; border-radius: var(--hb-radius-sm);
  padding: .5rem .65rem !important; margin: 1px 0; color: var(--hb-navy-600) !important; font-weight: 500;
  font-size: .9rem; text-decoration: none; background: transparent; transition: background .12s ease; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover { background: var(--hb-mint); }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a p { font-size: .9rem; font-weight: 500; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a span[data-testid="stIconMaterial"] { color: var(--hb-subtle); font-size: 20px; }
.hb-nav-active { background: var(--hb-teal-50); color: var(--hb-teal-600) !important; font-weight: 600; }
.hb-nav-active .hb-icon { color: var(--hb-teal); }

.hb-profile { display: flex; align-items: center; gap: .7rem; padding: .75rem; border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius); background: var(--hb-mint); }
.hb-profile .who { line-height: 1.25; min-width: 0; }
.hb-profile .name { font-weight: 600; font-size: .88rem; color: var(--hb-navy); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hb-profile .meta { font-size: .75rem; color: var(--hb-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ---------- Avatar ---------- */
.hb-avatar { flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 999px;
  font-weight: 700; color: #fff; background: linear-gradient(135deg, var(--hb-teal), var(--hb-navy-600)); }

/* ---------- Top header ---------- */
.st-key-hb_topbar { border-bottom: 1px solid var(--hb-border); padding-bottom: .85rem; margin-bottom: .5rem; }
.hb-crumbs { display: flex; align-items: center; gap: .4rem; font-size: .82rem; color: var(--hb-muted); min-height: 2.4rem; }
.hb-crumbs .sep { color: var(--hb-border-strong); }
.hb-crumbs { overflow: hidden; }
.hb-crumbs .current { color: var(--hb-navy); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.st-key-hb_topbar [data-testid="stPopover"] button { border-radius: 999px; border: 1px solid var(--hb-border);
  background: var(--hb-surface); box-shadow: var(--hb-shadow); padding: .3rem .9rem; font-weight: 600; color: var(--hb-navy); }
.st-key-hb_topbar [data-testid="stTextInput"] input { border-radius: 999px; padding-left: 1rem; background: var(--hb-surface); }
.hb-topbar-right { display: flex; align-items: center; justify-content: flex-end; gap: .5rem; min-height: 2.4rem; flex-wrap: wrap; }

/* ---------- Page header ---------- */
.hb-page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; margin: .75rem 0 1.25rem; }
.hb-eyebrow { font-size: .75rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--hb-teal); margin-bottom: .3rem; }
.hb-page-title { font-size: 1.75rem !important; font-weight: 800 !important; letter-spacing: -0.025em; color: var(--hb-navy);
  line-height: 1.15 !important; margin: 0 !important; padding: 0 !important; }
.hb-page-sub { color: var(--hb-muted); font-size: .95rem; margin-top: .35rem; }

/* ---------- Section ---------- */
.hb-section { display: flex; align-items: center; justify-content: space-between; margin: .25rem 0 .7rem; }
.hb-section h3 { font-size: 1rem; font-weight: 700; margin: 0; padding: 0; color: var(--hb-navy); letter-spacing: -0.01em; }
.hb-section .hint { font-size: .8rem; color: var(--hb-muted); }

/* ---------- Cards ---------- */
.hb-card { background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: var(--hb-radius);
  box-shadow: var(--hb-shadow); padding: 1.15rem 1.25rem; }
div[class*="st-key-hbcard"] { background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: var(--hb-radius);
  box-shadow: var(--hb-shadow); padding: 1.15rem 1.25rem; }
div[class*="st-key-hbcard"].hb-selected, div[class*="st-key-hbcard_sel"] { border-color: var(--hb-teal); box-shadow: 0 0 0 3px var(--hb-teal-50); }

/* KPI */
.hb-kpi { background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: var(--hb-radius);
  box-shadow: var(--hb-shadow); padding: 1.1rem 1.2rem; height: 100%; }
.hb-kpi .top { display: flex; align-items: center; justify-content: space-between; }
.hb-kpi .label { font-size: .82rem; font-weight: 600; color: var(--hb-muted); }
.hb-kpi .tile { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
.hb-kpi .value { font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; color: var(--hb-navy); margin-top: .5rem; line-height: 1.1; }
.hb-kpi .foot { font-size: .78rem; color: var(--hb-muted); margin-top: .35rem; }
.tone-teal { background: var(--hb-teal-50); color: var(--hb-teal-600); }
.tone-navy { background: #EBF0F6; color: var(--hb-navy-600); }
.tone-blue { background: var(--hb-blue-50); color: var(--hb-blue); }
.tone-amber { background: var(--hb-amber-50); color: var(--hb-amber); }
.tone-coral { background: var(--hb-coral-50); color: var(--hb-coral); }
.tone-violet { background: var(--hb-violet-50); color: var(--hb-violet); }
.tone-neutral { background: #EFF3F5; color: var(--hb-muted); }

/* Badges & chips */
.hb-badge { display: inline-flex; align-items: center; gap: .3rem; padding: .18rem .6rem; border-radius: 999px;
  font-size: .72rem; font-weight: 600; white-space: nowrap; line-height: 1.4; }
.hb-badge .hb-icon { font-size: 14px; }
.hb-badge.outline { background: var(--hb-surface); border: 1px solid var(--hb-border); color: var(--hb-muted); }
.hb-chip { display: inline-flex; align-items: center; gap: .3rem; padding: .22rem .65rem; border-radius: 8px;
  font-size: .78rem; font-weight: 500; margin: 0 .3rem .3rem 0; }
.hb-dot { width: 7px; height: 7px; border-radius: 999px; display: inline-block; background: currentColor; }

/* Patient summary */
.hb-patient { display: flex; gap: .9rem; align-items: flex-start; }
.hb-patient .body { min-width: 0; flex: 1; }
.hb-patient .name { font-weight: 700; color: var(--hb-navy); font-size: 1rem; }
.hb-patient .meta { color: var(--hb-muted); font-size: .8rem; margin: .1rem 0 .55rem; }
.hb-kv { display: grid; grid-template-columns: 110px 1fr; gap: .35rem .75rem; font-size: .84rem; }
.hb-kv .k { color: var(--hb-muted); }
.hb-kv .v { color: var(--hb-navy); font-weight: 500; }

/* Profile hero */
.hb-hero { display: flex; gap: 1.25rem; align-items: center; flex-wrap: wrap; }
.hb-hero .name { font-size: 1.45rem; font-weight: 800; letter-spacing: -0.02em; color: var(--hb-navy); }
.hb-hero .meta { color: var(--hb-muted); font-size: .9rem; display: flex; gap: .9rem; flex-wrap: wrap; margin-top: .2rem; }
.hb-hero .meta span { display: inline-flex; align-items: center; gap: .25rem; }
.hb-hero-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin-top: 1.1rem;
  padding-top: 1rem; border-top: 1px solid var(--hb-border); }
.hb-hero-grid .lbl { font-size: .72rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--hb-subtle); margin-bottom: .4rem; }
@media (max-width: 900px) { .hb-hero-grid { grid-template-columns: 1fr; } }

/* Prescription card */
.hb-rx .head { display: flex; justify-content: space-between; align-items: flex-start; gap: .75rem; }
.hb-rx .title { font-weight: 700; color: var(--hb-navy); }
.hb-rx .sub { font-size: .8rem; color: var(--hb-muted); margin-top: .1rem; }
.hb-rx .drug { display: flex; gap: .7rem; align-items: center; padding: .6rem .75rem; margin-top: .7rem;
  background: var(--hb-mint); border-radius: var(--hb-radius-sm); }
.hb-rx .drug .n { font-weight: 600; color: var(--hb-navy); font-size: .9rem; }
.hb-rx .drug .d { font-size: .78rem; color: var(--hb-muted); }
.hb-rx .foot { display: flex; justify-content: space-between; gap: .5rem; margin-top: .7rem; font-size: .76rem; color: var(--hb-muted); flex-wrap: wrap; }

/* Timeline */
.hb-timeline { position: relative; margin: .25rem 0 0; padding: 0; }
.hb-tl-item { position: relative; display: grid; grid-template-columns: 40px 1fr; gap: .9rem; padding-bottom: 1.1rem; }
.hb-tl-item:not(:last-child)::before { content: ""; position: absolute; left: 19px; top: 40px; bottom: 0; width: 2px; background: var(--hb-border); }
.hb-tl-dot { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; }
.hb-tl-body { background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: 12px; padding: .7rem .9rem; }
.hb-tl-top { display: flex; justify-content: space-between; gap: .75rem; align-items: center; flex-wrap: wrap; }
.hb-tl-title { font-weight: 600; color: var(--hb-navy); font-size: .9rem; }
.hb-tl-when { font-size: .75rem; color: var(--hb-muted); white-space: nowrap; }
.hb-tl-text { font-size: .85rem; color: var(--hb-navy-600); margin-top: .2rem; }
.hb-tl-meta { font-size: .75rem; color: var(--hb-muted); margin-top: .35rem; display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
.hb-tl-day { font-size: .72rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--hb-subtle); margin: .2rem 0 .6rem 56px; }

/* Alert */
.hb-alert { display: flex; gap: .8rem; align-items: flex-start; padding: .85rem 1rem; border-radius: 12px; border: 1px solid transparent; }
.hb-alert .t { font-weight: 600; font-size: .9rem; }
.hb-alert .b { font-size: .84rem; margin-top: .15rem; opacity: .9; }
.hb-alert.warning { background: var(--hb-amber-50); border-color: #F5DDB8; color: #7A4A12; }
.hb-alert.danger { background: var(--hb-coral-50); border-color: #F7C9C1; color: #8A2E20; }
.hb-alert.info { background: var(--hb-blue-50); border-color: #CFDDF5; color: #1E4B8F; }
.hb-alert.success { background: var(--hb-teal-50); border-color: var(--hb-teal-100); color: var(--hb-teal-600); }
.hb-alert.ai { background: var(--hb-violet-50); border: 1px dashed #C9C0F0; color: #44378F; }

/* Empty state */
.hb-empty { text-align: center; padding: 2rem 1rem; color: var(--hb-muted); }
.hb-empty .tile { width: 52px; height: 52px; margin: 0 auto .8rem; border-radius: 14px; display: flex; align-items: center; justify-content: center; }
.hb-empty .t { font-weight: 700; color: var(--hb-navy); font-size: .95rem; }
.hb-empty .b { font-size: .85rem; margin-top: .25rem; max-width: 420px; margin-left: auto; margin-right: auto; }

/* Table */
.hb-table-wrap { background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: var(--hb-radius);
  box-shadow: var(--hb-shadow); overflow-x: auto; }
table.hb-table { width: 100%; border-collapse: collapse; font-size: .86rem; }
table.hb-table th { text-align: left; font-size: .72rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  color: var(--hb-subtle); background: #FAFCFB; padding: .7rem 1rem; border-bottom: 1px solid var(--hb-border); }
table.hb-table td { padding: .75rem 1rem; border-bottom: 1px solid var(--hb-border); color: var(--hb-navy); vertical-align: middle; }
table.hb-table tr:last-child td { border-bottom: none; }
table.hb-table tr:hover td { background: #FAFCFB; }
table.hb-table .strong { font-weight: 600; }
table.hb-table .muted { color: var(--hb-muted); font-size: .8rem; }

/* AI vs verified provenance */
.hb-ai-card { border: 1px dashed #C9C0F0 !important; background: linear-gradient(180deg, #FBFAFF, #FFFFFF) !important; }
.hb-legend { display: flex; gap: 1.25rem; flex-wrap: wrap; font-size: .82rem; color: var(--hb-muted); }

/* Quick actions (page links rendered as tiles) */
div[class*="st-key-hb_qa"] [data-testid="stPageLink"] a { background: var(--hb-surface); border: 1px solid var(--hb-border);
  border-radius: var(--hb-radius); box-shadow: var(--hb-shadow); padding: .85rem 1rem; transition: all .12s ease; width: 100%; }
div[class*="st-key-hb_qa"] [data-testid="stPageLink"] a:hover { border-color: var(--hb-teal); box-shadow: var(--hb-shadow-lg); background: var(--hb-surface); }
div[class*="st-key-hb_qa"] [data-testid="stPageLink"] a p { font-weight: 600; color: var(--hb-navy); }
div[class*="st-key-hb_qa"] [data-testid="stPageLink"] a span[data-testid="stIconMaterial"] { color: var(--hb-teal); }

/* Native widgets */
.stButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] { border-radius: 10px; font-weight: 600; }
[data-testid="stBaseButton-primary"] { box-shadow: 0 1px 2px rgba(18,145,127,.25); }
[data-testid="stTextInput"] input, [data-testid="stSelectbox"] > div > div { border-radius: 10px; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--hb-border); }
[data-testid="stTabs"] button[role="tab"] { padding: .55rem .9rem; }
[data-testid="stTabs"] button[role="tab"] p { font-weight: 600; font-size: .88rem; }
[data-testid="stPopoverBody"] { border-radius: var(--hb-radius); border: 1px solid var(--hb-border); box-shadow: var(--hb-shadow-lg); }

/* Tiles, organization badges, plain-language notes */
.hb-tile { flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 10px; }
.hb-org { display: inline-flex; align-items: center; gap: .3rem; padding: .16rem .55rem; border-radius: 7px;
  font-size: .74rem; font-weight: 600; white-space: nowrap; }
.hb-plain { display: flex; gap: .45rem; align-items: flex-start; margin-top: .7rem; padding: .55rem .7rem; border-radius: 10px;
  background: var(--hb-blue-50); color: #1E4B8F; font-size: .82rem; line-height: 1.4; }

/* Access status (doctor view of a patient) */
.hb-access { display: flex; gap: .7rem; align-items: flex-start; padding: .75rem .9rem; border-radius: 12px; }
.hb-access .t { font-weight: 700; font-size: .88rem; }
.hb-access .s { font-size: .8rem; margin-top: .3rem; }
.hb-access.ok { background: var(--hb-teal-50); color: var(--hb-teal-600); border: 1px solid var(--hb-teal-100); }
.hb-access.locked { background: #F1F4F6; color: var(--hb-muted); border: 1px solid var(--hb-border); }
.hb-access.locked .t { color: var(--hb-navy); }
.hb-alert.lock { background: #F1F4F6; border-color: var(--hb-border); color: var(--hb-navy-600); }

/* Care network diagram */
.hb-net { background: linear-gradient(180deg, #FFFFFF, #F1F9F7); border: 1px solid var(--hb-border); border-radius: var(--hb-radius);
  box-shadow: var(--hb-shadow); padding: 1.4rem 1.25rem 1.25rem; text-align: center; }
.hb-net-center { display: inline-flex; align-items: center; gap: .85rem; text-align: left; padding: .7rem 1.1rem .7rem .75rem;
  border-radius: 999px; background: var(--hb-surface); border: 1px solid var(--hb-teal-100); box-shadow: 0 0 0 6px var(--hb-teal-50); }
.hb-net-title { font-weight: 800; font-size: 1.05rem; color: var(--hb-navy); }
.hb-net-sub { font-size: .78rem; color: var(--hb-teal-600); font-weight: 600; display: flex; align-items: center; gap: .25rem; }
.hb-net-rail { height: 26px; width: 2px; margin: 0 auto; background: var(--hb-teal-100); }
.hb-net-nodes { display: flex; flex-wrap: wrap; justify-content: center; gap: .7rem; padding-top: .9rem;
  border-top: 2px solid var(--hb-teal-100); }
.hb-net-node { position: relative; display: flex; flex-direction: column; align-items: center; gap: .35rem; width: 150px;
  padding: .8rem .6rem; background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: 12px; }
.hb-net-node::before { content: ""; position: absolute; top: calc(-.9rem - 2px); left: 50%; width: 2px; height: .9rem; background: var(--hb-teal-100); }
.hb-net-node .nm { font-weight: 700; font-size: .82rem; color: var(--hb-navy); line-height: 1.25; }
.hb-net-node .sb { font-size: .72rem; color: var(--hb-muted); }

/* Concept banner */
.hb-concept { display: flex; align-items: center; gap: .9rem; padding: .9rem 1.1rem; border-radius: var(--hb-radius);
  background: linear-gradient(90deg, var(--hb-navy), #17476A); color: #fff; }
.hb-concept .t { font-weight: 700; font-size: .95rem; }
.hb-concept .s { font-size: .82rem; opacity: .8; margin-top: .1rem; }
.hb-concept .hb-tile { background: rgba(255,255,255,.12); color: #fff; }

/* Forms */
.hb-field-error { color: #B23B2A; font-size: .8rem; font-weight: 600; margin: -.35rem 0 .4rem; display: flex; gap: .3rem; align-items: center; }
.hb-form-section { font-size: .72rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; color: var(--hb-teal-600);
  margin: .2rem 0 .2rem; display: flex; gap: .4rem; align-items: center; }
div[class*="st-key-hbcard"] [data-testid="stTextArea"] textarea, div[class*="st-key-hbcard"] [data-testid="stTextInput"] input {
  background: #FBFDFC; }
div[class*="st-key-hbform"] { background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: var(--hb-radius);
  box-shadow: var(--hb-shadow); padding: 1.1rem 1.25rem; }
[data-testid="stForm"] { border: none !important; padding: 0 !important; }
.hb-ai-out { border: 1px dashed #C9C0F0; background: linear-gradient(180deg, #FBFAFF, #FFFFFF); border-radius: var(--hb-radius);
  padding: 1.1rem 1.25rem; }
.hb-ai-h { display: flex; justify-content: space-between; align-items: center; gap: .5rem; margin-bottom: .6rem; flex-wrap: wrap; }
.hb-ai-h h4 { margin: 0; font-size: .95rem; font-weight: 700; color: var(--hb-navy); padding: 0; }
.hb-ai-item { padding: .45rem 0; border-bottom: 1px solid #EEEAFB; font-size: .86rem; color: var(--hb-navy); }
.hb-ai-item:last-child { border-bottom: none; }
.hb-cite { display: inline-flex; align-items: center; padding: .05rem .45rem; margin: .15rem .25rem 0 0; border-radius: 6px;
  background: var(--hb-violet-50); color: var(--hb-violet); font-size: .7rem; font-weight: 700; }

/* Provenance */
.hb-src-lbl { font-size: .66rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--hb-subtle); }
.hb-src-person { display: inline-flex; align-items: center; gap: .2rem; font-size: .76rem; color: var(--hb-muted); }

/* Prescription progress stepper */
.hb-steps { display: flex; gap: 0; margin-top: .75rem; }
.hb-step { flex: 1; display: flex; flex-direction: column; align-items: center; gap: .25rem; position: relative; text-align: center; }
.hb-step:not(:last-child)::after { content: ""; position: absolute; top: 11px; left: calc(50% + 12px); right: calc(-50% + 12px);
  height: 2px; background: var(--hb-border); }
.hb-step.done:not(:last-child)::after { background: var(--hb-teal-100); }
.hb-step .dot { width: 22px; height: 22px; border-radius: 999px; display: flex; align-items: center; justify-content: center;
  background: #EFF3F5; color: var(--hb-subtle); }
.hb-step.done .dot { background: var(--hb-teal); color: #fff; }
.hb-step .lbl { font-size: .66rem; font-weight: 600; color: var(--hb-subtle); line-height: 1.2; }
.hb-step.done .lbl { color: var(--hb-teal-600); }

/* Organization / provider cards */
.hb-entity { display: flex; gap: .8rem; align-items: center; }
.hb-entity .nm { font-weight: 700; font-size: .95rem; color: var(--hb-navy); }
.hb-entity .sb { font-size: .78rem; color: var(--hb-muted); }

/* ---------- Landing page ---------- */
.hb-landing-nav { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap;
  padding: .6rem 1rem .6rem .8rem; margin-bottom: .5rem; background: rgba(255,255,255,.75); border: 1px solid var(--hb-border);
  border-radius: 18px; box-shadow: var(--hb-shadow); backdrop-filter: blur(6px); }
.hb-landing-nav .brand { display: flex; align-items: center; gap: .7rem; }
.hb-landing-nav .brand img { width: 56px; height: 56px; }
.hb-landing-nav .brand .wordmark { font-weight: 800; font-size: 1.7rem; letter-spacing: -0.025em; color: var(--hb-navy); }
.hb-landing-nav .brand .wordmark span { color: var(--hb-teal); }
.hb-landing-nav .links { display: flex; align-items: center; gap: 1.4rem; flex-wrap: wrap; }
.hb-landing-nav .links a { color: var(--hb-navy-600) !important; text-decoration: none; font-weight: 600; font-size: .92rem; }
.hb-landing-nav .links a:hover { color: var(--hb-teal) !important; }
.hb-hero-l { padding: 2rem 0 1rem; }
.hb-hero-brand { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.3rem; }
.hb-hero-brand img { width: 96px; height: 96px; filter: drop-shadow(0 8px 18px rgba(18,145,127,.18)); }
.hb-hero-brand .wm { font-size: 2.3rem; font-weight: 800; letter-spacing: -0.03em; color: var(--hb-navy); line-height: 1; }
.hb-hero-brand .wm span { color: var(--hb-teal); }
.hb-hero-brand .tag { font-size: .82rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: var(--hb-teal-600); margin-top: .45rem; }
.hb-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .9rem; margin-top: 1.6rem; }
.hb-stats .s { display: flex; gap: .75rem; align-items: center; background: rgba(255,255,255,.85); border: 1px solid var(--hb-border);
  border-radius: 16px; padding: .9rem 1rem; box-shadow: var(--hb-shadow); }
.hb-stats .v { font-weight: 800; color: var(--hb-navy); font-size: 1rem; }
.hb-stats .l { font-size: .76rem; color: var(--hb-muted); }
@media (max-width: 900px) { .hb-stats { grid-template-columns: 1fr 1fr; } }
.hb-hero-kicker { font-size: .8rem; font-weight: 800; letter-spacing: .22em; color: var(--hb-teal); text-transform: uppercase; }
.hb-hero-title { font-size: 3.1rem; line-height: 1.06; font-weight: 800; letter-spacing: -0.035em; color: var(--hb-navy); margin: .7rem 0 1rem; }
.hb-hero-title span { color: var(--hb-teal); }
.hb-hero-sub { font-size: 1.15rem; color: var(--hb-muted); max-width: 560px; line-height: 1.55; }
.hb-hero-pills { display: flex; gap: .5rem; flex-wrap: wrap; margin-top: 1.4rem; }
.hb-hero-visual { background: linear-gradient(160deg, #FFFFFF 0%, #EAF7F3 100%); border: 1px solid var(--hb-border);
  border-radius: 22px; box-shadow: var(--hb-shadow-lg); padding: 1.6rem; margin-top: 1.6rem; }
.hb-orbit { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin-top: 1rem; }
.hb-orbit .n { display: flex; gap: .6rem; align-items: center; background: #fff; border: 1px solid var(--hb-border);
  border-radius: 12px; padding: .65rem .75rem; font-size: .82rem; font-weight: 600; color: var(--hb-navy); }
.hb-orbit .n small { display: block; font-weight: 500; color: var(--hb-muted); font-size: .72rem; }
.hb-section-title { text-align: center; margin: 2.6rem 0 .3rem; font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em; color: var(--hb-navy); }
.hb-section-sub { text-align: center; color: var(--hb-muted); margin-bottom: 1.4rem; }
div[class*="st-key-hbrole"] { background: var(--hb-surface); border: 1px solid var(--hb-border); border-radius: 18px;
  box-shadow: var(--hb-shadow); padding: 1.4rem 1.3rem 1.2rem; transition: all .15s ease; height: 100%; }
div[class*="st-key-hbrole"]:hover { border-color: var(--hb-teal); box-shadow: var(--hb-shadow-lg); transform: translateY(-2px); }
.hb-role { min-height: 300px; }
.hb-demo.inline { display: inline-flex; padding: .35rem .9rem; }
.hb-role .role { font-size: .72rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; margin-top: .9rem; }
.hb-role .who { font-size: 1.2rem; font-weight: 800; color: var(--hb-navy); letter-spacing: -0.01em; margin-top: .15rem; }
.hb-role .org { font-size: .82rem; color: var(--hb-muted); }
.hb-role ul { margin: .8rem 0 .4rem; padding-left: 1.1rem; font-size: .84rem; color: var(--hb-navy-600); }
.hb-role li { margin-bottom: .2rem; }
.hb-ccc { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; gap: .8rem; align-items: stretch; }
.hb-ccc .step { background: #fff; border: 1px solid var(--hb-border); border-radius: 18px; padding: 1.4rem; box-shadow: var(--hb-shadow); }
.hb-ccc .step .k { font-size: .78rem; font-weight: 800; letter-spacing: .18em; color: var(--hb-teal); margin-top: .8rem; }
.hb-ccc .step .t { font-size: 1.02rem; font-weight: 700; color: var(--hb-navy); margin-top: .3rem; }
.hb-ccc .arrow { display: flex; align-items: center; color: var(--hb-teal-100); }
.hb-landing-foot { margin-top: 2.6rem; padding: 1.2rem 0; border-top: 1px solid var(--hb-border); display: flex;
  justify-content: space-between; gap: 1rem; flex-wrap: wrap; font-size: .8rem; color: var(--hb-subtle); }
@media (max-width: 900px) { .hb-ccc { grid-template-columns: 1fr; } .hb-ccc .arrow { justify-content: center; transform: rotate(90deg); }
  .hb-hero-title { font-size: 2.3rem; } }

/* Responsive: on mid-size screens let column rows wrap instead of squeezing (KPIs go 2x2, splits stack). */
@media (max-width: 1180px) {
  section[data-testid="stMain"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  section[data-testid="stMain"] [data-testid="stColumn"] { flex: 1 1 280px !important; min-width: min(100%, 280px) !important; }
  [data-testid="stMainBlockContainer"], .block-container { padding-left: 1.25rem; padding-right: 1.25rem; }
  .hb-page-title { font-size: 1.5rem !important; }
}

/* Footer */
.hb-footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--hb-border); display: flex;
  gap: .5rem; align-items: center; font-size: .76rem; color: var(--hb-subtle); }
""".replace("ROOT_TOKENS", _ROOT)


def inject_theme() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
