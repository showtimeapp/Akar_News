# import streamlit as st
# from GoogleNews import GoogleNews
# import pandas as pd
# from textblob import TextBlob
# from datetime import datetime, timedelta
# import nltk
# import plotly.express as px
# import plotly.graph_objects as go
# import io
# import re
# import time
# import random

# nltk.download("punkt")

# st.set_page_config(page_title="Akar News Search & Analysis", layout="wide")

# # ===================== Custom CSS =====================
# st.markdown(
#     """
#     <style>
#     .news-table {
#         font-family: 'Segoe UI', sans-serif;
#         border-collapse: collapse;
#         width: 100%;
#     }
#     .news-table td, .news-table th {
#         border: 1px solid #ddd;
#         padding: 8px;
#         vertical-align: top;
#     }
#     .news-table tr:nth-child(even) { background-color: #f2f2f2; }
#     .news-table tr:hover { background-color: #ddd; }
#     .news-table th {
#         padding-top: 12px;
#         padding-bottom: 12px;
#         text-align: left;
#         background-color: #4CAF50;
#         color: white;
#     }
#     .metrics-container {
#         display: flex;
#         justify-content: space-between;
#         margin-bottom: 20px;
#         gap: 15px;
#         flex-wrap: wrap;
#     }
#     .metric-box {
#         flex: 1;
#         min-width: 160px;
#         padding: 15px 20px;
#         border-radius: 8px;
#         box-shadow: 0 4px 6px rgba(0,0,0,0.1);
#         text-align: center;
#         color: white;
#     }
#     .metric-positive { background: linear-gradient(135deg, #4CAF50, #2E7D32); }
#     .metric-neutral  { background: linear-gradient(135deg, #78909C, #455A64); }
#     .metric-negative { background: linear-gradient(135deg, #F44336, #C62828); }
#     .metric-non      { background: linear-gradient(135deg, #607D8B, #37474F); }
#     .metric-total    { background: linear-gradient(135deg, #3F51B5, #1A237E); }
#     .metric-value { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
#     .metric-label { font-size: 14px; opacity: 0.9; }
#     </style>
# """,
#     unsafe_allow_html=True,
# )

# st.markdown(
#     """
#     <h2 style='text-align:center;color:#fff;background:#262730;padding:10px;border-radius:10px;'>
#     📰 Akar's News Search and Analysis Portal
#     </h2>
# """,
#     unsafe_allow_html=True,
# )

# # ===================== Fixed Queries =====================
# FIXED_QUERIES = [
#     "Dharavi",
#     "Dharavi redevelopment project",
#     "Dharavi slum",
#     # //"Dharavi redevelopment",
#     # //"Dharavi slum redevelopment",
#     "DRP",
#     "Navbharat Mega Developers",
#     "NMDPL",
#     # //"NMDPL Dharavi",
#     "Dharavi Slum Rehabilitation Authority",
#     # //"Maharashtra Slum Areas (Improvement, Clearance & Redevelopment) Act",
#     "Devendra Fadnavis Dharavi",
#     "Eknath Shinde Dharavi",
#     # //"Housing allocation Dharavi",
#     "Bombay High Court Dharavi",
#     "eviction Dharavi redevelopment",
#     # //"Mithi River salt pan land Dharavi",
#     # //"Mumbai Urban Development",
#     "Dharavi survey",
#     "Dharavi SRA",
#     "Varsha Gaikwad Dharavi",
#     "Jyoti Gaikwad Dharavi",
#     "Rahul Shewale Dharavi",
#     "Bhaskar Shetty Dharavi"
# ]

# LANGS = [("English", "en"), ("Marathi", "mr")]
# REGION = "IN"

# # ===================== Session State =====================
# if "all_results" not in st.session_state:
#     st.session_state.all_results = []
# if "seen_keys" not in st.session_state:
#     st.session_state.seen_keys = set()
# if "df" not in st.session_state:
#     st.session_state.df = pd.DataFrame()
# if "sources_list" not in st.session_state:
#     st.session_state.sources_list = []
# if "selected_sources" not in st.session_state:
#     st.session_state.selected_sources = []
# if "has_fetched" not in st.session_state:
#     st.session_state.has_fetched = False


