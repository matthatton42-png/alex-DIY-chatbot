import anthropic
import streamlit as st
import base64
import io
from PIL import Image

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
            padding-top: 0.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 1rem !important;
        }
        /* Chat input container */
        .chat-input-wrapper {
            position: relative;
            margin-top: 0.75rem;
        }
        .chat-input-wrapper textarea {
            width: 100% !important;
            background: #2C2520 !important;
            color: #F5F0E8 !important;
            border: 1px solid rgba(232,82,26,0.3) !important;
            border-radius: 12px !important;
            padding: 12px 50px 12px 16px !important;
            font-size: 14px !important;
            font-family: sans-serif !important;
            resize: none !important;
            outline: none !important;
            box-sizing: border-box !important;
            line-height: 1.5 !important;
        }
        .chat-input-wrapper textarea:focus {
            border-color: #E8521A !important;
        }
        .chat-input-wrapper textarea::placeholder {
            color: #8A7E76 !important;
        }
        .send-btn {
            position: absolute !important;
            right: 10px !important;
            bottom: 10px !important;
            background: #E8521A !important;
            border: none !important;
            border-radius: 8px !important;
            width: 34px !important;
            height: 34px !important;
            cursor: pointer !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            color: white !important;
            font-size: 16px !important;
            transition: background 0.2s !important;
        }
        .send-btn:hover {
            background: #C43E0A !important;
        }
        /* Hide Streamlit text area label and default styling */
        .stTextArea { margin: 0 !important; }
        .stTextArea label { display: none !important; }
        .stTextArea textarea {
            background: #2C2520 !important;
            color: #F5F0E8 !important;
            border: 1px solid rgba(232,82,26,0.3) !important;
            border-radius: 12px !important;
            font-size: 14px !important;
            resize: none !important;
            padding-right: 50px !important;
        }
        .stTextArea textarea:focus {
            border-color: #E8521A !important;
            box-shadow: none !important;
        }
        /* Send button styling */
        .stButton { margin: 0 !important; }
        .stButton > button {
            background: #E8521A !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-size: 18px !important;
            padding: 0.4rem 0.75rem !important;
            line-height: 1 !important;
            min-height: 36px !important;
        }
        .stButton > button:hover {
            background: #C43E0A !important;
        }
        /* File uploader */
        [data-testid="stFileUploader"] label { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# Initialize Anthropic client
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)
except KeyError:
    st.error("API key not found.")
    st.stop()
except Exception as e:
    st.error(f"Failed to initialize: {e}")
    st.stop()

system_prompt = """
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
- Smoke Detectors

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

def compress_and_encode(file_bytes, max_size_mb=4):
    """Compress image to under max_size_mb and return base64"""
    MAX = max_size_mb * 1024 * 1024

    if len(file_bytes) <= MAX:
        return base64.standard_b64encode(file_bytes).decode("utf-8"), None

    try:
        img = Image.open(io.BytesIO(file_bytes))
    except Exception:
        return base64.standard_b64encode(file_bytes[:MAX]).decode("utf-8"), None

    # Convert to RGB
    if img.mode in ("RGBA", "P", "LA", "CMYK"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        try:
            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img)
        except Exception:
            bg.paste(img)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize large images first — mobile photos can be huge
    max_dimension = 1920
    if img.width > max_dimension or img.height > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    # Try quality reduction
    for quality in [85, 70, 55, 40, 25]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"

    # Try resizing further
    for scale in [0.75, 0.6, 0.5, 0.4, 0.3]:
        w = max(100, int(img.width * scale))
        h = max(100, int(img.height * scale))
        resized = img.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=40, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"

    # Absolute last resort
    img.thumbnail((640, 640), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=30)
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

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_image" not in st.session_state:
    st.session_state.pending_image = None

# Motivational banner
if not st.session_state.messages:
    st.markdown("""
        <div style="margin:0.25rem 0 0.75rem 0; padding:1rem;
            background:linear-gradient(135deg,#2C2520 0%,#1A1612 100%);
            border:1px solid rgba(232,82,26,0.3);
            border-left:4px solid #E8521A; border-radius:8px; text-align:center;">
            <div style="font-size:20px; margin-bottom:0.35rem;">🔧</div>
            <div style="font-size:15px; font-weight:700; color:#F5F0E8; margin-bottom:0.35rem;">
                Every Expert Was Once a Beginner
            </div>
            <div style="font-size:11px; color:#8A7E76; max-width:280px; margin:0 auto 0.5rem;">
                Ask me anything about your project and let's get it done together.
            </div>
            <div style="display:flex; justify-content:center; gap:0.6rem;">
                <span style="font-size:9px; color:#E8521A; font-family:monospace;">37+ CATEGORIES</span>
                <span style="font-size:9px; color:#8A7E76;">•</span>
                <span style="font-size:9px; color:#E8521A; font-family:monospace;">PHOTO ANALYSIS</span>
                <span style="font-size:9px; color:#8A7E76;">•</span>
                <span style="font-size:9px; color:#E8521A; font-family:monospace;">FREE 24/7</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], list):
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    st.markdown(block["text"])
        else:
            st.markdown(message["content"])

