import anthropic
import streamlit as st
import streamlit.components.v1 as components
import base64
import io
import json
import os
import tempfile
from datetime import datetime
from PIL import Image
from fpdf import FPDF

# ── Supabase setup (gracefully disabled if not configured) ──
DB_ENABLED = False
db = None
try:
    from supabase import create_client
    _sb_url = st.secrets["SUPABASE_URL"]
    _sb_key = st.secrets["SUPABASE_KEY"]
    db = create_client(_sb_url, _sb_key)
    DB_ENABLED = True
except Exception:
    pass

# ── Cookie manager for persistent sign-in ──
_cookie_mgr = None
try:
    import extra_streamlit_components as stx
    _cookie_mgr = stx.CookieManager(key="hh_auth_cookies")
except Exception:
    pass

def _get_cookie(name):
    try:
        return _cookie_mgr.get(name) if _cookie_mgr else None
    except: return None

def _set_cookie(name, value, days=30):
    try:
        if _cookie_mgr:
            expires = datetime.now().replace(
                year=datetime.now().year + (1 if datetime.now().month > 11 else 0),
                month=(datetime.now().month % 12) + (0 if datetime.now().month < 12 else -11)
            )
            _cookie_mgr.set(name, value, expires_at=expires)
    except: pass

def _del_cookie(name):
    try:
        if _cookie_mgr: _cookie_mgr.delete(name)
    except: pass

# ── Auth helper functions ──
def _restore_session():
    """Restore Supabase auth session — first from session_state, then from cookie."""
    if not DB_ENABLED:
        return
    # Fast path — session state already has tokens from this browser session
    if "sb_access_token" in st.session_state:
        try:
            db.auth.set_session(
                st.session_state.sb_access_token,
                st.session_state.sb_refresh_token
            )
            return
        except Exception:
            for k in ["sb_access_token","sb_refresh_token","sb_user_id","sb_user_email","sb_current_session"]:
                st.session_state.pop(k, None)
    # Slow path — try to restore from persistent cookie (survives page reload / app restart)
    if "sb_user_email" not in st.session_state:
        refresh_token = _get_cookie("hh_rt")
        if refresh_token:
            try:
                res = db.auth.refresh_session(refresh_token)
                st.session_state.sb_access_token  = res.session.access_token
                st.session_state.sb_refresh_token = res.session.refresh_token
                st.session_state.sb_user_id       = res.user.id
                st.session_state.sb_user_email    = res.user.email
                _set_cookie("hh_rt", res.session.refresh_token)
            except Exception:
                _del_cookie("hh_rt")

def get_user():
    if not DB_ENABLED or "sb_user_email" not in st.session_state:
        return None
    return {"id": st.session_state.sb_user_id, "email": st.session_state.sb_user_email}

def do_sign_in(email, password):
    res = db.auth.sign_in_with_password({"email": email.strip(), "password": password})
    st.session_state.sb_access_token  = res.session.access_token
    st.session_state.sb_refresh_token = res.session.refresh_token
    st.session_state.sb_user_id       = res.user.id
    st.session_state.sb_user_email    = res.user.email
    _set_cookie("hh_rt", res.session.refresh_token, days=30)
    return True

def do_sign_up(email, password):
    res = db.auth.sign_up({"email": email.strip(), "password": password})
    return res

def do_sign_out():
    if db:
        try: db.auth.sign_out()
        except: pass
    _del_cookie("hh_rt")
    st.session_state["sb_did_sign_out"] = True
    for k in ["sb_access_token","sb_refresh_token","sb_user_id","sb_user_email",
              "sb_current_session","sb_auth_mode"]:
        st.session_state.pop(k, None)

# ── Chat persistence helpers ──
def start_chat_session(first_message):
    user = get_user()
    if not user: return None
    try:
        title = first_message[:60] if first_message else "Conversation"
        res = db.table("chat_sessions").insert({
            "user_id": user["id"], "title": title
        }).execute()
        return res.data[0]["id"] if res.data else None
    except: return None

def save_message(session_id, role, content):
    if not session_id: return
    try:
        text = content if isinstance(content, str) else \
               " ".join(b.get("text","") for b in content if isinstance(b, dict) and b.get("type")=="text")
        db.table("chat_messages").insert({
            "session_id": session_id, "role": role, "content": text
        }).execute()
    except: pass

def load_history():
    user = get_user()
    if not user: return []
    try:
        res = db.table("chat_sessions").select("*") \
                .order("updated_at", desc=True).limit(30).execute()
        return res.data or []
    except: return []

def load_session_msgs(session_id):
    try:
        res = db.table("chat_messages").select("*") \
                .eq("session_id", session_id).order("created_at").execute()
        return [{"role": m["role"], "content": m["content"]} for m in (res.data or [])]
    except: return []

def delete_session(session_id):
    try:
        db.table("chat_sessions").delete().eq("id", session_id).execute()
    except: pass

_restore_session()

# ── Cookie manager timing fix ──
# extra-streamlit-components needs one render cycle to initialize before
# cookies are readable. If the user isn't signed in after the first restore
# attempt, trigger one silent rerun so the cookie can load properly.
# The flag prevents an infinite rerun loop — only fires once per app load.
if not get_user() and DB_ENABLED and _cookie_mgr is not None:
    if not st.session_state.get("_cookie_rerun_done"):
        st.session_state["_cookie_rerun_done"] = True
        st.rerun()
if get_user():
    st.session_state.pop("_cookie_rerun_done", None)


st.set_page_config(
    page_title="Handy Helper - DIY Services Assistant",
    page_icon="🔧",
    layout="wide"
)