# # ===================== Helpers =====================
# def clean_url(url: str) -> str:
#     if not url:
#         return ""
#     url = url.replace("%3F", "?").replace("%3D", "=").replace("%26", "&")
#     if "&ved=" in url:
#         url = url.split("&ved=")[0]
#     return url


# DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# def to_ascii_digits(s: str) -> str:
#     return s.translate(DEVANAGARI_DIGITS)

# def parse_relative_datetime(date_str: str):
#     """
#     Parses the EXACT formats you showed (EN/MR/HI):
#     English:
#       - '4 days ago', '2 weeks ago', '1 month ago'
#     Marathi:
#       - '३ तासांपूर्वी', '४ दिवसांपूर्वी', '२ आठवड्यांपूर्वी'
#     Hindi:
#       - '3 हफ़्ते पहले', '1 महीने पहले', '2 महीने पहले'
#     Returns datetime or None.
#     """
#     if not date_str:
#         return None

#     raw = str(date_str).strip()
#     s = to_ascii_digits(raw).strip().lower()
#     now = datetime.now()

#     # ---------- English: X minute/hour/day/week/month ago ----------
#     m = re.search(r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months)\s+ago", s)
#     if m:
#         n = int(m.group(1))
#         unit = m.group(2)
#         if "minute" in unit:
#             return now - timedelta(minutes=n)
#         if "hour" in unit:
#             return now - timedelta(hours=n)
#         if "day" in unit:
#             return now - timedelta(days=n)
#         if "week" in unit:
#             return now - timedelta(days=7 * n)
#         if "month" in unit:
#             return now - timedelta(days=30 * n)  # approximation; OK for filtering 2 days
#         return None

#     # ---------- Marathi: '...पूर्वी' ----------
#     # Examples:
#     # '३ तासांपूर्वी' => hours
#     # '४ दिवसांपूर्वी' => days
#     # '२ आठवड्यांपूर्वी' => weeks
#     # '१ महिन्यापूर्वी' (sometimes) => months
#     if "पूर्वी" in s:
#         nums = re.findall(r"\d+", s)
#         if nums:
#             n = int(nums[0])
#             if "मिनिट" in s:
#                 return now - timedelta(minutes=n)
#             if "तास" in s:
#                 return now - timedelta(hours=n)
#             if "दिवस" in s:
#                 return now - timedelta(days=n)
#             if "आठवड" in s:
#                 return now - timedelta(days=7 * n)
#             if "महिन" in s:
#                 return now - timedelta(days=30 * n)
#         return None

#     # ---------- Hindi: '... पहले' ----------
#     # Examples:
#     # '3 हफ़्ते पहले' => weeks
#     # '1 महीने पहले' => months
#     # '2 दिन पहले' => days
#     if "पहले" in s:
#         nums = re.findall(r"\d+", s)
#         if nums:
#             n = int(nums[0])
#             if "मिनट" in s:
#                 return now - timedelta(minutes=n)
#             if "घंट" in s:
#                 return now - timedelta(hours=n)
#             if "दिन" in s:
#                 return now - timedelta(days=n)
#             if "हफ्त" in s or "हफ़्त" in s:
#                 return now - timedelta(days=7 * n)
#             if "मही" in s:
#                 return now - timedelta(days=30 * n)
#         return None

#     # Some sources show 'Yesterday' variants; keep minimal:
#     if s in ["yesterday", "काल", "कल"]:
#         return now - timedelta(days=1)

#     return None


# def reset_state():
#     st.session_state.all_results = []
#     st.session_state.seen_keys = set()
#     st.session_state.df = pd.DataFrame()
#     st.session_state.sources_list = []
#     st.session_state.selected_sources = []
#     st.session_state.has_fetched = False


# def add_results(results: list[dict], query: str, lang_label: str):
#     for r in results:
#         title = (r.get("title") or "").strip()
#         link = clean_url((r.get("link") or "").strip())
#         media = (r.get("media") or "").strip()
#         date_str = (r.get("date") or "").strip()
#         desc = (r.get("desc") or "").strip()

