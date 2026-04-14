def add_few_shot_examples():
    return """
        Examples:

        Input: Every application must start with registration. If an application is approved, a welcome package must eventually be sent. Background check and fraud check must either both occur or both be absent.
        Activities: 'Register Application', 'Approve Application', 'Send Welcome Package', 'Background Check', 'Fraud Check', 'Reject Application'
        rule1 = Init("Register Application")
        rule2 = Response("Approve Application", "Send Welcome Package")
        rule3 = CoExistence("Background Check", "Fraud Check")
        \n\n
        Input: If an order is received, then the manager must be notified. If a refund is issued, then the refund must be processed eventually.
        Activities: 'Order Received', 'Notify Manager', 'Refund', 'Process Refund', 'Print Label', 'Scan Label'
        rule1 = RespondedExistence("Order Received", "Notify Manager")
        rule2 = Response("Refund", "Process Refund")
        rule3 = CoExistence("Print Label", "Scan Label")
        \n\n
        Input: Instances, where payment occurs, must also include an invoice.
        Activities: 'Payment', 'Invoice', 'Order', 'Delivery'
        Output:
        rule1 = RespondedExistence("Payment", "Invoice")
        \n\n

        Input: A process instance starts with a registration activity.A case cannot be wrapped up unless it has at some point actually been looked into. And whenever someone decides to escalate things, it shouldn't happen in isolation — some form of oversight must appear somewhere along the way.
        Activities: 'Register Case', 'Investigate Case', 'Escalate Case', 'Supervisor Review', 'Close Case', 'Cancel Case'
        rule1 = Init("Register Case")
        rule2 = Precedence("Investigate Case", "Close Case")
        rule3 = RespondedExistence("Escalate Case", "Supervisor Review")
    """


def generate_declare_prompt(process_description, activities):

    system_instructions = (
        "You are an expert in Process Mining and DECLARE modeling. Your task is to derive "
        "DECLARE rules based on a description of a process or its constraints.\n\n"
        "The activities involved in the process are: " + ", ".join(activities) + ".\n\n"
        "Use only the following rules:\n"
        "- AtMost1(A): Activity A occurs at most once in every trace.\n"
        "- Init(A): Each trace starts with activity A.\n"
        "- End(A): Each trace ends with activity A.\n"
        "- Existence(A): Activity A occurs at least once per trace.\n"
        "- CoExistence(A, B): If A occurs, B must occur; if B occurs, A must occur.\n"
        "- NotCoExistence(A, B): Activities A and B cannot coexist in the same trace.\n"
        "- NotSuccession(A, B): Activity B never follows activity A in the same trace.\n"
        "- Precedence(A, B): Activity B can only occur if activity A has occurred before it.\n"
        "- ChainPrecedence(A, B): Activity B can only occur if activity A has occurred **directly** before it.\n"
        "- RespondedExistence(A, B): If activity A occurs, activity B must also occur (anywhere in the trace).\n"
        "- Response(A, B): If activity A occurs, activity B must eventually follow it.\n"
        "- ChainResponse(A, B): If activity A occurs, activity B must **directly** follow it.\n\n"
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
