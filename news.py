import streamlit as st
from gnews import GNews
import pandas as pd
from textblob import TextBlob
from datetime import datetime
import plotly.express as px
import io
import time
import random
import requests
import nltk
import google.generativeai as genai

try:
    from newspaper import Article as NewspaperArticle
except ImportError:
    NewspaperArticle = None

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
st.markdown(
    """
    <style>
    .news-table {
        font-family: 'Segoe UI', sans-serif;
        border-collapse: collapse;
        width: 100%;
    }
    .news-table td, .news-table th {
        border: 1px solid #ddd;
        padding: 8px;
        vertical-align: top;
    }
    .news-table tr:nth-child(even) { background-color: #f2f2f2; }
    .news-table tr:hover { background-color: #ddd; }
    .news-table th {
        padding-top: 12px;
        padding-bottom: 12px;
        text-align: left;
        background-color: #4CAF50;
        color: white;
    }
    .metrics-container {
        display: flex;
        justify-content: space-between;
        margin-bottom: 20px;
        gap: 15px;
        flex-wrap: wrap;
    }
    .metric-box {
        flex: 1;
        min-width: 160px;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        color: white;
    }
    .metric-positive { background: linear-gradient(135deg, #4CAF50, #2E7D32); }
    .metric-neutral  { background: linear-gradient(135deg, #78909C, #455A64); }
    .metric-negative { background: linear-gradient(135deg, #F44336, #C62828); }
    .metric-non      { background: linear-gradient(135deg, #607D8B, #37474F); }
    .metric-total    { background: linear-gradient(135deg, #3F51B5, #1A237E); }
    .metric-value { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
    .metric-label { font-size: 14px; opacity: 0.9; }
    .summary-cell { font-size: 12px; color: #333; line-height: 1.5; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <h2 style='text-align:center;color:#fff;background:#262730;padding:10px;border-radius:10px;'>
    📰 Akar's News Search and Analysis Portal
    </h2>
    """,
    unsafe_allow_html=True,
)

# ===================== Fixed Queries =====================
FIXED_QUERIES = [
    "Dharavi",
    "Dharavi redevelopment project",
    "Dharavi slum",
    "DRP Dharavi",
    "Navbharat Mega Developers",
    "NMDPL Dharavi",
    "Dharavi Slum Rehabilitation Authority",
    "Devendra Fadnavis Dharavi",
    "Eknath Shinde Dharavi",
    "Bombay High Court Dharavi",
    "eviction Dharavi redevelopment",
    "Dharavi survey",
    "Dharavi SRA",
    "Varsha Gaikwad Dharavi",
    "Jyoti Gaikwad Dharavi",
    "Rahul Shewale Dharavi",
    "Bhaskar Shetty Dharavi",
]

LANGS = [("English", "en"), ("Hindi", "hi"), ("Marathi", "mr")]
COUNTRY = "IN"

