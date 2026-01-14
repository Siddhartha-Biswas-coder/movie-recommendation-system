import os
import requests
import streamlit as st

# =============================
# CONFIG  (FIXED)
# =============================
API_BASE = os.getenv(
    "API_BASE",
    "https://movie-recommendation-system-8a1e.onrender.com"
)
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

st.set_page_config(page_title="Movie Recommender", page_icon="🎬", layout="wide")

# =============================
# STYLES (minimal modern)
# =============================
st.markdown(
    """
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px; }
.small-muted { color:#6b7280; font-size: 0.92rem; }
.movie-title { font-size: 0.9rem; line-height: 1.15rem; height: 2.3rem; overflow: hidden; }
.card { border: 1px solid rgba(0,0,0,0.08); border-radius: 16px; padding: 14px; background: rgba(255,255,255,0.7); }
</style>
""",
    unsafe_allow_html=True,
)

# =============================
# STATE + ROUTING (SAFE)
# =============================
if "view" not in st.session_state:
    st.session_state.view = "home"
if "selected_tmdb_id" not in st.session_state:
    st.session_state.selected_tmdb_id = None

qp = st.query_params
qp_view = qp.get("view", None)
qp_id = qp.get("id", None)

if qp_view in ("home", "details"):
    st.session_state.view = qp_view

if qp_id:
    try:
        st.session_state.selected_tmdb_id = int(qp_id)
        st.session_state.view = "details"
    except:
        pass


def goto_home():
    st.session_state.view = "home"
    st.query_params.clear()
    st.query_params["view"] = "home"
    st.rerun()


def goto_details(tmdb_id: int):
    st.session_state.view = "details"
    st.session_state.selected_tmdb_id = int(tmdb_id)
    st.query_params.clear()
    st.query_params["view"] = "details"
    st.query_params["id"] = str(int(tmdb_id))
    st.rerun()


# =============================
# API HELPERS (SAFE)
# =============================
@st.cache_data(ttl=30)
def api_get_json(path: str, params: dict | None = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=20)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}"
        return r.json(), None
    except Exception:
        return None, "Backend unreachable (cold start or sleeping)"


def poster_grid(cards, cols=6, key_prefix="grid"):
    if not cards:
        st.info("No movies to show.")
        return

    rows = (len(cards) + cols - 1) // cols
    idx = 0
    for r in range(rows):
        colset = st.columns(cols)
        for c in range(cols):
            if idx >= len(cards):
                break
            m = cards[idx]
            idx += 1

            with colset[c]:
                if m.get("poster_url"):
                    st.image(m["poster_url"], use_column_width=True)
                else:
                    st.write("🖼️ No poster")

                if st.button("Open", key=f"{key_prefix}_{m.get('tmdb_id')}"):
                    goto_details(m["tmdb_id"])

                st.markdown(
                    f"<div class='movie-title'>{m.get('title','Untitled')}</div>",
                    unsafe_allow_html=True,
                )


def to_cards_from_tfidf_items(items):
    cards = []
    for x in items or []:
        tmdb = x.get("tmdb") or {}
        if tmdb.get("tmdb_id"):
            cards.append(
                {
                    "tmdb_id": tmdb["tmdb_id"],
                    "title": tmdb.get("title", "Untitled"),
                    "poster_url": tmdb.get("poster_url"),
                }
            )
    return cards


def parse_tmdb_search_to_cards(data, keyword: str, limit: int = 24):
    keyword_l = keyword.lower()
    raw_items = []

    if isinstance(data, dict) and "results" in data:
        for m in data["results"]:
            if m.get("title") and m.get("id"):
                raw_items.append(
                    {
                        "tmdb_id": m["id"],
                        "title": m["title"],
                        "poster_url": f"{TMDB_IMG}{m['poster_path']}" if m.get("poster_path") else None,
                        "release_date": m.get("release_date", ""),
                    }
                )

    elif isinstance(data, list):
        for m in data:
            if m.get("title") and (m.get("tmdb_id") or m.get("id")):
                raw_items.append(
                    {
                        "tmdb_id": m.get("tmdb_id") or m.get("id"),
                        "title": m["title"],
                        "poster_url": m.get("poster_url"),
                        "release_date": m.get("release_date", ""),
                    }
                )

    matched = [x for x in raw_items if keyword_l in x["title"].lower()]
    final_list = matched if matched else raw_items

    suggestions = []
    for x in final_list[:10]:
        year = x.get("release_date", "")[:4]
        label = f"{x['title']} ({year})" if year else x["title"]
        suggestions.append((label, x["tmdb_id"]))

    cards = [
        {"tmdb_id": x["tmdb_id"], "title": x["title"], "poster_url": x["poster_url"]}
        for x in final_list[:limit]
    ]

    return suggestions, cards


# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## 🎬 Menu")
    if st.button("🏠 Home"):
        goto_home()

    st.markdown("---")
    home_category = st.selectbox(
        "Home Category",
        ["trending", "popular", "top_rated", "now_playing", "upcoming"],
    )
    grid_cols = st.slider("Grid columns", 4, 8, 6)


# =============================
# HEADER
# =============================
st.title("🎬 Movie Recommender")
st.markdown(
    "<div class='small-muted'>Search → select → view details → recommendations</div>",
    unsafe_allow_html=True,
)
st.divider()

# =============================
# HOME
# =============================
if st.session_state.view == "home":
    typed = st.text_input("Search movie title")

    if typed.strip():
        if len(typed) < 2:
            st.info("Type at least 2 characters")
        else:
            data, err = api_get_json("/tmdb/search", {"query": typed})
            if err or not data:
                st.warning(err)
            else:
                suggestions, cards = parse_tmdb_search_to_cards(data, typed)

                labels = ["-- Select --"] + [s[0] for s in suggestions]
                selected = st.selectbox("Suggestions", labels)

                if selected != "-- Select --":
                    goto_details(dict(suggestions)[selected])

                poster_grid(cards, grid_cols, "search")

        st.stop()

    home_cards, err = api_get_json("/home", {"category": home_category, "limit": 24})
    if err or not home_cards:
        st.warning("Backend sleeping. Try refresh.")
    else:
        poster_grid(home_cards, grid_cols, "home")


# =============================
# DETAILS
# =============================
elif st.session_state.view == "details":
    tmdb_id = st.session_state.selected_tmdb_id

    if not tmdb_id:
        st.warning("No movie selected")
        st.stop()

    if st.button("← Back"):
        goto_home()

    data, err = api_get_json(f"/movie/id/{tmdb_id}")
    if err or not data:
        st.warning(err)
        st.stop()

    left, right = st.columns([1, 2.4])

    with left:
        if data.get("poster_url"):
            st.image(data["poster_url"])

    with right:
        st.header(data.get("title"))
        st.caption(data.get("release_date"))
        st.write(data.get("overview"))

    bundle, err = api_get_json(
        "/movie/search",
        {"query": data.get("title"), "tfidf_top_n": 12, "genre_limit": 12},
    )

    if bundle:
        st.subheader("Similar Movies")
        poster_grid(to_cards_from_tfidf_items(bundle.get("tfidf_recommendations")), grid_cols, "tfidf")
