import anthropic
import streamlit as st
import base64
import io
import os
import tempfile
from datetime import datetime
from PIL import Image
from fpdf import FPDF

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
        .block-container {
            padding: 0.5rem 1rem 0.5rem 1rem !important;
            max-width: 100% !important;
        }
        [data-testid="stFileUploader"] label { display: none !important; }

        /* ── DEFAULT: all buttons reset ── */
        .stButton { position: relative !important; margin: 0 !important; z-index: auto !important; }
        .stButton > button {
            background: #2C2520 !important;
            color: #F5F0E8 !important;
            border: 1px solid rgba(232,82,26,0.2) !important;
            border-radius: 10px !important;
            width: 100% !important;
            min-height: 52px !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            padding: 0.35rem 0.5rem !important;
            line-height: 1.3 !important;
            transition: border-color 0.2s !important;
            white-space: pre-wrap !important;
        }
        .stButton > button:hover {
            background: #3D3530 !important;
            border-color: rgba(232,82,26,0.5) !important;
        }
        .stButton > button:focus { box-shadow: none !important; }

        /* Hide the nav trigger buttons completely */
        .hidden-nav { display: none !important; }

        /* ── SEND BUTTON: only inside input-wrap ── */
        .input-wrap { position: relative; margin-top: 0.75rem; }
        .input-wrap .stTextArea { margin: 0 !important; }
        .input-wrap .stButton {
            position: absolute !important;
            right: 8px !important;
            bottom: 8px !important;
            z-index: 10 !important;
        }
        .input-wrap .stButton > button {
            background: #E8521A !important;
            border: none !important;
            border-radius: 8px !important;
            width: 36px !important;
            height: 36px !important;
            min-height: unset !important;
            font-size: 18px !important;
            font-weight: 400 !important;
            padding: 0 !important;
            color: white !important;
        }
        .input-wrap .stButton > button:hover { background: #C43E0A !important; }

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

        /* ── TEXT AREA ── */
        .stTextArea label { display: none !important; }
        .stTextArea textarea {
            background: #2C2520 !important;
            color: #F5F0E8 !important;
            border: 1px solid rgba(232,82,26,0.3) !important;
            border-radius: 12px !important;
            font-size: 14px !important;
            resize: none !important;
            padding: 12px 50px 12px 16px !important;
            min-height: 70px !important;
            font-family: sans-serif !important;
        }
        .stTextArea textarea:focus {
            border-color: #E8521A !important;
            box-shadow: none !important;
        }
        .stTextArea textarea::placeholder { color: #8A7E76 !important; }

        /* ── FORM/CARD ELEMENTS ── */
        .stSelectbox label { color: #8A7E76 !important; font-size: 13px !important; }
        .stTextInput label { color: #8A7E76 !important; font-size: 13px !important; }
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
        div[data-testid="stHorizontalBlock"] {
            gap: 0.5rem !important;
            align-items: stretch !important;
        }
        .nav-sub {
            font-size: 9px;
            color: #8A7E76;
            text-align: center;
            margin: -6px 0 6px 0;
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
and needs an independent assessment before releasing payment to their contractor.

Analyze the photos carefully and provide a structured response with these exact sections:

OVERALL ASSESSMENT
A 2-3 sentence summary of the overall quality of the work visible in the photos.

WHAT LOOKS CORRECT
List specific things that appear properly done and professionally completed.

ITEMS TO VERIFY
List things the homeowner should ask the contractor about or inspect more closely 
before paying — things that need clarification but may not be problems.

RED FLAGS
List any specific concerns that may indicate improper, incomplete, or substandard work.
If none are visible say "No red flags visible in these photos."

PAYMENT RECOMMENDATION
One clear recommendation: Proceed with payment / Request corrections first / 
Get a professional inspection before paying.

DISCLAIMER
Always end with: This AI analysis is for guidance only and does not replace a 
professional inspection. Handy Helper is not liable for work quality assessments.

Be specific to what is actually visible in the photos. Be honest and direct.
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
    pdf.cell(0, 5, "Completed With Pride — Job Documentation Report", ln=True)
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
        pdf.cell(0, 7, str(value), ln=True)
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
        pdf.cell(0, 8, f"STAGE {i}: {photo['stage'].upper()}", ln=True)
        pdf.set_xy(15, 22)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(60, 5, f"Timestamp: {photo['timestamp']}", ln=False)
        pdf.cell(0, 5, f"Job: {job_info.get('job_name', '')}  |  Type: {job_info.get('job_type', '')}", ln=True)
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
        pdf.multi_cell(0, 5, photo.get("analysis", "No analysis available."))
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
        st.markdown("""
            <div style="padding:0.75rem; margin-bottom:0.5rem;
                background:linear-gradient(135deg,#2C2520 0%,#1A1612 100%);
                border:1px solid rgba(232,82,26,0.3);
                border-left:4px solid #E8521A;
                border-radius:8px; text-align:center;">
                <div style="font-size:18px; margin-bottom:0.25rem;">🔧</div>
                <div style="font-size:14px; font-weight:700; color:#F5F0E8; margin-bottom:0.25rem;">
                    Every Expert Was Once a Beginner
                </div>
                <div style="font-size:10px; color:#8A7E76; max-width:280px; margin:0 auto 0.4rem;">
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

        # HTML nav cards — perfectly aligned, no Streamlit column constraints
        st.markdown("""
            <div style="display:flex; gap:0.4rem; margin:0 0 0.5rem 0;">
                <div onclick="navClick('PWC_NAV')" style="
                    flex:1; background:#2C2520;
                    border:1px solid rgba(232,82,26,0.2); border-radius:10px;
                    padding:0.5rem; text-align:center; cursor:pointer;
                    transition:border-color 0.2s;"
                    onmouseover="this.style.borderColor='rgba(232,82,26,0.5)'"
                    onmouseout="this.style.borderColor='rgba(232,82,26,0.2)'"
                    ontouchstart="this.style.borderColor='rgba(232,82,26,0.5)'"
                    ontouchend="this.style.borderColor='rgba(232,82,26,0.2)'">
                    <div style="font-size:14px; margin-bottom:2px;">💰</div>
                    <div style="font-size:11px; font-weight:600; color:#F5F0E8; margin-bottom:2px;">Pay With Confidence</div>
                    <div style="font-size:9px; color:#8A7E76;">Verify work before you pay</div>
                </div>
                <div onclick="navClick('CWP_NAV')" style="
                    flex:1; background:#2C2520;
                    border:1px solid rgba(232,82,26,0.2); border-radius:10px;
                    padding:0.5rem; text-align:center; cursor:pointer;
                    transition:border-color 0.2s;"
                    onmouseover="this.style.borderColor='rgba(232,82,26,0.5)'"
                    onmouseout="this.style.borderColor='rgba(232,82,26,0.2)'"
                    ontouchstart="this.style.borderColor='rgba(232,82,26,0.5)'"
                    ontouchend="this.style.borderColor='rgba(232,82,26,0.2)'">
                    <div style="font-size:14px; margin-bottom:2px;">🛡️</div>
                    <div style="font-size:11px; font-weight:600; color:#F5F0E8; margin-bottom:2px;">Completed With Pride</div>
                    <div style="font-size:9px; color:#8A7E76;">Contractors — document your work</div>
                </div>
            </div>
            <script>
            function navClick(label) {
                var btns = document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    if (btns[i].textContent.trim() === label) {
                        btns[i].click();
                        return;
                    }
                }
            }
            </script>
        """, unsafe_allow_html=True)

        # Hidden Streamlit buttons triggered by HTML cards above
        st.markdown('<div class="hidden-nav">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("PWC_NAV", key="nav_verify"):
                st.session_state.current_section = "verify"
                st.rerun()
        with col2:
            if st.button("CWP_NAV", key="nav_doc"):
                st.session_state.current_section = "document"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

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
        st.success("✓ Photo attached! Type your question and tap ➤")
    elif st.session_state.pending_image is None:
        st.markdown(
            '<p style="font-size:11px; color:#8A7E76; margin:0.1rem 0 0;">📷 Upload a photo (optional)</p>',
            unsafe_allow_html=True
        )
    else:
        st.success("✓ Photo still attached! Type your question and tap ➤")

    st.markdown('<div class="input-wrap">', unsafe_allow_html=True)
    user_input = st.text_area(
        "question", placeholder="What project are we working on today?",
        height=70, key="chat_input", label_visibility="collapsed"
    )
    send = st.button("➤", key="send_btn")
    st.markdown('</div>', unsafe_allow_html=True)

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
        st.session_state.pending_image = None
        st.rerun()

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
                💰 Pay With Confidence
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
                        model="claude-opus-4-6", max_tokens=1500,
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
                🛡️ Completed With Pride
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