st.markdown("""
    <style>
        #MainMenu { visibility: hidden; }
        header { visibility: hidden; }
        footer { visibility: hidden; }
        [data-testid="stToolbar"] { display: none; }
        [data-testid="stDecoration"] { display: none; }
        [data-testid="stBottom"] { display: none !important; }
        [data-testid="stBottomBlockContainer"] { display: none !important; }

        /* ── HORIZONTAL CENTERING — confirmed working ── */
        html, body {
            background: #1A1612 !important;
        }
        .block-container {
            padding: 0.5rem 0.75rem !important;
            max-width: 560px !important;
            margin: 0 auto !important;
        }

        [data-testid="stFileUploader"] label { display: none !important; }

        /* ── CRITICAL: Streamlit auto-stacks columns under 640px screen width.
           This is pure CSS (not JS) so it reliably applies — it forces columns
           to stay side-by-side on every screen size including phones. ── */
        @media (max-width: 640px) {
            div[data-testid="stHorizontalBlock"] {
                flex-direction: row !important;
                flex-wrap: nowrap !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                width: auto !important;
                min-width: 0 !important;
            }
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 8px !important;
        }
        div[data-testid="stHorizontalBlock"] [data-testid="column"] {
            padding: 0 !important;
        }

        /* ── BUTTONS ── */
        .stButton > button, [data-testid="stFormSubmitButton"] > button {
            background: #2C2520 !important;
            color: #F5F0E8 !important;
            border: 1px solid rgba(232,82,26,0.2) !important;
            border-radius: 10px !important;
            width: 100% !important;
            min-height: 44px !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            padding: 0.25rem 0.5rem !important;
            line-height: 1.3 !important;
            text-align: center !important;
            transition: border-color 0.2s !important;
        }
        .stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
            background: #3D3530 !important;
            border-color: rgba(232,82,26,0.5) !important;
        }
        .stButton > button:focus, [data-testid="stFormSubmitButton"] > button:focus {
            box-shadow: none !important;
        }

        /* ── Hide the form's submit button completely — Enter key still
           triggers it natively because that's how HTML forms work ── */
        [data-testid="stFormSubmitButton"] { display: none !important; }
        [data-testid="stForm"] { border: none !important; padding: 0 !important; }

        /* ── BACK BUTTON ── */
        .back-btn .stButton > button {
            background: transparent !important;
            border: 1px solid rgba(232,82,26,0.25) !important;
            border-radius: 8px !important;
            min-height: 36px !important;
            font-size: 12px !important;
            color: #8A7E76 !important;
            font-weight: 400 !important;
            padding: 4px 12px !important;
            width: auto !important;
        }
        .back-btn .stButton > button:hover {
            border-color: rgba(232,82,26,0.5) !important;
            color: #F5F0E8 !important;
        }

        /* ── TEXT INPUT (single line — Enter submits natively) ── */
        .stTextInput label { display: none !important; }
        .stTextInput input {
            background: #2C2520 !important;
            color: #F5F0E8 !important;
            border: 1px solid rgba(232,82,26,0.3) !important;
            border-radius: 12px !important;
            font-size: 14px !important;
            padding: 14px 16px !important;
            font-family: sans-serif !important;
        }
        .stTextInput input:focus {
            border-color: #E8521A !important;
            box-shadow: none !important;
        }
        .stTextInput input::placeholder { color: #8A7E76 !important; }

        /* ── TEXT AREA (used elsewhere — verify/document sections) ── */
        .stTextArea label { display: none !important; }
        .stTextArea textarea {
            background: #2C2520 !important;
            color: #F5F0E8 !important;
            border: 1px solid rgba(232,82,26,0.3) !important;
            border-radius: 12px !important;
            font-size: 14px !important;
            resize: none !important;
            padding: 10px 16px !important;
            font-family: sans-serif !important;
        }
        .stTextArea textarea:focus {
            border-color: #E8521A !important;
            box-shadow: none !important;
        }
        .stTextArea textarea::placeholder { color: #8A7E76 !important; }

        /* ── FORM/CARD ELEMENTS ── */
        .stSelectbox label { color: #8A7E76 !important; font-size: 13px !important; }
        div[data-testid="stSelectbox"] > div > div {
            background: #2C2520 !important;
            border-color: rgba(232,82,26,0.3) !important;
            color: #F5F0E8 !important;
        }
        div[data-testid="stTextInput"] input {
            background: #2C2520 !important;
            border-color: rgba(232,82,26,0.3) !important;
            color: #F5F0E8 !important;
        }
        /* ── AUTH UI ── */
        .account-bar div[data-testid="stHorizontalBlock"] {
            gap: 8px !important;
            flex-wrap: nowrap !important;
        }
        .account-bar div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            flex: 1 1 0 !important;
            min-width: 0 !important;
            max-width: 50% !important;
            padding: 0 !important;
        }
        .account-bar div[data-testid="stHorizontalBlock"] > div[data-testid="column"] .stButton > button {
            width: 100% !important;
            font-size: 11px !important;
        }
        [data-testid="stLinkButton"] a {
            background: #2C2520 !important; color: #8A7E76 !important;
            border: 1px solid rgba(232,82,26,0.25) !important; border-radius: 8px !important;
            width: 100% !important; min-height: 38px !important;
            font-size: 12px !important; font-weight: 500 !important;
            display: flex !important; align-items: center !important;
            justify-content: center !important; text-decoration: none !important;
        }
        [data-testid="stLinkButton"] a:hover {
            background: #3D3530 !important; color: #F5F0E8 !important;
            border-color: rgba(232,82,26,0.5) !important;
        }
    </style>
""", unsafe_allow_html=True)

# ── Initialize Anthropic client ──
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)
except KeyError:
    st.error("API key not found.")
    st.stop()
except Exception as e:
    st.error(f"Failed to initialize: {e}")
    st.stop()

# ── System prompts ──
chat_system_prompt = """
You are a helpful assistant named Handy Helper for DIY Services.

PERSONALITY:
You are friendly, knowledgeable, and always give structured, practical advice.
You turn handyman projects into DIY accomplishments.

PHOTO ANALYSIS:
When a user uploads a photo you should:
- Carefully examine what you see in the image
- Identify the specific problem, damage, or item shown
- Give advice tailored exactly to what is visible in the photo
- Point out anything concerning or important you notice
- Ask clarifying questions if needed based on what you see

CATEGORIES:
- Carpentry, Doors, Electrical, Flooring, Leaks, Lighting, Plumbing
- Trim, Windows, Generators, Decks and Porches, Garage Doors
- Siding, Roofing and Gutters, Drywall, Furniture Assembly
- Appliance Repair, Pest Control, Painting, Driveway Sealing
- Water Heater, Furnace, Air Conditioner, HVAC, Security
- Propane, Natural Gas, Foundation Repair, Landscaping
- Tile and Grout, Smart Home Devices, Garbage Disposal
- Dishwasher, Fencing, Weatherproofing, Carbon Monoxide Detectors
- Smoke Detectors, Pool and Spa, Insulation, Concrete and Masonry
- Chimney and Fireplace, Irrigation and Sprinklers, Basement Waterproofing
- EV Charging, Solar Panels, Dryer Vent Cleaning, Septic System
- Crawl Space, Cabinet Repair, Exterior Lighting

SAFETY RESTRICTIONS TIER 1:
- Power tools, Heavy equipment, Fire hazards, Safety concerns
- Verify user confidence and recommend three reputable local professionals

SAFETY RESTRICTIONS TIER 2:
- Inside electrical panel, Inside electrical meter base
- Ladder usage, Wall removal
- Explain risks and strongly recommend three reputable local professionals

RULES:
- Only answer questions based on CATEGORIES
- If someone asks something unrelated politely redirect
- Keep responses clear and practical
"""

