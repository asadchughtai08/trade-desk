import re  # regex library, private data dhoondne ke liye


def get_text(content):
    """Turn model or tool content (str or list of blocks) into plain text."""
    if isinstance(content, str):  # agar already text hai
        return content  # seedha wapas karo
    if isinstance(content, list):  # agar blocks ki list hai
        parts = []  # text parts yahan jama honge
        for block in content:  # har block ko dekho
            if isinstance(block, dict):  # block dict hai
                parts.append(str(block.get("text", "")))  # uska text lo
            else:  # block simple string hai
                parts.append(str(block))  # usko text bana lo
        return "".join(parts)  # sab jor kar wapas karo
    return str(content)  # baqi sab cheezen text bana do


def mask_text(text):
    """Hide emails and phone numbers so logs never show private data."""
    text = str(text)  # pakka karo ke text hai
    text = re.sub(r"([\w.])[\w.+-]*@([\w-]+\.[\w.]+)", r"\1***@\2", text)  # email: ali@x.com -> a***@x.com
    text = re.sub(r"\+?\d[\d\s-]{6,}\d", lambda m: "***" + re.sub(r"\D", "", m.group())[-2:], text)  # phone: sirf aakhri 2 digits
    return text  # masked text wapas karo