# ===================== Session State =====================
for key, default in [
    ("all_results", []),
    ("seen_keys", set()),
    ("df", pd.DataFrame()),
    ("sources_list", []),
    ("selected_sources", []),
    ("has_fetched", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ===================== Article Extraction Helpers =====================

def resolve_google_news_url(google_url: str, timeout: int = 10) -> str:
    """
    Follow the Google News redirect chain to get the real article URL.
    GNews returns URLs like news.google.com/rss/articles/CBMi...
    These are HTTP 301/302 redirects to the actual publisher page.
    """
    if "news.google.com" not in google_url:
        return google_url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        # Try HEAD first (lighter)
        resp = requests.head(google_url, allow_redirects=True,
                             timeout=timeout, headers=headers)
        if resp.url and "news.google.com" not in resp.url:
            return resp.url
    except Exception:
        pass

    try:
        # Fall back to GET with stream (some servers block HEAD)
        resp = requests.get(google_url, allow_redirects=True,
                            timeout=timeout, headers=headers, stream=True)
        final_url = resp.url
        resp.close()
        if final_url and "news.google.com" not in final_url:
            return final_url
    except Exception:
        pass

    return google_url


def scrape_article_text(url: str) -> tuple:
    """
    1. Resolve Google News redirect → real publisher URL.
    2. Download & parse full article text with newspaper3k.
    Returns (full_text: str, real_url: str).
    """
    real_url = resolve_google_news_url(url)

    if NewspaperArticle is None:
        return "", real_url

    try:
        art = NewspaperArticle(real_url)
        art.download()
        art.parse()
        text = (art.text or "").strip()
        if len(text) > 80:  # at least a meaningful paragraph
            return text, real_url
    except Exception:
        pass

    return "", real_url


# ===================== Core Helpers =====================

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


def add_results(results, query: str, lang_label: str, extract_full: bool = True):
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

        # --- Extract full article body ---
        full_text = ""
        real_url = url
        if extract_full and url:
            full_text, real_url = scrape_article_text(url)

        st.session_state.all_results.append({
            "title": title,
            "desc": desc,
            "full_text": full_text,
            "link": real_url,          # resolved publisher URL
            "google_link": url,        # original Google News URL
            "media": publisher,
            "published": "" if published is None else str(published),
            "query": query,
            "language": lang_label,
            "summary": "",
        })

        if publisher and publisher not in st.session_state.sources_list:
            st.session_state.sources_list.append(publisher)


def fetch_one_query(query: str, lang_code: str, lang_label: str,
                    days: int, max_results: int, extract_full: bool = True):
    gn = GNews(language=lang_code, country=COUNTRY,
               period=f"{days}d", max_results=max_results)
    results = gn.get_news(query) or []
    add_results(results, query=query, lang_label=lang_label, extract_full=extract_full)


# ===================== Gemini Summariser =====================
# gemini-2.5-flash-lite: $0.10 / 1M input, $0.40 / 1M output — cheapest available
GEMINI_MODEL = "gemini-2.5-flash-lite"


def summarise_articles(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """Generate 3-line summaries using the cheapest Gemini model."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    summaries = [""] * len(df)
    total = len(df)
    progress = st.progress(0)
    status = st.empty()

    for pos in range(total):
        row = df.iloc[pos]
        status.write(f"✍️ Summarising article {pos + 1}/{total}…")

        # Prefer full_text → desc → title
        content = row.get("full_text") or row.get("desc") or row.get("title") or ""
        if not content.strip():
            summaries[pos] = "No content available."
            progress.progress(min((pos + 1) / total, 1.0))
            continue

        prompt = (
            "Summarise the following news article in EXACTLY 3 concise lines. "
            "Each line should capture a distinct key point. "
            "Do not use numbering or bullet points.\n\n"
            f"Title: {row['title']}\n\n"
            f"Article:\n{content[:5000]}\n\n"
            "3-line summary:"
        )

        try:
            resp = model.generate_content(prompt)
            summaries[pos] = resp.text.strip()
        except Exception as e:
            summaries[pos] = f"⚠️ {e}"

        progress.progress(min((pos + 1) / total, 1.0))
        time.sleep(0.25)

    status.empty()
    progress.empty()
    df["summary"] = summaries
    return df


# ===================== Sidebar =====================
with st.sidebar:
    st.header("🔑 Gemini API Key")
    gemini_key = st.text_input(
        "Enter your Gemini API key",
        type="password",
        help="Required for AI summaries. Free key → https://aistudio.google.com/apikey",
    )
    st.caption(f"Model: `{GEMINI_MODEL}` — cheapest tier ($0.10/$0.40 per 1M tokens)")
    enable_full_text = st.checkbox("Extract full article text (slower but accurate)", value=True)
    enable_summary = st.checkbox("Generate AI summaries (Gemini)", value=True)


# ===================== Main UI =====================
st.subheader("Fixed Search Filters")

colA, colB = st.columns([3, 2])
with colA:
    st.info(
        "Runs fixed queries × 3 languages (EN/HI/MR), Country = India.\n"
        "Sentiment: English only (TextBlob). Hindi/Marathi ⇒ Non.\n"
        f"AI summaries: `{GEMINI_MODEL}` (enter API key in sidebar)."
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

    total_steps = len(FIXED_QUERIES) * len(LANGS)
    progress = st.progress(0)
    status = st.empty()

    step = 0
    with st.spinner("Fetching news across all queries & languages…"):
        for q in FIXED_QUERIES:
            for (lang_label, lang_code) in LANGS:
                step += 1
                status.write(f"🔎 [{step}/{total_steps}] {lang_label}: {q}")
                try:
                    fetch_one_query(q, lang_code=lang_code, lang_label=lang_label,
                                    days=days, max_results=max_results,
                                    extract_full=enable_full_text)
                except Exception as e:
                    st.warning(f"Failed for '{q}' ({lang_label}): {e}")
                progress.progress(step / total_steps)
                time.sleep(random.uniform(0.15, 0.35))

    progress.empty()
    status.empty()

    st.session_state.df = pd.DataFrame(st.session_state.all_results)
    if not st.session_state.df.empty:
        st.session_state.df = (
            st.session_state.df
            .drop_duplicates(subset=["title", "media", "link"])
            .reset_index(drop=True)
        )

    # --- Gemini Summarisation ---
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
        options=sorted(st.session_state.sources_list),
        default=[],
    )
    if st.session_state.selected_sources:
        display_df = display_df[display_df["media"].isin(st.session_state.selected_sources)].copy()

    # Sentiment (English-only via TextBlob)
    display_df["polarity"] = None
    display_df["sentiment"] = "Non"

    mask_en = display_df["language"].eq("English")
    display_df.loc[mask_en, "polarity"] = (
        display_df.loc[mask_en, "title"].fillna("")
        + ". "
        + display_df.loc[mask_en, "desc"].fillna("")
    ).apply(lambda x: TextBlob(str(x)).sentiment.polarity)
    display_df.loc[mask_en, "sentiment"] = display_df.loc[mask_en, "polarity"].apply(
        lambda x: "Positive" if x > 0 else ("Negative" if x < 0 else "Neutral")
    )

    sentiment_colors = {
        "Positive": "green", "Negative": "red",
        "Neutral": "gray", "Non": "#607D8B",
    }

    # Stats
    n_with_text = (display_df["full_text"].str.len() > 80).sum()
    n_with_summary = (display_df["summary"].str.len() > 10).sum()
    st.success(
        f"Showing **{len(display_df)}** articles (past {days} days) · "
        f"Full text: **{n_with_text}** · Summaries: **{n_with_summary}**"
    )

    # Build HTML table
    df_display = display_df[
        ["title", "media", "published", "language", "query",
         "desc", "full_text", "link", "sentiment", "summary"]
    ].copy()

    df_display["Sentiment"] = df_display["sentiment"].apply(
        lambda x: f"<span style='color:{sentiment_colors.get(x, 'black')};font-weight:600'>{x}</span>"
    )
    df_display["Title"] = df_display.apply(
        lambda r: f"<a href='{r['link']}' target='_blank'>{r['title']}</a>"
        if r["link"] else r["title"],
        axis=1,
    )
    df_display["Article Body"] = df_display["full_text"].apply(
        lambda x: (x[:300] + "…") if isinstance(x, str) and len(x) > 300 else (x if x else "—")
    )
    df_display["AI Summary"] = df_display["summary"].apply(
        lambda x: f"<div class='summary-cell'>{x}</div>" if x else "—"
    )

    df_display = df_display.rename(columns={
        "media": "Source",
        "language": "Language",
        "query": "Matched Query",
        "desc": "Description",
        "published": "Published",
    })

    df_display = df_display[
        ["Title", "Source", "Published", "Language", "Matched Query",
         "Description", "Article Body", "AI Summary", "Sentiment"]
    ]

    st.subheader("Search Results (All-in-One)")
    st.markdown(
        df_display.to_html(escape=False, index=False, classes="news-table"),
        unsafe_allow_html=True,
    )

    # CSV download
    download_df = display_df[
        ["title", "media", "published", "language", "query",
         "desc", "full_text", "link", "sentiment", "summary"]
    ].copy().rename(columns={
        "title": "Title",
        "media": "Source",
        "published": "Published",
        "language": "Language",
        "query": "Matched Query",
        "desc": "Description",
        "full_text": "Article Body",
        "link": "URL",
        "sentiment": "Sentiment",
        "summary": "AI Summary",
    })

    csv_bytes = download_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 Download Results as CSV",
        data=csv_bytes,
        file_name=f"dharavi_news_{days}d_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="download-csv",
    )

    # ===================== Charts =====================
    st.subheader("Overall Tone Summary")

    counts = display_df["sentiment"].value_counts().reindex(
        ["Positive", "Neutral", "Negative", "Non"], fill_value=0
    )
    total_articles = len(display_df)

    metric_html = f"""
    <div class="metrics-container">
        <div class="metric-box metric-positive">
            <div class="metric-value">{int(counts['Positive'])}</div>
            <div class="metric-label">Positive (EN)</div>
        </div>
        <div class="metric-box metric-neutral">
            <div class="metric-value">{int(counts['Neutral'])}</div>
            <div class="metric-label">Neutral (EN)</div>
        </div>
        <div class="metric-box metric-negative">
            <div class="metric-value">{int(counts['Negative'])}</div>
            <div class="metric-label">Negative (EN)</div>
        </div>
        <div class="metric-box metric-non">
            <div class="metric-value">{int(counts['Non'])}</div>
            <div class="metric-label">Non (HI/MR)</div>
        </div>
        <div class="metric-box metric-total">
            <div class="metric-value">{int(total_articles)}</div>
            <div class="metric-label">Total Articles</div>
        </div>
    </div>
    """
    st.markdown(metric_html, unsafe_allow_html=True)

    pie_fig = px.pie(
        names=counts.index,
        values=counts.values,
        title="Overall Sentiment Distribution",
        hole=0.55,
    )
    pie_fig.update_traces(textinfo="percent")
    st.plotly_chart(pie_fig, use_container_width=True)

elif st.session_state.has_fetched:
    st.warning("No articles found for the selected filters.")
else:
    st.info("Select day range and click **Fetch News**.")