verify_system_prompt = """
You are Handy Helper's Work Verification AI. A homeowner has uploaded photos of completed work 
and needs an independent, evidence-based assessment before releasing payment to their contractor.

CORE RULES — FOLLOW STRICTLY:

1. GROUND EVERY CLAIM IN A SPECIFIC VISUAL DETAIL. Never write a generic statement like 
   "the work looks professional" without naming exactly what you see that supports it — 
   the specific fixture, material, alignment, gap, color, texture, or measurement that led 
   you to that conclusion. If you cannot point to a specific visual detail, do not make the claim.

2. DISTINGUISH WHAT YOU CAN SEE FROM WHAT YOU CANNOT. Many quality issues (water-tightness, 
   electrical continuity, code compliance, structural integrity, what's behind a wall or under 
   a floor) cannot be verified from a photo. Explicitly say so rather than guessing or assuming 
   it is fine. Phrases like "this appears..." or "based on the visible portion..." are required 
   when you are inferring rather than directly observing.

3. EXAMINE EACH PHOTO METHODICALLY before writing your assessment. For each image, mentally 
   note: object identification, materials/fixtures visible, alignment and symmetry, gaps or 
   seams, color/finish consistency, visible hardware (screws, caulk lines, joints, connections), 
   and any debris, damage, or incomplete elements. Only then synthesize your findings.

4. DO NOT DEFAULT TO POSITIVE. There is no reward for finding the work acceptable. If photos 
   are blurry, poorly lit, too distant, or do not show the relevant area clearly, say so directly 
   and recommend the homeowner request a clearer photo or in-person inspection rather than 
   assuming the work is fine.

5. CALIBRATE CONFIDENCE TO IMAGE QUALITY. A close, well-lit, in-focus photo supports stronger 
   statements. A distant, dark, or blurry photo only supports weak, hedged statements. Say which 
   you're dealing with.

Analyze the photos carefully and provide a structured response with these exact sections:

OVERALL ASSESSMENT
2-3 sentences. State what trade/task this appears to be, image quality/clarity, and your 
overall confidence level in assessing it from these photos specifically.

WHAT LOOKS CORRECT
List specific, visually-grounded observations of properly done work. Each bullet must cite 
the specific visual evidence (e.g. "Caulk line along the tub edge is continuous and uniform 
width with no visible gaps" — not just "caulking looks good").

ITEMS TO VERIFY
List specific things the homeowner should ask the contractor about or inspect more closely 
in person — things the photo cannot confirm (e.g. "Photo doesn't show whether the P-trap 
connection is fully tightened — ask contractor to confirm or run water to check for leaks").

RED FLAGS
List specific, visually-grounded concerns only — things actually visible that indicate 
improper, incomplete, or substandard work (e.g. "Gap visible between the baseboard and 
flooring on the left side, roughly 1/4 inch, suggesting uneven installation"). 
If none are visible say "No red flags visible in these specific photos" — and note this 
does NOT mean the work is guaranteed correct, only that nothing visible raises concern.

PAYMENT RECOMMENDATION
One clear recommendation: Proceed with payment / Request corrections first / 
Get a professional inspection before paying. Justify the recommendation using only the 
specific evidence cited above — do not introduce new reasoning here.

DISCLAIMER
Always end with: This AI analysis is based solely on the photos provided and is for guidance 
only. It cannot detect issues not visible in the images (such as code compliance, hidden 
connections, or structural integrity) and does not replace a professional inspection. 
Handy Helper is not liable for work quality assessments.
"""

doc_system_prompt = """
You are Handy Helper's Job Documentation AI. A contractor has uploaded a photo 
of work in progress for their job record. Your job is to provide a brief, professional 
description of what is visible in the photo for the documentation record.

Stage: {stage}
Trade/Job Type: {job_type}

Provide a concise 2-4 sentence professional description of:
1. What is visible in the photo
2. The apparent quality and completeness of the work at this stage
3. Any notable observations relevant to this stage of work

Keep it factual and professional — this is for an official job record.
"""

# ── Helper functions ──
def compress_and_encode(file_bytes, max_size_mb=4):
    MAX = max_size_mb * 1024 * 1024
    try:
        img = Image.open(io.BytesIO(file_bytes))
    except Exception:
        return base64.standard_b64encode(file_bytes[:MAX]).decode("utf-8"), None
    if img.mode != "RGB":
        try:
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img.convert("RGB"))
            img = bg
        except Exception:
            img = img.convert("RGB")
    if img.width > 1280 or img.height > 1280:
        img.thumbnail((1280, 1280), Image.LANCZOS)
    for quality in [82, 70, 58, 45, 32, 20]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"
    for scale in [0.7, 0.55, 0.4, 0.3, 0.2]:
        w = max(100, int(img.width * scale))
        h = max(100, int(img.height * scale))
        resized = img.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=40, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"
    img.thumbnail((480, 480), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=25)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"

def get_media_type(file_type, override=None):
    if override:
        return override
    if file_type in ["image/jpeg", "image/jpg"]:
        return "image/jpeg"
    elif file_type == "image/png":
        return "image/png"
    elif file_type == "image/gif":
        return "image/gif"
    elif file_type == "image/webp":
        return "image/webp"
    return "image/jpeg"

