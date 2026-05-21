def build_prompt(message, retrieval):
    return f'''
Customer Question:
{message}

Retrieved Context:
{retrieval}
'''