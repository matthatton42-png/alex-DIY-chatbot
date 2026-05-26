import anthropic
import streamlit as st
import base64
import io
from PIL import Image

st.set_page_config(
    page_title="Handy Helper - DIY Services Assistant",
    page_icon="🔧",
    layout="centered"
)

st.markdown("""
    <style>
        #MainMenu { visibility: hidden; }
        header { visibility: hidden; }
        footer { visibility: hidden; }
        .stDeployButton { display: none; }
        .stAppToolbar { display: none; }
        [data-testid="stToolbar"] { display: none; }
        [data-testid="stDecoration"] { display: none; }
        [data-testid="stStatusWidget"] { display: none; }
        [data-testid="stHeader"] { display: none; }
        [data-testid="stBottom"] { display: none !important; }
        [data-testid="stBottomBlockContainer"] { display: none !important; }
        h1 { display: none; }
        .block-container {
            padding-top: 0.75rem !important;
            padding-bottom: 5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }
        [data-testid="stChatInput"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
        [data-testid="stChatInputContainer"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
        section[data-testid="stChatInput"] {
            display: block !important;
        }
    </style>
""", unsafe_allow_html=True)

# Initialize Anthropic client securely
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)
except KeyError:
    st.error("API key not found. Please check your Streamlit secrets settings.")
    st.stop()
except Exception as e:
    st.error(f"Failed to initialize client: {e}")
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

def compress_and_encode(file_bytes):
    """Compress image bytes to under 4MB and return base64 string"""
    MAX = 4 * 1024 * 1024

    if len(file_bytes) <= MAX:
        return base64.standard_b64encode(file_bytes).decode("utf-8"), None

    img = Image.open(io.BytesIO(file_bytes))

    # Convert to RGB
    if img.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            bg.paste(img, mask=img.split()[3])
        else:
            bg.paste(img)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Try quality reduction
    for quality in [80, 65, 50, 35]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"

    # Try resizing
    for scale in [0.75, 0.5, 0.35, 0.25]:
        resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=50, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX:
            return base64.standard_b64encode(data).decode("utf-8"), "image/jpeg"

    # Last resort
    img.thumbnail((800, 800), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=40)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"

def get_media_type(uploaded_file, override_type=None):
    if override_type:
        return override_type
    ft = uploaded_file.type
    if ft in ["image/jpeg", "image/jpg"]:
        return "image/jpeg"
    elif ft == "image/png":
        return "image/png"
    elif ft == "image/gif":
        return "image/gif"
    elif ft == "image/webp":
        return "image/webp"
    return "image/jpeg"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "image_data" not in st.session_state:
    st.session_state.image_data = None
if "image_type" not in st.session_state:
    st.session_state.image_type = None
if "image_name" not in st.session_state:
    st.session_state.image_name = None

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
    "📷 Upload a photo (optional)",
    type=["jpg", "jpeg", "png", "webp"],
    help="Upload a photo and Handy Helper will analyze it"
)

# Process uploaded file and store in session state
if uploaded_file is not None:
    raw_bytes = uploaded_file.read()
    encoded, override_type = compress_and_encode(raw_bytes)
    st.session_state.image_data = encoded
    st.session_state.image_type = get_media_type(uploaded_file, override_type)
    st.session_state.image_name = uploaded_file.name
    st.image(io.BytesIO(raw_bytes), caption="Your photo", width=200)
    st.success("Photo ready! Type your question below.")
else:
    st.session_state.image_data = None
    st.session_state.image_type = None
    st.session_state.image_name = None

# Motivational banner
if not st.session_state.messages:
    st.markdown("""
        <div style="
            margin: 1.5rem 0;
            padding: 1.25rem;
            background: linear-gradient(135deg, #2C2520 0%, #1A1612 100%);
            border: 1px solid rgba(232,82,26,0.3);
            border-left: 4px solid #E8521A;
            border-radius: 8px;
            text-align: center;">
            <div style="font-size: 24px; margin-bottom: 0.5rem;">🔧</div>
            <div style="font-size: 18px; font-weight: 700; color: #F5F0E8; margin-bottom: 0.5rem;">
                Every Expert Was Once a Beginner
            </div>
            <div style="font-size: 12px; color: #8A7E76; max-width: 300px; margin: 0 auto 0.75rem;">
                Ask me anything about your project and let's get it done together.
            </div>
            <div style="display: flex; justify-content: center; gap: 0.75rem; flex-wrap: wrap;">
                <span style="font-size: 10px; color: #E8521A; font-family: monospace;">37+ CATEGORIES</span>
                <span style="font-size: 10px; color: #8A7E76;">•</span>
                <span style="font-size: 10px; color: #E8521A; font-family: monospace;">PHOTO ANALYSIS</span>
                <span style="font-size: 10px; color: #8A7E76;">•</span>
                <span style="font-size: 10px; color: #E8521A; font-family: monospace;">FREE 24/7</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Chat input — always visible
user_input = st.chat_input("What project are we working on today?")

if user_input:
    # Build message content
    if st.session_state.image_data:
        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": st.session_state.image_type,
                    "data": st.session_state.image_data
                }
            },
            {
                "type": "text",
                "text": user_input
            }
        ]
        display_content = [
            {"type": "text", "text": f"[Photo: {st.session_state.image_name}] {user_input}"}
        ]
    else:
        user_content = user_input
        display_content = user_input

    # Show user message
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append({
        "role": "user",
        "content": display_content
    })

    # Build conversation history
    conversation = []
    for msg in st.session_state.messages[:-1]:
        if isinstance(msg["content"], list):
            text_only = " ".join(
                block["text"] for block in msg["content"]
                if isinstance(block, dict) and block.get("type") == "text"
            )
            conversation.append({"role": msg["role"], "content": text_only})
        else:
            conversation.append({"role": msg["role"], "content": msg["content"]})

    conversation.append({"role": "user", "content": user_content})

    # Get response
    with st.chat_message("assistant"):
        with st.spinner("Handy Helper is analyzing..."):
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
                        conversation.append({
                            "role": "assistant",
                            "content": response.content
                        })
                        tool_results = []
                        for block in response.content:
                            if block.type == "tool_use":
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": block.input.get("query", "")
                                })
                        conversation.append({
                            "role": "user",
                            "content": tool_results
                        })
                    else:
                        reply = ""
                        for block in response.content:
                            if hasattr(block, "text"):
                                reply += block.text
                        break

            except Exception as e:
                reply = f"Something went wrong: {e}"

        st.markdown(reply)
        st.session_state.messages.append({
            "role": "assistant",
            "content": reply
        })

    # Clear image after sending
    st.session_state.image_data = None
    st.session_state.image_type = None
    st.session_state.image_name = None