def generate_pdf(job_info, photos):
    # fpdf2 with Helvetica only supports Latin-1 characters.
    # Replace any unsupported Unicode chars before writing to PDF.
    def safe(text):
        return (str(text)
                .replace("\u2014", "-")   # em dash —
                .replace("\u2013", "-")   # en dash –
                .replace("\u2018", "'")   # left single quote
                .replace("\u2019", "'")   # right single quote
                .replace("\u201C", '"')   # left double quote
                .replace("\u201D", '"')   # right double quote
                .replace("\u2022", "*")   # bullet
                .replace("\u00e9", "e")   # é
                .replace("\u00e8", "e")   # è
                .replace("\u00e0", "a")   # à
                .encode("latin-1", errors="replace").decode("latin-1"))
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    pdf.set_fill_color(26, 22, 18)
    pdf.rect(0, 0, 210, 60, 'F')
    pdf.set_xy(15, 8)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(232, 82, 26)
    pdf.cell(0, 10, "HANDY", ln=False)
    pdf.set_text_color(245, 240, 232)
    pdf.cell(0, 10, "HELPER", ln=True)
    pdf.set_xy(15, 20)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(255, 122, 69)
    pdf.cell(0, 6, "COMPANY LLC", ln=True)
    pdf.set_xy(15, 28)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(138, 126, 118)
    pdf.cell(0, 5, "handyhelper.company", ln=True)
    pdf.set_xy(15, 36)
    pdf.set_text_color(245, 240, 232)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, safe("Completed With Pride — Job Documentation Report"), ln=True)
    pdf.set_xy(15, 43)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(138, 126, 118)
    pdf.cell(0, 5, f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", ln=True)
    pdf.set_xy(15, 70)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(26, 22, 18)
    pdf.cell(0, 8, "JOB INFORMATION", ln=True)
    pdf.set_line_width(0.5)
    pdf.set_draw_color(232, 82, 26)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)
    fields = [
        ("Job Name / ID", job_info.get("job_name", "")),
        ("Contractor", job_info.get("contractor_name", "")),
        ("Client Name", job_info.get("client_name", "")),
        ("Property Address", job_info.get("address", "")),
        ("Job Type / Trade", job_info.get("job_type", "")),
        ("Date", job_info.get("date", "")),
    ]
    pdf.set_font("Helvetica", "", 10)
    for label, value in fields:
        pdf.set_text_color(100, 100, 100)
        pdf.cell(55, 7, label + ":", ln=False)
        pdf.set_text_color(26, 22, 18)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, safe(str(value)), ln=True)
        pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(26, 22, 18)
    pdf.cell(0, 8, f"DOCUMENTED STAGES ({len(photos)} photos)", ln=True)
    pdf.set_draw_color(232, 82, 26)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    tmp_files = []
    for i, photo in enumerate(photos, 1):
        pdf.add_page()
        pdf.set_fill_color(232, 82, 26)
        pdf.rect(0, 0, 210, 18, 'F')
        pdf.set_xy(15, 5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 8, safe(f"STAGE {i}: {photo['stage'].upper()}"), ln=True)
        pdf.set_xy(15, 22)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(60, 5, safe(f"Timestamp: {photo['timestamp']}"), ln=False)
        pdf.cell(0, 5, safe(f"Job: {job_info.get('job_name', '')}  |  Type: {job_info.get('job_type', '')}"), ln=True)
        try:
            img_bytes = photo["bytes"]
            img = Image.open(io.BytesIO(img_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((800, 800), Image.LANCZOS)
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            img.save(tmp.name, "JPEG", quality=85)
            tmp.close()
            tmp_files.append(tmp.name)
            img_w, img_h = img.size
            max_w, max_h = 165, 110
            ratio = min(max_w / img_w, max_h / img_h)
            disp_w, disp_h = img_w * ratio, img_h * ratio
            x_offset = (210 - disp_w) / 2
            pdf.image(tmp.name, x=x_offset, y=32, w=disp_w, h=disp_h)
            pdf.set_y(32 + disp_h + 6)
        except Exception as e:
            pdf.set_y(35)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 6, f"[Photo could not be rendered: {e}]", ln=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(232, 82, 26)
        pdf.cell(0, 6, "AI DOCUMENTATION NOTES", ln=True)
        pdf.set_draw_color(232, 82, 26)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 5, safe(photo.get("analysis", "No analysis available.")))
        pdf.set_y(-20)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, f"Handy Helper Company LLC  |  handyhelper.company  |  Page {i + 1} of {len(photos) + 1}", ln=True, align="C")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(26, 22, 18)
    pdf.cell(0, 8, "DOCUMENTATION DISCLAIMER", ln=True)
    pdf.set_draw_color(232, 82, 26)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 6, (
        "This Contractor Job Documentation Report was generated by Handy Helper Company LLC "
        "using AI-powered photo analysis. The timestamps recorded in this document reflect the "
        "date and time each photo was uploaded to the Handy Helper platform.\n\n"
        "This document is intended to serve as a photographic record of work completed at each "
        "documented stage of the project. It is provided for informational and documentation "
        "purposes only and does not constitute a professional inspection, warranty, or guarantee "
        "of workmanship.\n\n"
        "Handy Helper Company LLC is not liable for any claims arising from the use of this "
        "documentation report. Both contractors and homeowners are encouraged to retain copies "
        "of this report for their records.\n\n"
        "For questions about this report contact:\n"
        "Handy Helper Company LLC\n"
        "yourhelper@handyhelper.company  |  513-223-1607  |  handyhelper.company"
    ))
    pdf_bytes = bytes(pdf.output())
    for f in tmp_files:
        try:
            os.unlink(f)
        except Exception:
            pass
    return pdf_bytes

# ── Session state ──
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_image" not in st.session_state:
    st.session_state.pending_image = None
if "current_section" not in st.session_state:
    st.session_state.current_section = "chat"
if "contractor_photos" not in st.session_state:
    st.session_state.contractor_photos = []
if "contractor_job_info" not in st.session_state:
    st.session_state.contractor_job_info = {}
if "job_started" not in st.session_state:
    st.session_state.job_started = False
if "hw_analysis" not in st.session_state:
    st.session_state.hw_analysis = None
if "sb_current_session" not in st.session_state:
    st.session_state.sb_current_session = None
if "sb_auth_mode" not in st.session_state:
    st.session_state.sb_auth_mode = "signin"

# ── Auto-navigate to auth if linked from website Sign In button ──
# Guard with not get_user() so a successful sign-in doesn't bounce back to auth
_qp = st.query_params
if _qp.get("section") == "auth" and st.session_state.current_section == "chat" and not get_user():
    st.session_state.current_section = "auth"

# ── Broadcast auth state to parent window on every render ──
# Only broadcasts when signed in — never clears on empty (cookie manager
# may not have initialized yet on first render, causing false sign-outs).
# Explicit sign-out is handled separately via sb_did_sign_out flag.
_broadcast_email = get_user()["email"] if get_user() else ""
_did_sign_out = st.session_state.pop("sb_did_sign_out", False)

if _broadcast_email:
    components.html(f"""<script>
    (function() {{
        var msg = {{action:'hhUserInfo', email:'{_broadcast_email}'}};
        try {{ window.top.postMessage(msg, '*'); }} catch(e) {{}}
        try {{ window.parent.postMessage(msg, '*'); }} catch(e) {{}}
    }})();
    </script>""", height=1)
elif _did_sign_out:
    components.html("""<script>
    (function() {
        var msg = {action:'hhSignOut'};
        try { window.top.postMessage(msg, '*'); } catch(e) {}
        try { window.parent.postMessage(msg, '*'); } catch(e) {}
    })();
    </script>""", height=1)