#         key = f"{title}||{media}||{link}"
#         if not title or key in st.session_state.seen_keys:
#             continue
#         st.session_state.seen_keys.add(key)

#         st.session_state.all_results.append(
#             {
#                 "title": title,
#                 "media": media,
#                 "date_raw": date_str,
#                 "desc": desc,
#                 "link": link,
#                 "query": query,
#                 "language": lang_label,
#             }
#         )

#         if media and media not in st.session_state.sources_list:
#             st.session_state.sources_list.append(media)


# def fetch_query_one_page(query: str, lang_code: str, lang_label: str):
#     gn = GoogleNews(lang=lang_code, region=REGION)
#     gn.set_period("30d")   # broad, final filter is strict 2 days
#     gn.search(query)
#     gn.get_page(1)         # ONLY ONE PAGE per query per language
#     results = gn.results() or []
#     add_results(results, query=query, lang_label=lang_label)


# # ===================== UI =====================
# st.subheader("Fixed Search Filters")

# colA, colB = st.columns([3, 2])
# with colA:
#     st.info(
#         "Runs 19 fixed queries × 3 languages (EN/MR/HI), ONLY page-1 each.\n"
#         "Then: parses relative publication time (days/hours/weeks/months) and STRICTLY filters LAST 2 DAYS."
#     )
# with colB:
#     if st.button("♻️ Reset"):
#         reset_state()
#         st.rerun()

# run_btn = st.button("🚀 Fetch News (Strict last 2 days)")

# # ===================== Fetch Runner =====================
# if run_btn:
#     reset_state()
#     st.session_state.has_fetched = True

#     total_steps = len(FIXED_QUERIES) * len(LANGS)
#     progress = st.progress(0)
#     status = st.empty()

#     step = 0
#     with st.spinner("Fetching news across all queries & languages..."):
#         for q in FIXED_QUERIES:
#             for (lang_label, lang_code) in LANGS:
#                 step += 1
#                 status.write(f"🔎 [{step}/{total_steps}] {lang_label}: {q}")
#                 try:
#                     fetch_query_one_page(q, lang_code=lang_code, lang_label=lang_label)
#                 except Exception as e:
#                     st.warning(f"Failed for '{q}' ({lang_label}): {e}")
#                 progress.progress(step / total_steps)
#                 time.sleep(random.uniform(10, 14))

#     st.session_state.df = pd.DataFrame(st.session_state.all_results)
#     if not st.session_state.df.empty:
#         st.session_state.df = st.session_state.df.drop_duplicates(subset=["title", "media", "link"])


# # ===================== Display =====================
# if not st.session_state.df.empty:

#     # Parse relative times to datetime (ONLY from date_raw)
#     st.session_state.df["Published_dt"] = st.session_state.df["date_raw"].apply(parse_relative_datetime)

#     # STRICT last 2 days (anything unparsed -> dropped)
#     cutoff = datetime.now() - timedelta(days=2)
#     display_df = st.session_state.df.copy()
#     display_df = display_df[
#         display_df["Published_dt"].notna() &
#         (display_df["Published_dt"] >= cutoff)
#     ].copy()

#     # English formatted date
#     display_df["Published Date (EN)"] = display_df["Published_dt"].dt.strftime("%d %b %Y %H:%M")

#     # Source filter
#     st.subheader("Filter by Source")
#     st.session_state.selected_sources = st.multiselect(
#         "Select news sources to display",
#         options=sorted(st.session_state.sources_list),
#         default=[],
#     )
#     if st.session_state.selected_sources:
#         display_df = display_df[display_df["media"].isin(st.session_state.selected_sources)].copy()

#     # Sentiment:
#     # English -> TextBlob
#     # Marathi/Hindi -> "Non"
#     display_df["polarity"] = None
#     display_df["sentiment"] = "Non"

#     mask_en = display_df["language"].eq("English")
#     display_df.loc[mask_en, "polarity"] = display_df.loc[mask_en, "desc"].fillna("").astype(str).apply(
#         lambda x: TextBlob(x).sentiment.polarity
#     )
#     display_df.loc[mask_en, "sentiment"] = display_df.loc[mask_en, "polarity"].apply(
#         lambda x: "Positive" if x > 0 else ("Negative" if x < 0 else "Neutral")
#     )