# Photo upload
uploaded_file = st.file_uploader(
    "photo",
    type=["jpg", "jpeg", "png", "webp"],
    label_visibility="collapsed"
)

if uploaded_file is not None:
    raw_bytes = uploaded_file.read()
    encoded, override = compress_and_encode(raw_bytes)
    media_type = get_media_type(uploaded_file.type, override)
    st.session_state.pending_image = {
        "data": encoded,
        "media_type": media_type,
        "name": uploaded_file.name,
        "bytes": raw_bytes
    }
    st.image(io.BytesIO(raw_bytes), caption="📷 Photo ready!", width=160)
    st.success("✓ Photo attached! Type your question and tap ➤")
else:
    if "last_file" not in st.session_state or st.session_state.get("last_file") != uploaded_file:
        st.session_state.pending_image = None
    st.markdown(
        '<p style="font-size:12px; color:#8A7E76; margin:0.25rem 0 0.5rem 0;">📷 Upload a photo (optional)</p>',
        unsafe_allow_html=True
    )

st.session_state.last_file = uploaded_file

# Input row — text area + send button side by side
col1, col2 = st.columns([9, 1])

with col1:
    user_input = st.text_area(
        "msg",
        placeholder="What project are we working on today?",
        height=80,
        key="chat_input",
        label_visibility="collapsed"
    )

with col2:
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    send = st.button("➤", key="send_btn", help="Send message")

# Process on send
if send and user_input and user_input.strip():
    prompt = user_input.strip()
    pending = st.session_state.pending_image

    if pending:
        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": pending["media_type"],
                    "data": pending["data"]
                }
            },
            {"type": "text", "text": prompt}
        ]
        display_content = [{"type": "text", "text": f"[Photo attached] {prompt}"}]
    else:
        user_content = prompt
        display_content = prompt

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": display_content})

    # Build conversation
    conversation = []
    for msg in st.session_state.messages[:-1]:
        if isinstance(msg["content"], list):
            text = " ".join(b["text"] for b in msg["content"] if isinstance(b, dict) and b.get("type") == "text")
            conversation.append({"role": msg["role"], "content": text})
        else:
            conversation.append({"role": msg["role"], "content": msg["content"]})
    conversation.append({"role": "user", "content": user_content})

    # Get response
    with st.chat_message("assistant"):
        with st.spinner("Handy Helper is thinking..."):
            try:
                while True:
                    response = client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=1024,
                        system=system_prompt,
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
                        reply = "".join(block.text for block in response.content if hasattr(block, "text"))
                        break
            except Exception as e:
                reply = f"Something went wrong: {e}"

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

    st.session_state.pending_image = None
    st.rerun()
