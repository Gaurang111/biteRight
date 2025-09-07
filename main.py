import json
import streamlit as st
from source import reconcile
import tempfile
from source import decode_barcode_from_image
import pandas as pd
import ast
import re
from collections import Counter

@st.cache_data
def load_risk_csv(csv_path):
    df = pd.read_csv(csv_path)
    # Ensure Labels column becomes a list
    def parse_labels(x):
        try:
            return ast.literal_eval(x) if isinstance(x, str) else []
        except Exception:
            return []
    df["Labels"] = df["Labels"].apply(parse_labels)

    alias_map = {}
    for _, row in df.iterrows():
        cat = str(row["Category"]).strip()
        risk = str(row["Risk Level"]).strip()
        concern = str(row["Main Concern"]).strip()
        for label in row["Labels"]:
            if isinstance(label, str) and label.strip():
                alias_map[label.strip().lower()] = (cat, risk, concern)
    return alias_map, df



def normalize_token(s: str):
    # keep letters, numbers, spaces, plus/minus & parentheses content; drop commas/periods etc.
    s = re.sub(r"[\u2019']", "'", s)           # normalize apostrophes
    s = re.sub(r"[^0-9a-zA-Z\-\+\(\) %]", " ", s)  # remove most punctuation, keep () + -
    return re.sub(r"\s+", " ", s).strip().lower()

