"""
Akar News Search & Analysis Portal
───────────────────────────────────
pip install streamlit gnews pandas textblob plotly newspaper3k \
            google-generativeai googlenewsdecoder lxml_html_parser
"""

import streamlit as st
from gnews import GNews
import pandas as pd
from textblob import TextBlob
from datetime import datetime
import plotly.express as px
import time
import random
import nltk

# ── Optional imports (graceful fallback) ──
try:
    from googlenewsdecoder import gnewsdecoder
    HAS_DECODER = True
except ImportError:
    HAS_DECODER = False

try:
    from newspaper import Article as NewspaperArticle
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("brown", quiet=True)
nltk.download("wordnet", quiet=True)
nltk.download("averaged_perceptron_tagger", quiet=True)
nltk.download("averaged_perceptron_tagger_eng", quiet=True)
nltk.download("conll2000", quiet=True)
nltk.download("movie_reviews", quiet=True)

st.set_page_config(page_title="Akar News Search & Analysis", layout="wide")

# ===================== Custom CSS =====================
st.markdown("""
<style>
.news-table { font-family:'Segoe UI',sans-serif; border-collapse:collapse; width:100%; }
.news-table td,.news-table th { border:1px solid #ddd; padding:8px; vertical-align:top; }
.news-table tr:nth-child(even) { background:#f2f2f2; }
.news-table tr:hover { background:#ddd; }
.news-table th { padding:12px 8px; text-align:left; background:#4CAF50; color:#fff; }
.metrics-container { display:flex; justify-content:space-between; margin-bottom:20px; gap:15px; flex-wrap:wrap; }
.metric-box { flex:1; min-width:160px; padding:15px 20px; border-radius:8px;
              box-shadow:0 4px 6px rgba(0,0,0,.1); text-align:center; color:#fff; }
.metric-positive { background:linear-gradient(135deg,#4CAF50,#2E7D32); }
.metric-neutral  { background:linear-gradient(135deg,#78909C,#455A64); }
.metric-negative { background:linear-gradient(135deg,#F44336,#C62828); }
.metric-non      { background:linear-gradient(135deg,#607D8B,#37474F); }
.metric-total    { background:linear-gradient(135deg,#3F51B5,#1A237E); }
.metric-value { font-size:24px; font-weight:bold; margin-bottom:5px; }
.metric-label { font-size:14px; opacity:.9; }
.summary-cell { font-size:12px; color:#333; line-height:1.5; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<h2 style='text-align:center;color:#fff;background:#262730;padding:10px;border-radius:10px;'>
📰 Akar's News Search and Analysis Portal
</h2>
""", unsafe_allow_html=True)

# ===================== Fixed Queries =====================
FIXED_QUERIES = [
    "Dharavi", "Dharavi redevelopment project", "Dharavi slum",
    "DRP Dharavi", "Navbharat Mega Developers", "NMDPL Dharavi",
    "Dharavi Slum Rehabilitation Authority", "Devendra Fadnavis Dharavi",
    "Eknath Shinde Dharavi", "Bombay High Court Dharavi",
    "eviction Dharavi redevelopment", "Dharavi survey", "Dharavi SRA",
    "Varsha Gaikwad Dharavi", "Jyoti Gaikwad Dharavi",
    "Rahul Shewale Dharavi", "Bhaskar Shetty Dharavi",
]
LANGS = [("English", "en"), ("Hindi", "hi"), ("Marathi", "mr")]
COUNTRY = "IN"

