import anthropic
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Handy Helper - DIY Services Assistant",
    page_icon="🔧",
    layout="centered"
)

# Title and description
st.title("Handy Helper - DIY Services Assistant")
st.caption("Your personal handyman guide. Ask me anything about DIY home repairs!")

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# System prompt
system_prompt = """
You are a helpful assistant named Handy Helper.

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
- If the chat falls under SAFETY RESTRICTIONS TIER 2 explain the risk and potential consequences to the user
  and strongly recommend three reputable local professionals that could do the project however if they wish to proceed
  have them click an acceptance of risk button that we retain for liability
  recommend the user contact a professional
"""

print("What project are we working on today? Type 'quit' to exit.\n")

# Main chat loop
while True:
    try:
        user_input = input("You: ")
    except KeyboardInterrupt:
        print("\nGoodbye!")
        with open("chat_history.json", "w") as f:
            json.dump(conversation, f)
        print("Conversation saved to chat_history.json")
        break

    if user_input.lower() == "quit":
        print("Goodbye!")
        with open("chat_history.json", "w") as f:
            json.dump(conversation, f)
        print("Conversation saved to chat_history.json")
        break

    conversation.append({"role": "user", "content": user_input})

    # Typing indicator
    print("Your Helper is thinking", end="", flush=True)
    for _ in range(3):
        time.sleep(0.5)
        print(".", end="", flush=True)
    print()

    # Keep looping until Claude gives a final text response
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
            print("Your Helper: Sorry, I am having trouble connecting. Please check your internet and try again.\n")
            conversation.pop()
            break
        except anthropic.RateLimitError:
            print("Your Helper: I am a little overwhelmed right now. Give me a moment and try again.\n")
            conversation.pop()
            break
        except anthropic.AuthenticationError:
            print("Your Helper: There is an issue with the API key. Please check your credentials.\n")
            exit()
        except Exception as e:
            print(f"Your Helper: Something unexpected went wrong: {e}\n")
            conversation.pop()
            break

        # Check if Claude wants to search the web
        if response.stop_reason == "tool_use":
            print("Your Helper is searching the web...\n")

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
            # Claude has a final answer, print it and break inner loop
            reply = ""
            for block in response.content:
                if hasattr(block, "text"):
                    reply += block.text

            conversation.append({"role": "assistant", "content": reply})
            print(f"Alex: {reply}\n")
            break

        # Display and save Alex reply
        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