#     sentiment_colors = {"Positive": "green", "Negative": "red", "Neutral": "gray", "Non": "#607D8B"}

#     st.success(f"Showing {len(display_df)} articles (STRICT last 2 days).")

#     # Table
#     df_display = display_df[
#         ["title", "media", "Published Date (EN)", "date_raw", "language", "query", "desc", "link", "sentiment"]
#     ].copy()

#     df_display["Sentiment"] = df_display["sentiment"].apply(
#         lambda x: f"<span style='color:{sentiment_colors.get(x, 'black')}'>{x}</span>"
#     )
#     df_display["Title"] = df_display.apply(
#         lambda row: f"<a href='{row['link']}' target='_blank'>{row['title']}</a>", axis=1
#     )

#     df_display = df_display.rename(
#         columns={
#             "media": "Source",
#             "language": "Language",
#             "query": "Matched Query",
#             "desc": "Description",
#             "date_raw": "Original Published Text",
#         }
#     )

#     df_display = df_display[
#         ["Title", "Source", "Published Date (EN)", "Original Published Text", "Language", "Matched Query", "Description", "Sentiment"]
#     ]

#     st.subheader("Search Results (All-in-One • Strict last 2 days)")
#     st.markdown(df_display.to_html(escape=False, index=False, classes="news-table"), unsafe_allow_html=True)

#     # Excel download
#     download_df = display_df[
#         ["title", "media", "Published Date (EN)", "date_raw", "language", "query", "desc", "link", "sentiment"]
#     ].copy()

#     download_df = download_df.rename(
#         columns={
#             "title": "Title",
#             "media": "Source",
#             "language": "Language",
#             "query": "Matched Query",
#             "desc": "Description",
#             "link": "URL",
#             "sentiment": "Sentiment",
#             "date_raw": "Original Published Text",
#         }
#     )

#     excel_buffer = io.BytesIO()
#     with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
#         download_df.to_excel(writer, sheet_name="News Data", index=False)

#     st.download_button(
#         label="📥 Download Results as Excel",
#         data=excel_buffer.getvalue(),
#         file_name=f"dharavi_news_last_2_days_{datetime.now().strftime('%Y%m%d')}.xlsx",
#         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#         key="download-excel",
#     )

#     # Charts
#     st.subheader("Overall Tone Summary")
#     counts = display_df["sentiment"].value_counts().reindex(["Positive", "Neutral", "Negative", "Non"], fill_value=0)
#     total_articles = len(display_df)

#     metric_html = f"""
#     <div class="metrics-container">
#         <div class="metric-box metric-positive">
#             <div class="metric-value">{counts['Positive']}</div>
#             <div class="metric-label">Positive (EN)</div>
#         </div>
#         <div class="metric-box metric-neutral">
#             <div class="metric-value">{counts['Neutral']}</div>
#             <div class="metric-label">Neutral (EN)</div>
#         </div>
#         <div class="metric-box metric-negative">
#             <div class="metric-value">{counts['Negative']}</div>
#             <div class="metric-label">Negative (EN)</div>
#         </div>
#         <div class="metric-box metric-non">
#             <div class="metric-value">{counts['Non']}</div>
#             <div class="metric-label">Non (MR/HI)</div>
#         </div>
#         <div class="metric-box metric-total">
#             <div class="metric-value">{total_articles}</div>
#             <div class="metric-label">Total Articles</div>
#         </div>
#     </div>
#     """
#     st.markdown(metric_html, unsafe_allow_html=True)

#     pie_fig = px.pie(
#         names=counts.index,
#         values=counts.values,
#         title="Overall Sentiment Distribution",
#         hole=0.4,
#     )
#     st.plotly_chart(pie_fig, use_container_width=True)

# elif st.session_state.has_fetched:
#     st.warning("No articles found after STRICT last 2 days filter.")



import time
from datetime import datetime
import pandas as pd
import streamlit as st
from gnews import GNews
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import plotly.express as px

# Optional: Improve description by scraping the article
try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except Exception:
    NEWSPAPER_AVAILABLE = False


