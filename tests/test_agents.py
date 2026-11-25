import sys  # modules ke liye
import types  # fake module banane ke liye
import unittest  # test framework

try:  # asli langchain ho to wohi use karo
    import langchain_core.messages  # noqa: F401
except ImportError:  # warna chhote fake messages banao (taake test bina install chalein)
    class _Msg:
        def __init__(self, content="", tool_calls=None, tool_call_id=None):
            self.content = content  # text
            self.tool_calls = tool_calls or []  # tool requests
            self.tool_call_id = tool_call_id  # tool id
    fake = types.ModuleType("langchain_core.messages")  # fake module
    for _name in ("SystemMessage", "HumanMessage", "AIMessage", "ToolMessage"):  # 4 classes
        setattr(fake, _name, type(_name, (_Msg,), {}))  # class banao
    sys.modules["langchain_core"] = types.ModuleType("langchain_core")  # parent module
    sys.modules["langchain_core.messages"] = fake  # messages module

from langchain_core.messages import AIMessage  # noqa: E402  (asli ya fake)
import agents  # noqa: E402  hamara code

# fake model tool ko ye args deta hai
TOOL_ARGS = {
    "search_products": {"query": "cable"},
    "check_stock": {"sku": "CAB-4MM"},
    "get_order_status": {"order_id": "PO-1001", "customer_email": "ali@example.com"},
    "request_sales_rep": {"customer_name": "Ali", "contact": "0300", "request_summary": "Quote"},
}


class FakeTool:
    """Fake MCP tool: records calls."""
    def __init__(self, name, log):
        self.name = name  # tool ka naam
        self.log = log  # calls ki list

    async def ainvoke(self, args):
        self.log.append(self.name)  # call likho
        return '{"ok": true}'  # fake result


class FakeBound:
    """Fake model with tools attached."""
    def __init__(self, llm, names):
        self.llm = llm  # asli fake model
        self.names = names  # is agent ko mile hue tools
        llm.offered.append(set(names))  # yaad rakho kaunse tools diye gaye

    async def ainvoke(self, messages):
        self.llm.calls += 1  # call gino
        if type(messages[-1]).__name__ == "ToolMessage" and not self.llm.always_tool:  # tool result aa gaya
            return AIMessage(content="Final answer")  # final jawab
        if self.llm.always_tool:  # loop test ke liye: hamesha tool maango
            return AIMessage(content="", tool_calls=[{"name": self.names[0], "args": TOOL_ARGS[self.names[0]], "id": "c1"}])
        text = messages[-1].content.lower()  # customer ka text
        name = self.names[0]  # pehla tool
        if "check_stock" in self.names and ("stock" in text or "available" in text):  # stock ka sawal
            name = "check_stock"  # stock tool
        return AIMessage(content="", tool_calls=[{"name": name, "args": TOOL_ARGS[name], "id": "c1"}])


class FakeLLM:
    """Fake Gemini: router uses simple keywords."""
    def __init__(self, always_tool=False):
        self.calls = 0  # model calls
        self.offered = []  # diye gaye tools
        self.always_tool = always_tool  # loop test flag

    def bind_tools(self, tools):
        return FakeBound(self, [t.name for t in tools])  # tools wala model

    async def ainvoke(self, messages):
        self.calls += 1  # call gino
        if "ROUTER" in messages[0].content:  # router ka sawal
            text = messages[-1].content.lower().split("new message:")[-1]  # sirf naya message
            if any(k in text for k in ("quote", "price", "discount", "negotiat", "human", "sales rep")):
                return AIMessage(content="handoff")  # handoff
            if any(k in text for k in ("order", "po-")):
                return AIMessage(content="order")  # order
            if any(k in text for k in ("stock", "available", "cable", "inverter", "breaker", "panel", "do you have")):
                return AIMessage(content="catalog")  # catalog
            return AIMessage(content="general")  # baqi sab
        return AIMessage(content="Hello, how can I help?")  # general agent ka jawab


