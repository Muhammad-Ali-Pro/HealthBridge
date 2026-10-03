"""HealthBridge — Streamlit entry point and router.  Run:  streamlit run app.py"""

import streamlit as st

from ui import landing, shell
from ui.components import disclaimer_footer
from ui.theme import inject_theme

st.set_page_config(
    page_title="HealthBridge",
    page_icon=str(shell.LOGO_MARK),
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()
shell.bootstrap_db()
shell.handle_deep_link()

if not shell.has_entered():
    landing.render()
else:
    actor = shell.resolve_actor()
    page = shell.build_navigation(actor)
    shell.render_sidebar(page, actor)
    shell.render_topbar(page, actor)
    page.run()
    disclaimer_footer()