# --------------------------
# FIXED SETTINGS
# --------------------------
COUNTRY = "IN"
LANGUAGES = [("en", "English"), ("hi", "Hindi"), ("mr", "Marathi")]

FIXED_QUERIES = [
    "Dharavi",
    "Dharavi redevelopment project",
    "Dharavi slum",
    "DRP",
    "Navbharat Mega Developers",
    "NMDPL",
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
    "Bhaskar Shetty Dharavi"
]


# --------------------------
# Sentiment Model (Multilingual)
# --------------------------
# Model: CardiffNLP XLM-R sentiment (3-class)
MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

LABEL_MAP = {
    "LABEL_0": "Negative",
    "LABEL_1": "Neutral",
    "LABEL_2": "Positive",
}

@st.cache_resource
def load_sentiment_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()
    return tokenizer, model

def predict_sentiment(text: str, tokenizer, model) -> str:
    if not text or not text.strip():
        return "Neutral"

    # truncate long texts safely
    inputs = tokenizer(
        text.strip(),
        return_tensors="pt",
        truncation=True,
        max_length=256
    )

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]
        label_id = int(torch.argmax(probs).item())
        label = f"LABEL_{label_id}"
        return LABEL_MAP.get(label, "Neutral")


# --------------------------
# Helpers
# --------------------------
def safe_str(x):
    return "" if x is None else str(x)

def normalize_publisher(pub):
    # gnews sometimes returns dict: {"title": "...", "href": "..."}
    if isinstance(pub, dict):
        return pub.get("title") or pub.get("name") or ""
    return safe_str(pub)

def try_fetch_better_description(url: str) -> str:
    """
    If title==description (or description empty), attempt to scrape article and use:
    - meta description OR first ~2 paragraphs
    """
    if not NEWSPAPER_AVAILABLE or not url:
        return ""

    try:
        a = Article(url)
        a.download()
        a.parse()
        # a.nlp() can be heavy; we avoid it.

        text = (a.text or "").strip()
        if not text:
            return ""

        # Take first ~80-120 words as a decent "extended description"
        words = text.split()
        if len(words) <= 120:
            return " ".join(words)
        return " ".join(words[:120]) + "…"
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def fetch_news_for_queries(days: int, max_results_per_query: int = 10):
    """
    Fetch news for all FIXED_QUERIES across fixed languages, fixed country,
    for past N days.
    """
    period = f"{days}d"

    rows = []
    for lang_code, lang_name in LANGUAGES:
        gn = GNews(
            language=lang_code,
            country=COUNTRY,
            period=period,
            max_results=max_results_per_query
        )

        for q in FIXED_QUERIES:
            results = gn.get_news(q) or []
            for item in results:
                rows.append({
                    "query": q,
                    "language": lang_name,
                    "lang_code": lang_code,
                    "title": safe_str(item.get("title")),
                    "description": safe_str(item.get("description")),
                    "published_date": safe_str(item.get("published date")),
                    "publisher": normalize_publisher(item.get("publisher")),
                    "url": safe_str(item.get("url")),
                })

            # tiny pause reduces chance of throttling
            time.sleep(0.2)

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # Deduplicate same story across queries/languages
    df = df.drop_duplicates(subset=["url", "title"], keep="first").reset_index(drop=True)
    return df


def build_summary_cards(df: pd.DataFrame):
    counts = df["sentiment"].value_counts().to_dict()
    pos = int(counts.get("Positive", 0))
    neu = int(counts.get("Neutral", 0))
    neg = int(counts.get("Negative", 0))
    total = int(len(df))
    return pos, neu, neg, total


def donut_chart(df: pd.DataFrame):
    counts = df["sentiment"].value_counts().reindex(["Neutral", "Positive", "Negative"]).fillna(0).astype(int)
    chart_df = pd.DataFrame({
        "Sentiment": counts.index,
        "Count": counts.values
    })

    fig = px.pie(
        chart_df,
        names="Sentiment",
        values="Count",
        hole=0.55
    )
    fig.update_traces(textinfo="percent")
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend_title_text=""
    )
    return fig


# --------------------------
# UI
# --------------------------
st.set_page_config(page_title="Dharavi News Sentiment Dashboard", layout="wide")

