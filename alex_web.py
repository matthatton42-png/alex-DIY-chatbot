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
            padding: 1rem !important;
            max-width: 100% !important;
        }
        [data-testid="stFileUploader"] label { display: none !important; }

        /* Center the whole page content vertically */
        .center-wrap {
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 80vh;
            gap: 0.75rem;
        }

        /* Chat input with button inside */
        .hh-form {
            display: flex;
            align-items: flex-end;
            background: #2C2520;
            border: 1px solid rgba(232,82,26,0.3);
            border-radius: 12px;
            padding: 8px 8px 8px 12px;
            gap: 8px;
        }
        .hh-form:focus-within { border-color: #E8521A; }
        .hh-textarea {
            flex: 1;
            background: transparent;
            border: none;
            outline: none;
            color: #F5F0E8;
            font-size: 14px;
            font-family: sans-serif;
            resize: none;
            line-height: 1.5;
            min-height: 52px;
            max-height: 120px;
        }
        .hh-textarea::placeholder { color: #8A7E76; }
        .hh-send {
            background: #E8521A;
            border: none;
            border-radius: 8px;
            width: 36px;
            height: 36px;
            min-width: 36px;
            cursor: pointer;
            color: white;
            font-size: 16px;
            flex-shrink: 0;
        }
        .hh-send:hover { background: #C43E0A; }

        /* Hide the st.text_input used for message passing */
        [data-testid="stTextInput"] {
            position: absolute !important;
            opacity: 0 !important;
            height: 0 !important;
            pointer-events: none !important;
            overflow: hidden !important;
        }
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
    MAX = max_size_mb * 1024 * 1024
    if len(file_bytes) <= MAX:
        return base64.standard_b64encode(file_bytes).decode("utf-8"), None
    try:
        img = Image.open(io.BytesIO(file_bytes))
    except Exception:
        return base64.standard_b64encode(file_bytes[:MAX]).decode("utf-8"), None
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
    if img.width > 1920 or img.height > 1920:
        img.thumbnail((1920, 1920), Image.LANCZOS)
    for quality in [85, 70, 55, 40, 25]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"
    for scale in [0.75, 0.6, 0.5, 0.4, 0.3]:
        w = max(100, int(img.width * scale))
        h = max(100, int(img.height * scale))
        resized = img.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=40, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"
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
if "submitted_text" not in st.session_state:
    st.session_state.submitted_text = ""

# Chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], list):
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    st.markdown(block["text"])
        else:
            st.markdown(message["content"])

# Opening layout — centered when no messages
st.markdown('<div class="center-wrap">', unsafe_allow_html=True)

# Motivational banner
if not st.session_state.messages:
    st.markdown("""
        <div style="padding:1.25rem;
            background:linear-gradient(135deg,#2C2520 0%,#1A1612 100%);
            border:1px solid rgba(232,82,26,0.3);
            border-left:4px solid #E8521A;
            border-radius:8px; text-align:center;">
            <div style="font-size:22px; margin-bottom:0.4rem;">🔧</div>
            <div style="font-size:16px; font-weight:700; color:#F5F0E8; margin-bottom:0.4rem;">
                Every Expert Was Once a Beginner
            </div>
            <div style="font-size:11px; color:#8A7E76; max-width:280px; margin:0 auto 0.6rem;">
                Ask me anything about your project and let's get it done together.
            </div>
            <div style="display:flex; justify-content:center; gap:0.75rem;">
                <span style="font-size:9px; color:#E8521A; font-family:monospace;">37+ CATEGORIES</span>
                <span style="font-size:9px; color:#8A7E76;">•</span>
                <span style="font-size:9px; color:#E8521A; font-family:monospace;">PHOTO ANALYSIS</span>
                <span style="font-size:9px; color:#8A7E76;">•</span>
                <span style="font-size:9px; color:#E8521A; font-family:monospace;">FREE 24/7</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

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
    st.image(io.BytesIO(raw_bytes), caption="📷 Photo ready!", width=150)
    st.success("✓ Photo attached! Type your question and tap ➤")
elif st.session_state.pending_image is None:
    st.markdown(
        '<p style="font-size:11px; color:#8A7E76; margin:0.1rem 0 0;">📷 Upload a photo (optional)</p>',
        unsafe_allow_html=True
    )
else:
    st.success("✓ Photo still attached! Type your question and tap ➤")

# Custom HTML chat input with ➤ inside
st.markdown("""
    <div class="hh-form">
        <textarea id="hh-input" class="hh-textarea"
            placeholder="What project are we working on today?"
            rows="2"></textarea>
        <button class="hh-send" onclick="sendMessage()">&#10148;</button>
    </div>
    <script>
    function sendMessage() {
        var text = document.getElementById('hh-input').value.trim();
        if (!text) return;
        var hiddenInput = window.parent.document.querySelector('[data-testid="stTextInput"] input');
        if (hiddenInput) {
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(hiddenInput, text);
            hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
            document.getElementById('hh-input').value = '';
        }
    }
    document.getElementById('hh-input').addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    </script>
""", unsafe_allow_html=True)

# Invisible Streamlit input that receives the message
user_msg = st.text_input("h", key="hidden_msg", label_visibility="collapsed")

st.markdown('</div>', unsafe_allow_html=True)

# Process message
if user_msg and user_msg.strip() and user_msg.strip() != st.session_state.submitted_text:
    st.session_state.submitted_text = user_msg.strip()
    prompt = user_msg.strip()
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

    conversation = []
    for msg in st.session_state.messages[:-1]:
        if isinstance(msg["content"], list):
            text = " ".join(b["text"] for b in msg["content"] if isinstance(b, dict) and b.get("type") == "text")
            conversation.append({"role": msg["role"], "content": text})
        else:
            conversation.append({"role": msg["role"], "content": msg["content"]})
    conversation.append({"role": "user", "content": user_content})

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
