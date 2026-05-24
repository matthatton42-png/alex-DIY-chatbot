import anthropic
import streamlit as st
import base64

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
        h1 { display: none; }
        .block-container {
            padding-top: 0.75rem !important;
            padding-bottom: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
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

# System prompt
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

def encode_image(uploaded_file):
    return base64.standard_b64encode(uploaded_file.read()).decode("utf-8")

def get_image_media_type(uploaded_file):
    file_type = uploaded_file.type
    if file_type in ["image/jpeg", "image/jpg"]:
        return "image/jpeg"
    elif file_type == "image/png":
        return "image/png"
    elif file_type == "image/gif":
        return "image/gif"
    elif file_type == "image/webp":
        return "image/webp"
    return "image/jpeg"

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], list):
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    st.markdown(block["text"])
                elif isinstance(block, dict) and block.get("type") == "image_url":
                    st.image(block["url"], caption="Uploaded photo", width=300)
        else:
            st.markdown(message["content"])

# Photo upload
uploaded_file = st.file_uploader(
    "📷 Upload a photo (optional)",
    type=["jpg", "jpeg", "png", "webp"],
    help="Upload a photo and Handy Helper will analyze it"
)

if uploaded_file:
    st.image(uploaded_file, caption="Your photo", width=200)
    st.success("Photo ready! Ask your question below.")

# Motivational banner
if not st.session_state.messages:
    st.markdown("""
        <div style="
            margin: 2rem 0;
            padding: 1.5rem;
            background: linear-gradient(135deg, #2C2520 0%, #1A1612 100%);
            border: 1px solid rgba(232,82,26,0.3);
            border-left: 4px solid #E8521A;
            border-radius: 8px;
            text-align: center;">
            <div style="
                font-size: 28px;
                margin-bottom: 0.75rem;">🔧</div>
            <div style="
                font-family: sans-serif;
                font-size: 20px;
                font-weight: 700;
                color: #F5F0E8;
                line-height: 1.3;
                margin-bottom: 0.75rem;
                letter-spacing: 0.5px;">
                Every Expert Was Once a Beginner
            </div>
            <div style="
                font-size: 13px;
                color: #8A7E76;
                line-height: 1.6;
                max-width: 320px;
                margin: 0 auto 1rem;">
                You already have what it takes. Ask me anything about your project and let's get it done together.
            </div>
            <div style="
                display: flex;
                justify-content: center;
                gap: 1rem;
                flex-wrap: wrap;">
                <span style="font-size: 11px; color: #E8521A; font-family: monospace; letter-spacing: 1px;">37+ CATEGORIES</span>
                <span style="font-size: 11px; color: #8A7E76;">•</span>
                <span style="font-size: 11px; color: #E8521A; font-family: monospace; letter-spacing: 1px;">PHOTO ANALYSIS</span>
                <span style="font-size: 11px; color: #8A7E76;">•</span>
                <span style="font-size: 11px; color: #E8521A; font-family: monospace; letter-spacing: 1px;">FREE 24/7</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Chat input
if user_input := st.chat_input("What project are we working on today?"):
    if uploaded_file:
        uploaded_file.seek(0)
        image_data = encode_image(uploaded_file)
        media_type = get_image_media_type(uploaded_file)
        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data
                }
            },
            {
                "type": "text",
                "text": user_input
            }
        ]
        display_content = [
            {"type": "image_url", "url": uploaded_file.name},
            {"type": "text", "text": user_input}
        ]
    else:
        user_content = user_input
        display_content = user_input

    with st.chat_message("user"):
        if uploaded_file:
            st.image(uploaded_file, caption="Your photo", width=200)
        st.markdown(user_input)

    st.session_state.messages.append({
        "role": "user",
        "content": display_content
    })

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