st.title("Dharavi News Sentiment Dashboard")
st.caption("Country fixed: India | Languages fixed: English, Hindi, Marathi | Queries fixed (DRP ecosystem)")

with st.sidebar:
    st.header("Controls")
    day_range = st.slider("Past day range", min_value=1, max_value=30, value=2, step=1)
    max_results = st.slider("Max results per query (per language)", min_value=5, max_value=30, value=10, step=5)

    scrape_desc = st.toggle(
        "Improve description (scrape article)",
        value=True,
        help="If title and description look same, this tries to fetch a better summary from the article."
    )

    run_btn = st.button("Fetch News", type="primary")


if run_btn:
    with st.spinner("Fetching news..."):
        df = fetch_news_for_queries(day_range, max_results_per_query=max_results)

    if df.empty:
        st.warning("No news found for the selected day range.")
        st.stop()

    # Fix description if same as title / empty
    if scrape_desc:
        with st.spinner("Improving descriptions (where needed)..."):
            improved = []
            for _, row in df.iterrows():
                title = (row["title"] or "").strip()
                desc = (row["description"] or "").strip()
                url = row["url"]

                # if description missing or identical to title, try scraping
                if not desc or desc.lower() == title.lower():
                    better = try_fetch_better_description(url)
                    improved.append(better if better else desc)
                else:
                    improved.append(desc)

            df["description"] = improved

    # Sentiment
    with st.spinner("Running sentiment analysis (English/Hindi/Marathi)..."):
        tokenizer, model = load_sentiment_model()
        # Use title + description for better signal
        df["sentiment_text"] = (df["title"].fillna("") + ". " + df["description"].fillna("")).str.strip()
        df["sentiment"] = df["sentiment_text"].apply(lambda t: predict_sentiment(t, tokenizer, model))

    # --------------------------
    # Summary + Visualization (like your screenshot)
    # --------------------------
    st.subheader("Overall Tone Summary")

    pos, neu, neg, total = build_summary_cards(df)

    # Simple CSS cards
    st.markdown(
        """
        <style>
        .tone-card {
            border-radius: 12px;
            padding: 18px 18px;
            color: white;
            font-weight: 700;
            box-shadow: 0 6px 16px rgba(0,0,0,0.12);
            height: 92px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .tone-card .num { font-size: 28px; line-height: 30px; }
        .tone-card .lbl { font-size: 13px; opacity: 0.95; margin-top: 6px; font-weight: 600; }
        .green { background: linear-gradient(90deg, #2e7d32, #43a047); }
        .gray  { background: linear-gradient(90deg, #546e7a, #607d8b); }
        .red   { background: linear-gradient(90deg, #c62828, #e53935); }
        .blue  { background: linear-gradient(90deg, #283593, #3949ab); }
        </style>
        """,
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"""<div class="tone-card green"><div class="num">{pos}</div><div class="lbl">Positive</div></div>""", unsafe_allow_html=True)
    c2.markdown(f"""<div class="tone-card gray"><div class="num">{neu}</div><div class="lbl">Neutral</div></div>""", unsafe_allow_html=True)
    c3.markdown(f"""<div class="tone-card red"><div class="num">{neg}</div><div class="lbl">Negative</div></div>""", unsafe_allow_html=True)
    c4.markdown(f"""<div class="tone-card blue"><div class="num">{total}</div><div class="lbl">Total Articles</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Overall Sentiment Distribution")

    left, right = st.columns([2, 1])
    with left:
        st.plotly_chart(donut_chart(df), use_container_width=True)
    with right:
        st.write("**Legend**")
        st.write("- Neutral")
        st.write("- Positive")
        st.write("- Negative")

    st.markdown("---")

    # --------------------------
    # Table + Export
    # --------------------------
    st.subheader("News Articles")

    show_cols = ["published_date", "language", "query", "publisher", "title", "description", "sentiment", "url"]
    st.dataframe(df[show_cols], use_container_width=True, height=420)

    # Export CSV
    csv_bytes = df[show_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ Export to CSV",
        data=csv_bytes,
        file_name=f"dharavi_news_{day_range}d_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        type="primary"
    )

else:
    st.info("Select day range and click **Fetch News**.")
