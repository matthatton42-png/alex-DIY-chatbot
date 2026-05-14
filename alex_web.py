import anthropic
import json
import time
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Handy Helper - DIY Services Assistant",
    page_icon="🔧",
    layout="centered"
)

# Title and description
st.title("🔧 Handy Helper - DIY Services Assistant")
st.caption("Your personal handyman guide. Ask me anything about DIY home repairs!")

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

CATEGORIES:
- Carpentry
- Doors
- Electrical
- Flooring
- Leaks
- Lighting
- Plumbing
- Trim
- Windows
- Generators
- Decks and Porches
- Garage Doors
- Siding
- Roofing and Gutters
- Drywall
- Furniture Assembly
- Appliance Repair
- Pest Control
- Painting
- Driveway Sealing
- Water Heater
- Furnace
- Air Conditioner
- HVAC
- Security
- Propane
- Natural Gas
- Foundation Repair
- Landscaping
- Tile and Grout
- Smart Home Devices
- Garbage Disposal
- Dishwasher
- Fencing
- Weatherproofing
- Carbon Monoxide Detectors
- Smoke Detectors

SAFETY RESTRICTIONS TIER 1:
- Power tools
- Heavy equipment
- Fire hazards
- Safety concerns

SAFETY RESTRICTIONS TIER 2:
- Inside electrical panel
- Inside electrical meter base
- Ladder usage
- Wall removal

BUSINESS INFO:
- Live on call service technician available Monday to Friday 8am to 6pm, Saturday 9am to 1pm
- Live technician assistance is requested and/or offered through the chatbot and once accepted
  billing will be presented prior to deployment

RULES:
- Only answer questions based on these CATEGORIES
- If someone asks something unrelated, politely redirect to CATEGORIES
- If the chat falls under SAFETY RESTRICTIONS TIER 1 verify that the user is confident in
  moving forward and offer three reputable local professionals that could do the project
- If the chat falls under SAFETY RESTRICTIONS TIER 2 explain the risk and potential consequences
  to the user and strongly recommend three reputable local professionals that could do the project
  however if they wish to proceed have them acknowledge the risk before continuing
"""

# Initialize chat history in session
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input box at the bottom
if user_input := st.chat_input("What project are we working on today?"):

    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Show Handy Helper thinking
    with st.chat_message("assistant"):
        with st.spinner("Your Helper is thinking..."):

            # Build conversation for API
            conversation = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]

            # Keep looping until we get a final response
            while True:
                try:
                    response = client.messages.create(
                        model="claude-opus-4-6",
                        max_tokens=1024,
                        system=system_prompt,
                        tools=[{"type": "web_search_20250305", "name": "web_search"}],
                        messages=conversation
                    )
                except anthropic.APIConnectionError:
                    st.error("Sorry, I am having trouble connecting. Please check your internet and try again.")
                    st.stop()
                except anthropic.RateLimitError:
                    st.error("I am a little overwhelmed right now. Give me a moment and try again.")
                    st.stop()
                except anthropic.AuthenticationError:
                    st.error("There is an issue with the API key. Please check your credentials.")
                    st.stop()
                except Exception as e:
                    st.error(f"Something unexpected went wrong: {e}")
                    st.stop()

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

        # Display and save reply
        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
