import os  # file path ke liye
import sys  # python ka path lene ke liye
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage  # message types
from utils import get_text  # model content ko text banane ke liye

MAX_ROUNDS = 5  # ek agent zyada se zyada 5 baar tool maang sakta hai

# Har agent ko sirf apne tools milte hain (least privilege)
AGENT_TOOLS = {
    "catalog": ["search_products", "check_stock"],
    "order": ["get_order_status"],
    "handoff": ["request_sales_rep"],
    "general": [],
}

ROUTER_PROMPT = """You are a ROUTER for a trade desk (cables, inverters, breakers, solar panels).
Read the new customer message (use recent chat for follow-ups) and reply with ONE word only:
- catalog: product search, availability, stock, lead time
- order: order status or tracking
- handoff: quote, price, discount, negotiation, or customer wants a human sales rep
- general: greetings, thanks, questions about what you can do, anything else
Reply with exactly one word."""

COMMON_RULES = """Rules: Never show prices. Never give exact stock numbers, use words only.
Never invent facts, use only tool results. If a tool returns an error, explain it to the customer in simple plain words.
Keep answers short and polite. Reply in the same language the customer uses."""

PROMPTS = {
    "catalog": "You are the Catalog Agent. Use search_products to find products and check_stock for availability of a SKU. " + COMMON_RULES,
    "order": "You are the Order Agent. To check an order you need BOTH the order ID and the email registered on the order. "
             "If either is missing, ASK the customer for it and do NOT call the tool. "
             "If the tool returns an error, say the order could not be found with these details and ask them to check the ID and email. "
             "Do not say which one was wrong. " + COMMON_RULES,
    "handoff": "You are the Handoff Agent. You cannot give quotes, prices or discounts. A human sales rep will do it. "
               "You need the customer's name and a contact (phone or email). If missing, ASK for it and do NOT call the tool. "
               "Then call request_sales_rep with a short request summary and share the reference number with the customer. " + COMMON_RULES,
    "general": "You are the General Agent of a trade desk for cables, inverters, breakers and solar panels. "
               "You can help with product availability, order status, and connecting to a sales rep for quotes. " + COMMON_RULES,
}


def build_llm():
    """Create the Gemini model."""
    from langchain_google_genai import ChatGoogleGenerativeAI  # yahan import taake tests bina Gemini chalein
    return ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", google_api_key=os.getenv("GEMINI_API_KEY"))  # key .env se


async def load_tools(db_path):
    """Start the MCP server (stdio) and load its tools. Tools are async only."""
    from langchain_mcp_adapters.client import MultiServerMCPClient  # MCP client
    server_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_server.py")  # server file ka path
    client = MultiServerMCPClient({  # server ki setting
        "trade": {"command": sys.executable, "args": [server_file], "transport": "stdio",
                  "env": {"DB_PATH": db_path}}})  # server ko same database batao
    return await client.get_tools()  # tools wapas karo


async def pick_agent(llm, message, history, counter):
    """Router: ask the model which agent should handle this message."""
    recent = "\n".join(f"{role}: {text}" for role, text in history[-4:])  # aakhri 4 messages
    messages = [SystemMessage(content=ROUTER_PROMPT),
                HumanMessage(content=f"Recent chat:\n{recent}\n\nNew message: {message}")]  # router ko sawal
    response = await llm.ainvoke(messages)  # model se pucho
    counter["llm_calls"] += 1  # model call gino
    answer = get_text(response.content).lower()  # jawab text mein
    for name in AGENT_TOOLS:  # har agent ka naam dekho
        if name in answer:  # jawab mein naam mila
            return name  # wohi agent chuno
    return "general"  # kuch samajh na aaye to general


async def run_agent(llm, tools, system_prompt, history, message, counter):
    """Tool loop: model asks for a tool, we run it, result goes back, until model answers."""
    model = llm.bind_tools(tools) if tools else llm  # tools ho to model ko do
    by_name = {t.name: t for t in tools}  # naam se tool dhoondne ke liye
    messages = [SystemMessage(content=system_prompt)]  # pehle system prompt
    for role, text in history:  # purani baat cheet
        messages.append(HumanMessage(content=text) if role == "user" else AIMessage(content=text))  # sahi type mein
    messages.append(HumanMessage(content=message))  # naya sawal
    for _ in range(MAX_ROUNDS):  # max rounds tak
        response = await model.ainvoke(messages)  # model se pucho
        counter["llm_calls"] += 1  # model call gino
        messages.append(response)  # jawab history mein daalo
        if not response.tool_calls:  # tool nahi maanga
            return get_text(response.content)  # final jawab wapas
        for call in response.tool_calls:  # har tool request ke liye
            tool = by_name.get(call["name"])  # tool dhoondo
            try:  # tool fail ho sakta hai
                result = await tool.ainvoke(call["args"]) if tool else '{"error": "Unknown tool"}'  # tool chalao (async)
            except Exception:  # koi bhi error
                result = '{"error": "Tool failed, please try again"}'  # safe error
            messages.append(ToolMessage(content=get_text(result), tool_call_id=call["id"]))  # result model ko wapas
    return "Sorry, I could not finish this request. Please try again or ask for a sales rep."  # rounds khatam


class TradeDeskBot:
    """Router + 4 agents. Keeps short chat history per session (in memory)."""

    def __init__(self, llm, all_tools, max_history=6, max_sessions=1000):
        self.llm = llm  # model
        self.tools = {t.name: t for t in all_tools}  # sab tools naam ke sath
        self.history = {}  # session id -> messages
        self.max_history = max_history  # kitne messages yaad rakhne hain
        self.max_sessions = max_sessions  # kitni sessions yaad rakhni hain

    async def chat(self, session_id, message):
        """Handle one customer message and return reply, agent name and LLM call count."""
        counter = {"llm_calls": 0}  # model calls ka hisab
        history = self.history.get(session_id, [])  # is session ki history
        agent = await pick_agent(self.llm, message, history, counter)  # router agent chunta hai
        tools = [self.tools[n] for n in AGENT_TOOLS[agent] if n in self.tools]  # sirf us agent ke tools
        reply = await run_agent(self.llm, tools, PROMPTS[agent], history, message, counter)  # agent kaam kare
        history = (history + [("user", message), ("assistant", reply)])[-self.max_history:]  # history update
        self.history.pop(session_id, None)  # purani entry hatao (order theek rakhne ke liye)
        self.history[session_id] = history  # nayi history rakho
        while len(self.history) > self.max_sessions:  # bohat sessions ho gayi
            self.history.pop(next(iter(self.history)))  # sab se purani hatao
        return {"reply": reply, "agent": agent, "llm_calls": counter["llm_calls"]}  # nateeja
