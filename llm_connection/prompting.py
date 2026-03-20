def add_few_shot_examples():
    return """
        Examples:

        Input: The process always starts with 'Registration'. 'Credit Check' and 'Cash Payment' are mutually exclusive. Every trace ends with 'Archive'.
        Output:
        rule1 = Init("Registration")
        rule2 = NotCoExistence("Credit Check", "Cash Payment")
        rule3 = End("Archive")

        Input: 'Validation' must happen at least once. 'Final Sign-off' can occur at most once. 'Shipment' can only happen if 'Packaging' has already occurred.
        Output:
        rule1 = Existence("Validation")
        rule2 = AtMost1("Final Sign-off")
        rule3 = Precedence("Packaging", "Shipment")

        Input: If 'Order Received' occurs, then 'Notify Manager' must also happen at some point. If 'Refund' is requested, 'Process Refund' must eventually follow. 'Print Label' and 'Scan Label' must always appear together.
        Output:
        rule1 = RespondedExistence("Order Received", "Notify Manager")
        rule2 = Response("Refund", "Process Refund")
        rule3 = CoExistence("Print Label", "Scan Label")
    """


def generate_declare_prompt(process_description):

    system_instructions = (
        "You are an expert in Process Mining and DECLARE modeling. Your task is to derive "
        "DECLARE rules based on a description of a process or its constraints.\n\n"
        "Use only the following rules:\n"
        "- AtMost1(A): Activity A occurs at most once in every trace.\n"
        "- Init(A): Each trace starts with activity A.\n"
        "- End(A): Each trace ends with activity A.\n"
        "- Existence(A): Activity A occurs at least once per trace.\n"
        "- CoExistence(A, B): If A occurs, B must occur; if B occurs, A must occur.\n"
        "- NotCoExistence(A, B): Activities A and B cannot coexist in the same trace.\n"
        "- Precedence(A, B): Activity B can only occur if activity A has occurred before it.\n"
        "- RespondedExistence(A, B): If activity A occurs, activity B must also occur (anywhere in the trace).\n"
        "- Response(A, B): If activity A occurs, activity B must eventually follow it.\n\n"
        "The expected output must be a Python code snippet with the following format:\n"
        "```python\n"
        'rule1 = RuleName("ActivityA")\n'
        'rule2 = RuleName("ActivityA", "ActivityB")\n'
        "```\n"
        "Return ONLY the code block."
    )

    # Combine instructions with the specific process description
    full_prompt = f"{system_instructions}\n\n{add_few_shot_examples}\n\nProcess Description:\n{process_description}"

    return full_prompt


def feedback_prompt(feedback):
    return f"The user has provided the following feedback: {feedback}. Use it to refine the previous results."