# ===================== Session State =====================
for key, default in [
    ("all_results", []), ("seen_keys", set()), ("df", pd.DataFrame()),
    ("sources_list", []), ("selected_sources", []), ("has_fetched", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ════════════════════════════════════════════════════════
# Google News URL → Real URL → Full Article
# ════════════════════════════════════════════════════════

def decode_gnews_url(google_url: str) -> str:
    """
    Decode a Google News redirect URL to the real publisher URL.
    Uses googlenewsdecoder which calls Google's server-side API.
    """
    if not HAS_DECODER or "news.google.com" not in google_url:
        return google_url
    try:
        result = gnewsdecoder(google_url, interval=1)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception:
        pass
    return google_url


def scrape_full_article(real_url: str) -> str:
    """Scrape article text from a real publisher URL using newspaper3k."""
    if not HAS_NEWSPAPER:
        return ""
    try:
        art = NewspaperArticle(real_url)
        art.download()
        art.parse()
        text = (art.text or "").strip()
        return text if len(text) > 80 else ""
    except Exception:
        return ""


def extract_article(google_url: str) -> tuple:
    """Full pipeline: Google News URL → decode → scrape. Returns (full_text, real_url)."""
    real_url = decode_gnews_url(google_url)
    full_text = ""
    if real_url and "news.google.com" not in real_url:
        full_text = scrape_full_article(real_url)
    return full_text, real_url


# ===================== Helpers =====================

def reset_state():
    st.session_state.all_results = []
    st.session_state.seen_keys = set()
    st.session_state.df = pd.DataFrame()
    st.session_state.sources_list = []
    st.session_state.selected_sources = []
    st.session_state.has_fetched = False


def normalize_publisher(pub):
    if isinstance(pub, dict):
        return pub.get("title") or pub.get("name") or ""
    return "" if pub is None else str(pub)


def add_results(results, query, lang_label, extract_full=True, status_widget=None):
    for item in results:
        title = (item.get("title") or "").strip()
        desc = (item.get("description") or "").strip()
        url = (item.get("url") or "").strip()
        publisher = normalize_publisher(item.get("publisher"))
        published = item.get("published date")

        key = f"{title}||{publisher}||{url}"
        if not title or key in st.session_state.seen_keys:
            continue
        st.session_state.seen_keys.add(key)

        full_text, real_url = "", url
        if extract_full and url:
            if status_widget:
                status_widget.write(f"📄 Extracting: {title[:60]}…")
            full_text, real_url = extract_article(url)

        st.session_state.all_results.append({
            "title": title, "desc": desc, "full_text": full_text,
            "link": real_url, "google_link": url, "media": publisher,
            "published": "" if published is None else str(published),
            "query": query, "language": lang_label, "summary": "",
        })

        if publisher and publisher not in st.session_state.sources_list:
            st.session_state.sources_list.append(publisher)


def fetch_one_query(query, lang_code, lang_label, days, max_results,
                    extract_full=True, status_widget=None):
    gn = GNews(language=lang_code, country=COUNTRY,
               period=f"{days}d", max_results=max_results)
    results = gn.get_news(query) or []
    add_results(results, query=query, lang_label=lang_label,
                extract_full=extract_full, status_widget=status_widget)


# ===================== Gemini Summariser =====================
GEMINI_MODEL = "gemini-2.5-flash-lite"


def summarise_articles(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """
    Generate 3-line summaries using Gemini.
    Uses TITLE + ARTICLE BODY (full_text) when available.
    Falls back to TITLE + DESCRIPTION when article body is missing.
    """
    if not HAS_GENAI:
        st.error("google-generativeai not installed.")
        return df

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    summaries = [""] * len(df)
    total = len(df)
    progress = st.progress(0)
    status = st.empty()

    for pos in range(total):
        row = df.iloc[pos]
        title = row.get("title", "")
        full_text = row.get("full_text", "") or ""
        desc = row.get("desc", "") or ""

        status.write(f"✍️ Summarising {pos+1}/{total}: {title[:50]}…")

        # ── Build the best available content for summarisation ──
        has_body = len(full_text.strip()) > 80

        if has_body:
            # BEST CASE: we have the full article body
            content_block = f"Article Body:\n{full_text[:5000]}"
            instruction = (
                "Based on the title and article body below, write EXACTLY 3 concise summary lines. "
                "Each line must capture a distinct key point from the article. "
                "Do not use numbering or bullet points."
            )
        else:
            # FALLBACK: only title (+ description which is usually same as title)
            # Ask Gemini to use its knowledge to provide context
            content_block = f"Description: {desc}" if desc.strip() != title.strip() else ""
            instruction = (
                "Based on the news headline below, write EXACTLY 3 concise informative lines. "
                "Line 1: Restate the core news event clearly. "
                "Line 2: Provide likely context or background (who, why, where). "
                "Line 3: State the probable significance or impact. "
                "Use your knowledge of Indian urban development and Dharavi redevelopment for context. "
                "Do not use numbering or bullet points."
            )

        prompt = f"{instruction}\n\nTitle: {title}\n{content_block}\n\n3-line summary:"

        try:
            resp = model.generate_content(prompt)
            summaries[pos] = resp.text.strip()
        except Exception as e:
            summaries[pos] = f"⚠️ {e}"

        progress.progress(min((pos + 1) / total, 1.0))
        time.sleep(0.3)

    status.empty()
    progress.empty()
    df["summary"] = summaries
    return df


# ===================== Sidebar =====================
with st.sidebar:
    st.header("🔑 Gemini API Key")
    gemini_key = st.text_input(
        "Enter your Gemini API key", type="password",
        help="Free key → https://aistudio.google.com/apikey",
    )
    st.caption(f"Model: `{GEMINI_MODEL}` ($0.10 / $0.40 per 1M tokens)")

    st.divider()
    st.header("⚙️ Options")
    enable_full_text = st.checkbox("Extract full article text", value=True,
        help="Resolves Google News URLs → scrapes publisher page. Slower but gives much better summaries.")
    enable_summary = st.checkbox("Generate AI summaries", value=True)

    st.divider()
    st.header("📦 Status")
    st.write(f"URL Decoder: {'✅' if HAS_DECODER else '❌ `pip install googlenewsdecoder`'}")
    st.write(f"Article Scraper: {'✅' if HAS_NEWSPAPER else '❌ `pip install newspaper3k`'}")
    st.write(f"Gemini API: {'✅' if HAS_GENAI else '❌ `pip install google-generativeai`'}")


# ===================== Main UI =====================
st.subheader("Fixed Search Filters")

colA, colB = st.columns([3, 2])
with colA:
    st.info(
        "Runs fixed queries × 3 languages (EN / HI / MR), Country = India.\n\n"
        "**Summary logic:**\n"
        "- If full article body extracted → summary from **title + article body**\n"
        "- If extraction fails → summary from **title + Gemini's knowledge**"
    )
with colB:
    if st.button("♻️ Reset"):
        reset_state()
        st.rerun()

days = st.slider("Select day range (past N days)", 1, 30, 2, 1)
max_results = st.slider("Max results per query (per language)", 5, 30, 10, 5)

run_btn = st.button("🚀 Fetch News", type="primary")


# ===================== Fetch Runner =====================
if run_btn:
    reset_state()
    st.session_state.has_fetched = True

    if enable_full_text and not HAS_DECODER:
        st.error("❌ `googlenewsdecoder` not installed. Run: `pip install googlenewsdecoder`")
    if enable_full_text and not HAS_NEWSPAPER:
        st.error("❌ `newspaper3k` not installed. Run: `pip install newspaper3k`")

    total_steps = len(FIXED_QUERIES) * len(LANGS)
    progress = st.progress(0)
    status = st.empty()
    extract_status = st.empty()

    step = 0
    with st.spinner("Fetching news across all queries & languages…"):
        for q in FIXED_QUERIES:
            for (lang_label, lang_code) in LANGS:
                step += 1
                status.write(f"🔎 [{step}/{total_steps}] {lang_label}: {q}")
                try:
                    fetch_one_query(
                        q, lang_code=lang_code, lang_label=lang_label,
                        days=days, max_results=max_results,
                        extract_full=enable_full_text,
                        status_widget=extract_status,
                    )
                except Exception as e:
                    st.warning(f"Failed for '{q}' ({lang_label}): {e}")
                progress.progress(step / total_steps)
                time.sleep(random.uniform(0.1, 0.25))

    progress.empty()
    status.empty()
    extract_status.empty()

    st.session_state.df = pd.DataFrame(st.session_state.all_results)
    if not st.session_state.df.empty:
        st.session_state.df = (
            st.session_state.df
            .drop_duplicates(subset=["title", "media", "link"])
            .reset_index(drop=True)
        )

    # ── Extraction stats ──
    if not st.session_state.df.empty:
        n_total = len(st.session_state.df)
        n_body = (st.session_state.df["full_text"].str.len() > 80).sum()
        if n_body > 0:
            st.info(f"📊 Full article text extracted for **{n_body}/{n_total}** articles. "
                    f"Summaries will use article body where available.")
        else:
            st.info(f"📊 **{n_total}** articles found. Article body extraction was not possible — "
                    f"summaries will be generated from **title + Gemini's contextual knowledge**.")

    # ── Gemini Summarisation ──
    if enable_summary and gemini_key and not st.session_state.df.empty:
        st.subheader("🤖 Generating AI Summaries…")
        st.session_state.df = summarise_articles(st.session_state.df, gemini_key)
        st.success("✅ Summaries generated!")
    elif enable_summary and not gemini_key:
        st.warning("⚠️ Enter your Gemini API key in the sidebar to enable AI summaries.")


# ===================== Display =====================
if not st.session_state.df.empty:
    display_df = st.session_state.df.copy()

    # Source filter
    st.subheader("Filter by Source")
    st.session_state.selected_sources = st.multiselect(
        "Select news sources to display",
        options=sorted(st.session_state.sources_list), default=[],
    )
    if st.session_state.selected_sources:
        display_df = display_df[display_df["media"].isin(st.session_state.selected_sources)].copy()

    # Sentiment (English-only via TextBlob)
    display_df["polarity"] = None
    display_df["sentiment"] = "Non"
    mask_en = display_df["language"].eq("English")
    display_df.loc[mask_en, "polarity"] = (
        display_df.loc[mask_en, "title"].fillna("") + ". " +
        display_df.loc[mask_en, "desc"].fillna("")
    ).apply(lambda x: TextBlob(str(x)).sentiment.polarity)
    display_df.loc[mask_en, "sentiment"] = display_df.loc[mask_en, "polarity"].apply(
        lambda x: "Positive" if x > 0 else ("Negative" if x < 0 else "Neutral")
    )

    sentiment_colors = {"Positive": "green", "Negative": "red", "Neutral": "gray", "Non": "#607D8B"}

    n_with_text = (display_df["full_text"].str.len() > 80).sum()
    n_with_summ = (display_df["summary"].str.len() > 10).sum()
    st.success(
        f"Showing **{len(display_df)}** articles (past {days} days) · "
        f"Full text: **{n_with_text}** · Summaries: **{n_with_summ}**"
    )

    # Build HTML table
    df_show = display_df[[
        "title", "media", "published", "language", "query",
        "desc", "full_text", "link", "sentiment", "summary"
    ]].copy()

    df_show["Sentiment"] = df_show["sentiment"].apply(
        lambda x: f"<span style='color:{sentiment_colors.get(x,'black')};font-weight:600'>{x}</span>"
    )
    df_show["Title"] = df_show.apply(
        lambda r: f"<a href='{r['link']}' target='_blank'>{r['title']}</a>"
        if r["link"] else r["title"], axis=1,
    )
    df_show["Article Body"] = df_show["full_text"].apply(
        lambda x: (x[:300] + "…") if isinstance(x, str) and len(x) > 300 else (x if x else "—")
    )
    df_show["AI Summary"] = df_show["summary"].apply(
        lambda x: f"<div class='summary-cell'>{x}</div>" if x else "—"
    )
    df_show = df_show.rename(columns={
        "media": "Source", "language": "Language", "query": "Matched Query",
        "desc": "Description", "published": "Published",
    })
    df_show = df_show[[
        "Title", "Source", "Published", "Language", "Matched Query",
        "Description", "Article Body", "AI Summary", "Sentiment"
    ]]

    st.subheader("Search Results (All-in-One)")
    st.markdown(df_show.to_html(escape=False, index=False, classes="news-table"),
                unsafe_allow_html=True)

    # CSV download
    dl = display_df[[
        "title", "media", "published", "language", "query",
        "desc", "full_text", "link", "sentiment", "summary"
    ]].copy().rename(columns={
        "title": "Title", "media": "Source", "published": "Published",
        "language": "Language", "query": "Matched Query", "desc": "Description",
        "full_text": "Article Body", "link": "URL",
        "sentiment": "Sentiment", "summary": "AI Summary",
    })
    st.download_button(
        "📥 Download Results as CSV",
        data=dl.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"dharavi_news_{days}d_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv", key="download-csv",
    )

    # ===================== Charts =====================
    st.subheader("Overall Tone Summary")
    counts = display_df["sentiment"].value_counts().reindex(
        ["Positive", "Neutral", "Negative", "Non"], fill_value=0
    )
    total_articles = len(display_df)

    st.markdown(f"""
    <div class="metrics-container">
        <div class="metric-box metric-positive">
            <div class="metric-value">{int(counts['Positive'])}</div>
            <div class="metric-label">Positive (EN)</div></div>
        <div class="metric-box metric-neutral">
            <div class="metric-value">{int(counts['Neutral'])}</div>
            <div class="metric-label">Neutral (EN)</div></div>
        <div class="metric-box metric-negative">
            <div class="metric-value">{int(counts['Negative'])}</div>
            <div class="metric-label">Negative (EN)</div></div>
        <div class="metric-box metric-non">
            <div class="metric-value">{int(counts['Non'])}</div>
            <div class="metric-label">Non (HI/MR)</div></div>
        <div class="metric-box metric-total">
            <div class="metric-value">{int(total_articles)}</div>
            <div class="metric-label">Total Articles</div></div>
    </div>
    """, unsafe_allow_html=True)

    fig = px.pie(names=counts.index, values=counts.values,
                 title="Overall Sentiment Distribution", hole=0.55)
    fig.update_traces(textinfo="percent")
    st.plotly_chart(fig, use_container_width=True)

elif st.session_state.has_fetched:
    st.warning("No articles found for the selected filters.")
else:
    st.info("Select day range and click **Fetch News**.")