# (sawal, expected agent, expected tool)
CASES = [
    ("Do you have 4mm cable?", "catalog", "search_products"),
    ("Show me solar panels", "catalog", "search_products"),
    ("I need MCB breakers", "catalog", "search_products"),
    ("Which inverters do you sell?", "catalog", "search_products"),
    ("Is the 10kW inverter in stock?", "catalog", "check_stock"),
    ("Is 6mm cable available?", "catalog", "check_stock"),
    ("Check stock of solar panel 550W", "catalog", "check_stock"),
    ("Do you have breaker 63A in stock", "catalog", "check_stock"),
    ("Where is my order PO-1001?", "order", "get_order_status"),
    ("Track order PO-1002 ali@example.com", "order", "get_order_status"),
    ("Order status please", "order", "get_order_status"),
    ("What is the delivery status of my order?", "order", "get_order_status"),
    ("Give me a quote for 100 panels", "handoff", "request_sales_rep"),
    ("What is the price of the 5kW inverter?", "handoff", "request_sales_rep"),
    ("Can I get a discount on cables?", "handoff", "request_sales_rep"),
    ("I want to negotiate the rate", "handoff", "request_sales_rep"),
    ("I want to talk to a human", "handoff", "request_sales_rep"),
    ("Please send me the best price", "handoff", "request_sales_rep"),
    ("Quote for 500 meters cable", "handoff", "request_sales_rep"),
    ("I need a sales rep", "handoff", "request_sales_rep"),
    ("Hello", "general", None),
    ("What can you help me with?", "general", None),
    ("Thanks!", "general", None),
    ("Who are you?", "general", None),
    ("Tell me a joke", "general", None),
    ("What is your address?", "general", None),
]


def make_bot(llm=None):
    """Build a bot with fake model and fake tools."""
    log = []  # tool calls ki list
    tools = [FakeTool(n, log) for n in TOOL_ARGS]  # 4 fake tools
    return agents.TradeDeskBot(llm or FakeLLM(), tools), log  # bot aur log


class AgentsTest(unittest.IsolatedAsyncioTestCase):
    async def test_routing_and_tools(self):
        for query, agent, tool in CASES:  # har case
            with self.subTest(query=query):  # case ka naam
                bot, log = make_bot()  # naya bot
                result = await bot.chat("session-0001", query)  # sawal bhejo
                self.assertEqual(result["agent"], agent)  # sahi agent?
                self.assertEqual(log, [tool] if tool else [])  # sahi tool (ya koi nahi)

    async def test_least_privilege(self):
        llm = FakeLLM()  # fake model
        bot, _ = make_bot(llm)  # bot
        await bot.chat("session-0001", "Where is my order PO-1001?")  # order agent
        self.assertEqual(llm.offered, [{"get_order_status"}])  # sirf apna tool mila

    async def test_llm_call_count(self):
        bot, _ = make_bot()  # bot
        self.assertEqual((await bot.chat("session-0001", "Show me cables"))["llm_calls"], 3)  # router + 2
        self.assertEqual((await bot.chat("session-0002", "Hello"))["llm_calls"], 2)  # router + 1

    async def test_history_is_capped(self):
        bot, _ = make_bot()  # bot
        for _ in range(5):  # 5 baar baat karo
            await bot.chat("session-0001", "Hello")  # sawal
        self.assertEqual(len(bot.history["session-0001"]), 6)  # sirf 6 messages yaad

    async def test_session_limit(self):
        bot, _ = make_bot()  # bot
        bot.max_sessions = 2  # sirf 2 sessions
        for i in range(4):  # 4 sessions
            await bot.chat(f"session-000{i}", "Hello")  # sawal
        self.assertEqual(len(bot.history), 2)  # sirf 2 bachi

    async def test_loop_stops_after_max_rounds(self):
        bot, log = make_bot(FakeLLM(always_tool=True))  # model jo hamesha tool maangta hai
        result = await bot.chat("session-0001", "Show me cables")  # sawal
        self.assertEqual(len(log), agents.MAX_ROUNDS)  # 5 baar tool chala, phir ruk gaya
        self.assertIn("Sorry", result["reply"])  # safe message


if __name__ == "__main__":  # direct chalane par
    unittest.main()  # tests chalao