# ══════════════════════════════════════════════════════════
# SECTION: AI CHAT
# ══════════════════════════════════════════════════════════
if st.session_state.current_section == "chat":

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                for block in message["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        st.markdown(block["text"])
            else:
                st.markdown(message["content"])

    if not st.session_state.messages:
        # ── Account bar — very top of window ──
        # Detect if running embedded in the homepage (vs full-screen in chat.html)
        _is_embedded = st.query_params.get("embedded") == "true"
        user = get_user()
        if user:
            # Always show signed-in state — both embedded and full-screen
            st.markdown(f'<p style="font-size:11px; color:#8A7E76; margin:0.2rem 0 0.3rem; text-align:center;">👤 {user["email"]}</p>', unsafe_allow_html=True)
            if not _is_embedded:
                if st.button("📜  Chat History", key="sign_top_history", use_container_width=True):
                    st.session_state.current_section = "history"
                    st.rerun()
            if st.button("↩️  Sign Out", key="sign_out_top", use_container_width=True):
                do_sign_out()
                st.rerun()
        elif DB_ENABLED and not _is_embedded:
            # Only show sign-in prompt in full-screen mode (chat.html)
            # Homepage nav already handles sign-in — showing it twice is confusing
            st.markdown('<p style="font-size:11px; color:#8A7E76; margin:0.2rem 0 0.3rem; text-align:center;">💾 Sign in to save your history & projects</p>', unsafe_allow_html=True)
            if st.button("👤  Sign In / Create Account", key="nav_auth_top", use_container_width=True):
                st.session_state.current_section = "auth"
                st.rerun()

        st.markdown("""
            <div style="height:6vh;"></div>
            <div style="padding:0.5rem; margin-bottom:0.4rem;
                background:linear-gradient(135deg,#2C2520 0%,#1A1612 100%);
                border:1px solid rgba(232,82,26,0.3);
                border-left:4px solid #E8521A;
                border-radius:8px; text-align:center;">
                <div style="font-size:16px; margin-bottom:0.2rem;">🔧</div>
                <div style="font-size:13px; font-weight:700; color:#F5F0E8; margin-bottom:0.2rem;">
                    Every Expert Was Once a Beginner
                </div>
                <div style="font-size:10px; color:#8A7E76; max-width:280px; margin:0 auto 0.3rem;">
                    Ask me anything about your project and let's get it done together.
                </div>
                <div style="display:flex; justify-content:center; gap:0.75rem;">
                    <span style="font-size:9px; color:#E8521A; font-family:monospace;">50+ CATEGORIES</span>
                    <span style="font-size:9px; color:#8A7E76;">•</span>
                    <span style="font-size:9px; color:#E8521A; font-family:monospace;">PHOTO ANALYSIS</span>
                    <span style="font-size:9px; color:#8A7E76;">•</span>
                    <span style="font-size:9px; color:#E8521A; font-family:monospace;">FREE 24/7</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # ── Chat input — native HTML form, Enter submits, no arrow needed ──
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "question", placeholder="What project are we working on today?",
            key="chat_input", label_visibility="collapsed"
        )
        send = st.form_submit_button("Send")

    # ── Upload box (under chat input) ──
    uploaded_file = st.file_uploader(
        "photo", type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed", key="chat_uploader"
    )

    if uploaded_file is not None:
        raw_bytes = uploaded_file.read()
        encoded, override = compress_and_encode(raw_bytes)
        media_type = get_media_type(uploaded_file.type, override)
        st.session_state.pending_image = {
            "data": encoded, "media_type": media_type,
            "name": uploaded_file.name, "bytes": raw_bytes
        }
        st.image(io.BytesIO(raw_bytes), caption="📷 Photo ready!", width=150)
        st.success("✓ Photo attached! Type your question and press Enter")
    elif st.session_state.pending_image is None:
        st.markdown(
            '<p style="font-size:11px; color:#8A7E76; margin:0.1rem 0 0;">📷 Upload a photo (optional)</p>',
            unsafe_allow_html=True
        )
    else:
        st.success("✓ Photo still attached! Type your question and press Enter")

    # ── Nav buttons (under uploader, only when no messages) ──
    if not st.session_state.messages:
        if st.button("🗓️  Project Manager", key="nav_projects", use_container_width=True):
            st.session_state.current_section = "projects"
            st.rerun()
        if st.button("🏠👋  Pay With Confidence", key="nav_verify", use_container_width=True):
            st.session_state.current_section = "verify"
            st.rerun()
        if st.button("🚐👋  Completed With Pride", key="nav_doc", use_container_width=True):
            st.session_state.current_section = "document"
            st.rerun()
        st.markdown(
            '<p style="font-size:10px; color:#8A7E76; text-align:center; margin-top:0.3rem;">'
            'Use the top bar to return to the website</p>',
            unsafe_allow_html=True
        )

    if send and user_input and user_input.strip():
        prompt = user_input.strip()
        pending = st.session_state.pending_image
        if pending:
            user_content = [
                {"type": "image", "source": {"type": "base64",
                 "media_type": pending["media_type"], "data": pending["data"]}},
                {"type": "text", "text": prompt}
            ]
            display_content = [{"type": "text", "text": f"[Photo attached] {prompt}"}]
        else:
            user_content = prompt
            display_content = prompt
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": display_content})

        # ── Create or reuse DB session for this conversation ──
        if DB_ENABLED and get_user():
            if not st.session_state.sb_current_session:
                st.session_state.sb_current_session = start_chat_session(prompt)
            save_message(st.session_state.sb_current_session, "user", prompt)
        conversation = []
        for msg in st.session_state.messages[:-1]:
            if isinstance(msg["content"], list):
                text = " ".join(b["text"] for b in msg["content"]
                                if isinstance(b, dict) and b.get("type") == "text")
                conversation.append({"role": msg["role"], "content": text})
            else:
                conversation.append({"role": msg["role"], "content": msg["content"]})
        conversation.append({"role": "user", "content": user_content})
        with st.chat_message("assistant"):
            with st.spinner("Handy Helper is thinking..."):
                try:
                    while True:
                        response = client.messages.create(
                            model="claude-opus-4-6", max_tokens=1024,
                            system=chat_system_prompt,
                            tools=[{"type": "web_search_20250305", "name": "web_search"}],
                            messages=conversation
                        )
                        if response.stop_reason == "tool_use":
                            conversation.append({"role": "assistant", "content": response.content})
                            tool_results = []
                            for block in response.content:
                                if block.type == "tool_use":
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": block.id,
                                        "content": block.input.get("query", "")
                                    })
                            conversation.append({"role": "user", "content": tool_results})
                        else:
                            reply = "".join(block.text for block in response.content
                                            if hasattr(block, "text"))
                            break
                except Exception as e:
                    reply = f"Something went wrong: {e}"
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            # ── Save assistant reply to DB ──
            if DB_ENABLED and get_user():
                save_message(st.session_state.sb_current_session, "assistant", reply)
        st.session_state.pending_image = None
        st.rerun()

# ══════════════════════════════════════════════════════════
# SECTION: AUTH (Sign In / Create Account)
# ══════════════════════════════════════════════════════════
elif st.session_state.current_section == "auth":

    st.markdown('<div class="back-btn">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Chat", key="back_auth"):
            st.query_params.clear()
            st.session_state.current_section = "chat"
            st.rerun()
    with col2:
        st.link_button(
            "← Return to handyhelper.company",
            "https://handyhelper.company",
            use_container_width=True
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
        <div style="padding:1rem; margin-bottom:1rem;
            background:linear-gradient(135deg,#2C2520,#1A1612);
            border:1px solid rgba(232,82,26,0.3);
            border-left:4px solid #E8521A; border-radius:8px;">
            <div style="font-size:15px; font-weight:700; color:#F5F0E8; margin-bottom:0.3rem;">
                👤 Your Handy Helper Account
            </div>
            <div style="font-size:12px; color:#8A7E76;">
                Create a free account to save your chat history and projects
                across all your devices. The app is always free — an account
                just gives you a memory.
            </div>
        </div>
    """, unsafe_allow_html=True)

    mode = st.session_state.get("sb_auth_mode", "signin")
    if st.button("Sign In", key="mode_signin",
                 use_container_width=True,
                 type="primary" if mode == "signin" else "secondary"):
        st.session_state.sb_auth_mode = "signin"
        st.rerun()
    if st.button("Create Account", key="mode_signup",
                 use_container_width=True,
                 type="primary" if mode == "signup" else "secondary"):
        st.session_state.sb_auth_mode = "signup"
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    auth_email = st.text_input("Email address", key="auth_email", placeholder="you@email.com")
    auth_pass  = st.text_input("Password", key="auth_pass", type="password",
                                placeholder="Minimum 6 characters")

    if mode == "signin":
        if st.button("Sign In →", key="do_signin", use_container_width=True):
            if not auth_email or not auth_pass:
                st.error("Please enter your email and password.")
            else:
                try:
                    do_sign_in(auth_email, auth_pass)
                    st.query_params.clear()
                    st.success("Signed in! Loading your history...")
                    st.session_state.current_section = "chat"
                    st.session_state.sb_current_session = None
                    st.rerun()
                except Exception as e:
                    st.error("Sign in failed — check your email and password.")
    else:
        auth_pass2 = st.text_input("Confirm password", key="auth_pass2", type="password")
        if st.button("Create Account →", key="do_signup", use_container_width=True):
            if not auth_email or not auth_pass:
                st.error("Please enter your email and password.")
            elif auth_pass != auth_pass2:
                st.error("Passwords don't match.")
            elif len(auth_pass) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    res = do_sign_up(auth_email, auth_pass)
                    if res.user:
                        st.success("Account created! Check your email to confirm, then sign in.")
                        st.session_state.sb_auth_mode = "signin"
                        st.rerun()
                    else:
                        st.error("Something went wrong. Please try again.")
                except Exception as e:
                    st.error(f"Could not create account: {e}")

# ══════════════════════════════════════════════════════════
# SECTION: CHAT HISTORY
# ══════════════════════════════════════════════════════════
elif st.session_state.current_section == "history":

    st.markdown('<div class="back-btn">', unsafe_allow_html=True)
    if st.button("← Back to Chat", key="back_history"):
        st.session_state.current_section = "chat"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    user = get_user()
    if not user:
        st.info("Sign in to view your chat history.")
    else:
        st.markdown(f"""
            <div style="padding:0.75rem 1rem; margin-bottom:1rem;
                background:linear-gradient(135deg,#2C2520,#1A1612);
                border:1px solid rgba(232,82,26,0.3);
                border-left:4px solid #E8521A; border-radius:8px;">
                <div style="font-size:14px; font-weight:700; color:#F5F0E8;">📜 Chat History</div>
                <div style="font-size:11px; color:#8A7E76; margin-top:2px;">Signed in as {user['email']}</div>
            </div>
        """, unsafe_allow_html=True)

        if st.button("➕  Start New Conversation", key="new_convo", use_container_width=True):
            st.session_state.messages = []
            st.session_state.sb_current_session = None
            st.session_state.current_section = "chat"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        history = load_history()

        if not history:
            st.markdown('<p style="font-size:13px; color:#8A7E76; text-align:center;">No conversations saved yet.<br>Start chatting and your history will appear here.</p>', unsafe_allow_html=True)
        else:
            for session in history:
                ts = session.get("updated_at","")[:10]
                col1, col2 = st.columns([7, 2])
                with col1:
                    st.markdown(f"""
                        <div style="background:#2C2520; border:1px solid rgba(232,82,26,0.15);
                            border-radius:8px; padding:0.6rem 0.75rem; margin-bottom:4px;">
                            <div style="font-size:13px; color:#F5F0E8; font-weight:500;">{session.get('title','Conversation')[:50]}</div>
                            <div style="font-size:10px; color:#8A7E76; margin-top:2px;">{ts}</div>
                        </div>
                    """, unsafe_allow_html=True)
                with col2:
                    if st.button("Open", key=f"open_sess_{session['id']}"):
                        msgs = load_session_msgs(session["id"])
                        st.session_state.messages = msgs
                        st.session_state.sb_current_session = session["id"]
                        st.session_state.current_section = "chat"
                        st.rerun()
                    if st.button("🗑️", key=f"del_sess_{session['id']}"):
                        delete_session(session["id"])
                        st.rerun()

# ══════════════════════════════════════════════════════════
# SECTION: PROJECT MANAGER
# ══════════════════════════════════════════════════════════
elif st.session_state.current_section == "projects":

    st.markdown('<div class="back-btn">', unsafe_allow_html=True)
    if st.button("← Back to Chat", key="back_projects"):
        st.session_state.current_section = "chat"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
        <div style="padding:1rem; margin-bottom:1rem;
            background:linear-gradient(135deg,#2C2520,#1A1612);
            border:1px solid rgba(232,82,26,0.3);
            border-left:4px solid #E8521A; border-radius:8px;">
            <div style="font-size:15px; font-weight:700; color:#F5F0E8; margin-bottom:0.3rem;">
                🗓️ Project Manager
            </div>
            <div style="font-size:12px; color:#8A7E76;">
                Plan and track your entire renovation from pre-construction
                through every phase to final completion — with AI guidance
                at every step.
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style="display:flex; flex-direction:column; gap:0.5rem; margin-bottom:1rem;">
            <div style="display:flex; align-items:center; gap:0.5rem; font-size:13px; color:#8A7E76;">
                <span style="color:#E8521A;">✓</span> AI-generated contractor questions before work begins
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem; font-size:13px; color:#8A7E76;">
                <span style="color:#E8521A;">✓</span> Phase-by-phase tracking with notes and photos
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem; font-size:13px; color:#8A7E76;">
                <span style="color:#E8521A;">✓</span> Budget tracker — estimated vs actual
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem; font-size:13px; color:#8A7E76;">
                <span style="color:#E8521A;">✓</span> Full PDF project report export
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem; font-size:13px; color:#8A7E76;">
                <span style="color:#E8521A;">✓</span> Supports 8 major project types
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <style>
            [data-testid="stLinkButton"] a {
                background: #E8521A !important;
                color: white !important;
                border: none !important;
                border-radius: 10px !important;
                width: 100% !important;
                min-height: 52px !important;
                font-size: 14px !important;
                font-weight: 700 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                text-decoration: none !important;
                letter-spacing: 0.5px !important;
            }
            [data-testid="stLinkButton"] a:hover {
                background: #C43E0A !important;
                color: white !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.link_button(
        "🏗️  Open Project Manager →",
        "https://handy-projects-ydshcuvzcxmsqs8ygkhvxi.streamlit.app",
        use_container_width=True
    )

    st.markdown(
        '<p style="font-size:10px; color:#8A7E76; text-align:center; margin-top:0.4rem;">'
        'Opens in full screen · Free · No account required</p>',
        unsafe_allow_html=True
    )

# ══════════════════════════════════════════════════════════
# SECTION: PAY WITH CONFIDENCE
# ══════════════════════════════════════════════════════════
elif st.session_state.current_section == "verify":

    st.markdown('<div class="back-btn">', unsafe_allow_html=True)
    if st.button("← Back to Chat", key="back_verify"):
        st.session_state.current_section = "chat"
        st.session_state.hw_analysis = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
        <div style="padding:1rem; margin-bottom:1rem;
            background:linear-gradient(135deg,#2C2520,#1A1612);
            border:1px solid rgba(232,82,26,0.3);
            border-left:4px solid #E8521A; border-radius:8px;">
            <div style="font-size:15px; font-weight:700; color:#F5F0E8; margin-bottom:0.3rem;">
                🏠👋 Pay With Confidence
            </div>
            <div style="font-size:12px; color:#8A7E76;">
                Upload photos of completed work before paying your contractor.
                Our AI gives you an independent assessment so you never pay blindly again.
            </div>
        </div>
    """, unsafe_allow_html=True)

    hw_job_desc = st.text_area(
        "Describe the job that was done",
        placeholder="Example: Plumber replaced pipes under kitchen sink and installed new faucet...",
        height=80, key="hw_job_desc"
    )
    hw_photos = st.file_uploader(
        "Upload photos of the completed work",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True, key="hw_uploader"
    )
    st.markdown(
        '<p style="font-size:10px; color:#8A7E76; margin:-0.4rem 0 0.5rem 0;">'
        '💡 For the most accurate assessment: take close-up, well-lit photos '
        'directly facing the work — avoid distance shots, shadows, or blur.</p>',
        unsafe_allow_html=True
    )
    if hw_photos:
        cols = st.columns(min(len(hw_photos), 3))
        for i, photo in enumerate(hw_photos):
            with cols[i % 3]:
                st.image(photo, caption=f"Photo {i+1}", use_column_width=True)

    analyze_btn = st.button("🔍 Analyze Work Quality", key="hw_analyze", use_container_width=True)

    if analyze_btn:
        if not hw_photos:
            st.warning("Please upload at least one photo of the completed work.")
        elif not hw_job_desc.strip():
            st.warning("Please describe the job that was done.")
        else:
            with st.spinner("Analyzing work quality — this may take a moment..."):
                try:
                    content = []
                    for photo in hw_photos:
                        raw = photo.read()
                        encoded, override = compress_and_encode(raw)
                        mt = get_media_type(photo.type, override)
                        content.append({"type": "image",
                                        "source": {"type": "base64", "media_type": mt, "data": encoded}})
                    content.append({"type": "text",
                                    "text": f"Job Description: {hw_job_desc}\n\nPlease analyze these photos."})
                    response = client.messages.create(
                        model="claude-opus-4-6", max_tokens=2200,
                        system=verify_system_prompt,
                        messages=[{"role": "user", "content": content}]
                    )
                    st.session_state.hw_analysis = "".join(
                        block.text for block in response.content if hasattr(block, "text")
                    )
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

    if st.session_state.hw_analysis:
        st.markdown("""
            <div style="margin-top:1rem; padding:0.75rem 1rem;
                background:#2C2520; border:1px solid rgba(232,82,26,0.3);
                border-radius:8px;">
                <div style="font-size:13px; font-weight:700; color:#E8521A; margin-bottom:0.5rem;">
                    📋 VERIFICATION REPORT
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown(st.session_state.hw_analysis)
        if st.button("🔄 Start New Verification", key="hw_reset"):
            st.session_state.hw_analysis = None
            st.rerun()

# ══════════════════════════════════════════════════════════
# SECTION: COMPLETED WITH PRIDE
# ══════════════════════════════════════════════════════════
elif st.session_state.current_section == "document":

    st.markdown('<div class="back-btn">', unsafe_allow_html=True)
    if st.button("← Back to Chat", key="back_doc"):
        st.session_state.current_section = "chat"
        st.session_state.job_started = False
        st.session_state.contractor_photos = []
        st.session_state.contractor_job_info = {}
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
        <div style="padding:1rem; margin-bottom:1rem;
            background:linear-gradient(135deg,#2C2520,#1A1612);
            border:1px solid rgba(232,82,26,0.3);
            border-left:4px solid #E8521A; border-radius:8px;">
            <div style="font-size:15px; font-weight:700; color:#F5F0E8; margin-bottom:0.3rem;">
                🚐👋 Completed With Pride
            </div>
            <div style="font-size:12px; color:#8A7E76;">
                Document your work stage by stage with timestamped AI-verified photos.
                Protects you from disputes and builds homeowner confidence.
            </div>
        </div>
    """, unsafe_allow_html=True)

    STAGES = [
        "Before — Demo/Removal", "Rough-In Phase", "Behind Wall / In Wall Cavity",
        "Under Floor / Under Slab", "In Ceiling / Attic Space", "Before Drywall",
        "Before Tile", "Before Insulation", "Before Concrete Pour", "Before Backfill",
        "Framing Complete", "Electrical Rough-In", "Plumbing Rough-In", "HVAC Rough-In",
        "Inspection Ready", "Final Completion", "Custom Stage...",
    ]
    JOB_TYPES = [
        "Plumbing", "Electrical", "HVAC", "Roofing", "Flooring", "Drywall",
        "Foundation / Concrete", "Framing", "Insulation", "Painting", "Tile Work",
        "General Contractor", "Other"
    ]

    if not st.session_state.job_started:
        st.markdown("**Step 1 — Enter Job Information**")
        job_name    = st.text_input("Job Name / ID *", placeholder="e.g. Johnson Kitchen Reno — June 2026", key="job_name")
        cont_name   = st.text_input("Contractor Name *", placeholder="Your name or company name", key="cont_name")
        client_name = st.text_input("Client Name *", placeholder="Homeowner name", key="client_name")
        address     = st.text_input("Property Address *", placeholder="123 Main St, Cincinnati OH 45238", key="address")
        job_type    = st.selectbox("Job Type / Trade *", JOB_TYPES, key="job_type_select")
        job_date    = st.text_input("Job Date", value=datetime.now().strftime("%B %d, %Y"), key="job_date")

        if st.button("✅ Start Job Documentation", key="start_job", use_container_width=True):
            if not job_name.strip() or not cont_name.strip() or not client_name.strip() or not address.strip():
                st.warning("Please fill in all required fields marked with *")
            else:
                st.session_state.contractor_job_info = {
                    "job_name": job_name.strip(), "contractor_name": cont_name.strip(),
                    "client_name": client_name.strip(), "address": address.strip(),
                    "job_type": job_type, "date": job_date,
                }
                st.session_state.contractor_photos = []
                st.session_state.job_started = True
                st.rerun()
    else:
        info = st.session_state.contractor_job_info
        st.markdown(f"""
            <div style="background:#2C2520; border:1px solid rgba(232,82,26,0.25);
                border-radius:8px; padding:0.75rem 1rem; margin-bottom:0.75rem;">
                <div style="font-size:13px; font-weight:700; color:#E8521A;">{info.get('job_name','')}</div>
                <div style="font-size:11px; color:#8A7E76; margin-top:3px;">
                    {info.get('contractor_name','')} → {info.get('client_name','')} &nbsp;|&nbsp;
                    {info.get('job_type','')} &nbsp;|&nbsp; {info.get('address','')}
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"**Step 2 — Add Photos** &nbsp;<span style='color:#8A7E76;font-size:12px;'>{len(st.session_state.contractor_photos)} documented</span>", unsafe_allow_html=True)

        stage_select = st.selectbox("Work Stage", STAGES, key="stage_select")
        stage_label = st.text_input("Enter custom stage name", key="custom_stage") if stage_select == "Custom Stage..." else stage_select

        doc_photo = st.file_uploader("Upload photo for this stage",
                                     type=["jpg", "jpeg", "png", "webp"], key="doc_uploader")
        if doc_photo:
            st.image(doc_photo, caption="Preview", width=200)

        if st.button("📸 Add Photo to Job Record", key="add_photo", use_container_width=True):
            if not doc_photo:
                st.warning("Please upload a photo first.")
            elif not stage_label or stage_label.strip() == "":
                st.warning("Please enter a stage name.")
            else:
                raw_bytes = doc_photo.read()
                timestamp = datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")
                with st.spinner("Analyzing and documenting..."):
                    try:
                        encoded, override = compress_and_encode(raw_bytes)
                        mt = get_media_type(doc_photo.type, override)
                        system = doc_system_prompt.format(
                            stage=stage_label, job_type=info.get("job_type", ""))
                        response = client.messages.create(
                            model="claude-opus-4-6", max_tokens=400, system=system,
                            messages=[{"role": "user", "content": [
                                {"type": "image", "source": {"type": "base64", "media_type": mt, "data": encoded}},
                                {"type": "text", "text": f"Document this photo for stage: {stage_label}"}
                            ]}]
                        )
                        analysis = "".join(block.text for block in response.content if hasattr(block, "text"))
                    except Exception as e:
                        analysis = f"AI analysis unavailable: {e}"
                st.session_state.contractor_photos.append({
                    "stage": stage_label, "timestamp": timestamp,
                    "bytes": raw_bytes, "analysis": analysis, "filename": doc_photo.name
                })
                st.success(f"✓ Added — {stage_label} — {timestamp}")
                st.rerun()

        if st.session_state.contractor_photos:
            st.markdown("---")
            st.markdown("**Documented Stages:**")
            for i, photo in enumerate(st.session_state.contractor_photos, 1):
                with st.expander(f"📸 Stage {i}: {photo['stage']} — {photo['timestamp']}"):
                    st.image(io.BytesIO(photo["bytes"]), width=280)
                    st.markdown(f"**AI Notes:** {photo['analysis']}")
                    if st.button(f"🗑️ Remove", key=f"remove_{i}"):
                        st.session_state.contractor_photos.pop(i - 1)
                        st.rerun()

            st.markdown("---")
            if st.button("📄 Generate & Download PDF Report", key="gen_pdf", use_container_width=True):
                with st.spinner("Building your PDF report..."):
                    try:
                        pdf_bytes = generate_pdf(
                            st.session_state.contractor_job_info,
                            st.session_state.contractor_photos
                        )
                        job_name_safe = st.session_state.contractor_job_info.get(
                            "job_name", "job").replace(" ", "_").replace("/", "-")
                        filename = f"HandyHelper_{job_name_safe}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        st.download_button(
                            label="⬇️ Download PDF Report", data=pdf_bytes,
                            file_name=filename, mime="application/pdf",
                            use_container_width=True
                        )
                        st.success("✓ Your PDF report is ready!")
                    except Exception as e:
                        st.error(f"PDF generation failed: {e}")

        st.markdown("")
        if st.button("🔄 Start New Job", key="reset_job"):
            st.session_state.job_started = False
            st.session_state.contractor_photos = []
            st.session_state.contractor_job_info = {}
            st.rerun()