def main():
    st.markdown(
        "<h1 style='text-align: center;'>🥗 Bite Right</h1><br>",
        unsafe_allow_html=True)

    input_col1, input_col2 = st.columns(2)

    with input_col1:
        take_pic = st.button("📷 Take a picture", use_container_width=True)
    with input_col2:
        upload_pic = st.button("📂 Upload photo", use_container_width=True)

    # Remember choice in session state
    if "choice" not in st.session_state:
        st.session_state.choice = None

    if take_pic:
        st.session_state.choice = "camera"
    elif upload_pic:
        st.session_state.choice = "upload"

    file = None

    # Show input based on choice
    if st.session_state.choice == "camera":
        file = st.camera_input("")
    elif st.session_state.choice == "upload":
        file = st.file_uploader("", type=["png", "jpg", "jpeg"])

    if file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(file.getbuffer())
            tmp_path = tmp.name

        barcode_gtin = decode_barcode_from_image(tmp_path)
        data = reconcile(barcode_gtin)

        # ---------- images side by side ----------
        st.markdown("""
        <style>
        .img-container {
            width: 100%;
            height: 350px;            
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid #eee;   
            border-radius: 10px;
            overflow: hidden;         
            background: #fff;
        }
        .img-container img {
            height: 100%;            
            width: auto;              
            object-fit: cover;        
        }
        .caption {
            text-align:center;
            color:#666;
            font-size:0.9rem;
            margin-top:0.25rem;
        }
        </style>
        """, unsafe_allow_html=True)
        brand = data.get('brand') or None
        product = data.get('product_name') or None
        if brand or product:
            st.markdown(f"<h3 style='text-align: center;'>✨ {brand or ''} {product or ''} ✨</h3>",
                        unsafe_allow_html=True)

        c1, c2 = st.columns(2)

        with c1:
            img1 = data.get("image_front_url")
            if img1:
                st.markdown(
                    f"<div class='img-container'><img src='{img1}'></div>",
                    unsafe_allow_html=True)

        with c2:
            img2 = data.get("image_nutri_url")
            if img2:  # only render if not None/empty
                st.markdown(
                    f"<div class='img-container'><img src='{img2}'></div>",
                    unsafe_allow_html=True)

        # ---------- Ingredients ----------
        CSV = r"harmful_ingredients_risk_list.csv"

        RISK_COLORS = {
            "High": {"bg": "#FEE2E2", "border": "#991B1B", "text": "#991B1B"},  # red-ish
            "Moderate": {"bg": "#FEF3C7", "border": "#92400E", "text": "#92400E"},  # amber-ish
            "Low": {"bg": "#ECFDF5", "border": "#065F46", "text": "#065F46"},  # green-ish
            "Unknown": {"bg": "#F3F4F6", "border": "#E5E7EB", "text": "#374151"},  # gray
        }
        st.markdown("""
        <style>
        .pills { display:flex; flex-wrap:wrap; gap:10px; }
        .pill {
          display:inline-flex; align-items:center; gap:6px;
          padding:8px 12px; border-radius:9999px; border:1px solid transparent;
          font-size:0.95rem; font-weight:600; white-space:nowrap;
        }
        .legend { display:inline-flex; align-items:center; gap:26px; }
        .legend-item { display: inline-flex; align-items:center; gap:6px; }
        .legend-dot {
          width:14px; height:14px; border-radius:9999px; border:1px solid #e5e7eb;
        }
        .pill[data-risk="High"]     { background:%(High_bg)s;     border-color:%(High_border)s;     color:%(High_text)s; }
        .pill[data-risk="Moderate"] { background:%(Moderate_bg)s; border-color:%(Moderate_border)s; color:%(Moderate_text)s; }
        .pill[data-risk="Low"]      { background:%(Low_bg)s;      border-color:%(Low_border)s;      color:%(Low_text)s; }
        .pill[data-risk="Unknown"]  { background:%(Unknown_bg)s;  border-color:%(Unknown_border)s;  color:%(Unknown_text)s; }
        </style>
        """ % {
            "High_bg": RISK_COLORS["High"]["bg"], "High_border": RISK_COLORS["High"]["border"],
            "High_text": RISK_COLORS["High"]["text"],
            "Moderate_bg": RISK_COLORS["Moderate"]["bg"], "Moderate_border": RISK_COLORS["Moderate"]["border"],
            "Moderate_text": RISK_COLORS["Moderate"]["text"],
            "Low_bg": RISK_COLORS["Low"]["bg"], "Low_border": RISK_COLORS["Low"]["border"],
            "Low_text": RISK_COLORS["Low"]["text"],
            "Unknown_bg": RISK_COLORS["Unknown"]["bg"], "Unknown_border": RISK_COLORS["Unknown"]["border"],
            "Unknown_text": RISK_COLORS["Unknown"]["text"],
        }, unsafe_allow_html=True)

        alias_map, df_risk = load_risk_csv(CSV)

        ingredients_text = (data.get("ingredients_text") or "").strip()

        tokens_raw = [t.strip() for t in re.split(r"[;,]", ingredients_text) if t.strip()]
        tokens_norm = [normalize_token(t) for t in tokens_raw]

        def match_token(token_norm):
            # exact label match
            if token_norm in alias_map:
                return alias_map[token_norm]
            # contains match (alias in token), prefer longest alias to avoid partials
            for alias in sorted(alias_map.keys(), key=len, reverse=True):
                if alias in token_norm:
                    return alias_map[alias]
            return ("—", "Unknown", "Not in risk list")

        matched = []
        for raw, norm in zip(tokens_raw, tokens_norm):
            cat, risk, concern = match_token(norm)
            matched.append({
                "display": raw.strip(),
                "category": cat,
                "risk": risk,
                "concern": concern
            })

        # ---------- RENDER ----------

        st.markdown("<h3 style='text-align: center;'> 🌿 Ingredients 🌿 </h3>",
                    unsafe_allow_html=True)
        pills_html = "<div class='pills'>"
        for item in matched:
            title = f"Category: {item['category']} • Concern: {item['concern']}"
            pills_html += f"<span class='pill' data-risk='{item['risk']}' title='{title}'>{item['display']}</span>"
        pills_html += "</div><br>"
        st.markdown(pills_html, unsafe_allow_html=True)
        risk_counts = Counter(item["risk"] for item in matched)
        for lvl in ["High", "Moderate", "Low", "Unknown"]:
            risk_counts.setdefault(lvl, 0)

        RISK_EMOJIS = {
            "High": "☠️",
            "Moderate": "🚨",
            "Low": "⚠️",
            "Unknown": "❓"
        }
        summary_html = "<div class='pills'>"
        for lvl in ["High", "Moderate", "Low"]:
            emoji = RISK_EMOJIS.get(lvl, "")
            summary_html += f"<span class='pill' data-risk='{lvl}'>{emoji} {lvl} Risk: {risk_counts[lvl]}</span>"
        summary_html += "</div><br>"
        st.markdown(summary_html, unsafe_allow_html=True)

        # -------------------------------------------------------------------------------------------------------------

        st.markdown("<h3 style='text-align: center;'> ⚡ Macros & Micros ⚡ </h3>",
                    unsafe_allow_html=True)

        def get_serving(nutriments, key_base, fallback_unit=""):
            val = nutriments.get(f"{key_base}_serving")
            unit = nutriments.get(f"{key_base}_unit", fallback_unit)
            if val is None:
                return None, unit
            try:
                val = round(val, 2)
            except Exception:
                pass
            return val, unit

        def tile(label, value, unit="", kind="macro"):
            klass = "tile-macro" if kind == "macro" else "tile-micro"
            value_s = "-" if value is None else value
            unit_s = f" {unit}" if unit and value is not None else ""
            return f"""<div class="tile {klass}"><div class="tile-label">{label}</div>
                        <div class="tile-value">{value_s}{unit_s}</div></div>"""

        MACRO_KEYS = {
            "energy-kcal": ("Energy", "kcal"),
            "carbohydrates": ("Carbs", "g"),
            "sugars": ("Sugars", "g"),
            "added-sugars": ("Added sugars", "g"),
            "proteins": ("Protein", "g"),
            "fat": ("Fat", "g"),
            "saturated-fat": ("Sat. Fat", "g"),
            "fiber": ("Fiber", "g"),
            "sodium": ("Sodium", "g"),
        }

        MICRO_KEYS = {
            "potassium": ("Potassium", "mg"),
            "magnesium": ("Magnesium", "mg"),
            "calcium": ("Calcium", "mg"),
            "phosphorus": ("Phosphorus", "mg"),
            "iron": ("Iron", "mg"),
            "zinc": ("Zinc", "mg"),
            "iodine": ("Iodine", "µg"),
            "selenium": ("Selenium", "µg"),
            "copper": ("Copper", "mg"),
            "manganese": ("Manganese", "mg"),
            "vitamin-a": ("Vitamin A", "µg"),
            "vitamin-d": ("Vitamin D", "µg"),
            "vitamin-e": ("Vitamin E", "mg"),
            "vitamin-k": ("Vitamin K", "µg"),
            "vitamin-c": ("Vitamin C", "mg"),
            "vitamin-b1": ("Vitamin B1 (Thiamin)", "mg"),
            "vitamin-b2": ("Vitamin B2 (Riboflavin)", "mg"),
            "vitamin-b3": ("Vitamin B3 (Niacin)", "mg"),
            "vitamin-b6": ("Vitamin B6", "mg"),
            "vitamin-b12": ("Vitamin B12", "µg"),
            "folates": ("Folate", "µg"),
            "choline": ("Choline", "mg"),
        }

        st.markdown("""
                    <style>
                    .section-title { font-weight:700; font-size:1.05rem; margin: 0.75rem 0 0.5rem 0; }
            
                    .serving-banner {
                      display:flex; align-items:center; justify-content:center;
                      padding:10px 14px; border-radius:12px; border:1px solid #C8E6C9;
                      background:#E8F5E9; color:#1B5E20; font-weight:700;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                    }
            
                    .tiles {
                      display: grid;
                      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                      gap: 12px;
                    }

                    .tile {
                      border-radius: 14px;
                      padding: 12px;
                      background: #ffffff;
                      border: 1px solid #e5e7eb;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
                    }
                    .tile-label { color:#374151; font-size:0.9rem; margin-bottom:6px; font-weight:600; }
                    .tile-value { font-size:1.15rem; font-weight:800; color:#111827; }
            
                    .tile-macro {
                      background: #F0F9FF;           /* light blue */
                      border-color: #93C5FD;         /* blue border */
                    }
                    .tile-micro {
                      background: #FFF7ED;           /* light orange/peach */
                      border-color: #FDBA74;         /* orange border */
                    }
            
                    </style>
                    """, unsafe_allow_html=True)

        nut = data.get("nutriments", {})

        serving = data.get("serving_size", "-")
        st.markdown("<div class='section-title'>🥄 Serving Size</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='serving-banner'>{serving}</div>", unsafe_allow_html=True)

        # ---------- 5 Macros ----------
        st.markdown("<div class='section-title'>⚡ Macros (per serving)</div>", unsafe_allow_html=True)
        macro_tiles = []
        for key, (label, default_unit) in MACRO_KEYS.items():
            val, unit = get_serving(nut, key, default_unit)
            if val is not None:
                macro_tiles.append(tile(label, val, unit, kind="macro"))

        st.markdown(f"<div class='tiles'>{''.join(macro_tiles) if macro_tiles else '<em>No macro data</em>'} </div>",
                    unsafe_allow_html=True)

        # ---- Micros (show all available from MICRO_KEYS) ----
        st.markdown("<div class='section-title'>💊 Micros (per serving)</div>", unsafe_allow_html=True)
        micro_tiles = []
        for key, (label, default_unit) in MICRO_KEYS.items():
            val, unit = get_serving(nut, key, default_unit)
            if val is not None:
                micro_tiles.append(tile(label, val, unit, kind="micro"))

        st.markdown(f"<div class='tiles'>{''.join(micro_tiles) if micro_tiles else '<em>No micro data</em>'}</div>",
                    unsafe_allow_html=True)


if __name__ == "__main__":
    main()