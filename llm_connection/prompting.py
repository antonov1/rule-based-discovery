def add_few_shot_examples():
    return """
        Examples:

        Input: Every application process must start with registration. An application may only be approved after its documents have been reviewed. If an application is approved, a welcome package must eventually be sent. A background check and a fraud check must either both occur or both be absent. Rejected applications must never receive a welcome package.
        Activities: ‘Register Application’, ‘Review Documents’, ‘Approve Application’, ‘Reject Application’, ‘Send Welcome Package’, ‘Background Check’, ‘Fraud Check’
        Output:
        rule1 = Init(“Register Application”)
        rule2 = Precedence(“Review Documents”, “Approve Application”)
        rule3 = Response(“Approve Application”, “Send Welcome Package”)
        rule4 = CoExistence(“Background Check”, “Fraud Check”)
        rule5 = NotSuccession(“Reject Application”, “Send Welcome Package”)

        Input: Every purchasing process starts when a purchase request is submitted. Whenever payment occurs, the process instance must also include an invoice. A payment may only be made after the purchase request has been approved. If payment is made, a confirmation must eventually be sent. The process ends when the order is closed.
        Activities: ‘Submit Purchase Request’, ‘Approve Purchase Request’, ‘Reject Purchase Request’, ‘Make Payment’, ‘Create Invoice’, ‘Send Payment Confirmation’, ‘Close Order’
        Output:
        rule1 = Init(“Submit Purchase Request”)
        rule2 = RespondedExistence(“Make Payment”, “Create Invoice”)
        rule3 = Precedence(“Approve Purchase Request”, “Make Payment”)
        rule4 = Response(“Make Payment”, “Send Payment Confirmation”)
        rule5 = End(“Close Order”)

        Input: A case-management process begins with case registration. A case cannot be closed unless it has previously been investigated. Whenever a case is escalated, a supervisor review must occur somewhere in the same process instance. If the supervisor approves the escalation, the case must eventually be reassigned. A case cannot be both cancelled and closed.
        Activities: ‘Register Case’, ‘Investigate Case’, ‘Escalate Case’, ‘Supervisor Review’, ‘Approve Escalation’, ‘Reassign Case’, ‘Cancel Case’, ‘Close Case’
        Output:
        rule1 = Init(“Register Case”)
        rule2 = Precedence(“Investigate Case”, “Close Case”)
        rule3 = RespondedExistence(“Escalate Case”, “Supervisor Review”)
        rule4 = Response(“Approve Escalation”, “Reassign Case”)
        rule5 = NotCoExistence(“Cancel Case”, “Close Case”)

        Input: A warehouse replenishment process begins by checking the current inventory level. If an automated alert is sent, an order must eventually be placed with a supplier. The same applies when a manual alert is sent. Automated and manual alerts cannot both occur in the same process instance. Stock may only be inspected after it has been received. Recording the stock must occur directly after the inspection. Placing the stock on shelves and placing it in storage are mutually exclusive. The process ends when inventory levels are updated.
        Activities: ‘Check Current Inventory Level’, ‘Send Automated Alert’, ‘Send Manual Alert’, ‘Place Supplier Order’, ‘Receive Stock’, ‘Inspect Stock’, ‘Record Stock’, ‘Place Stock on Shelves’, ‘Place Stock in Storage’, ‘Update Inventory Levels’
        Output:
        rule1 = Init(“Check Current Inventory Level”)
        rule2 = Response(“Send Automated Alert”, “Place Supplier Order”)
        rule3 = Response(“Send Manual Alert”, “Place Supplier Order”)
        rule4 = NotCoExistence(“Send Automated Alert”, “Send Manual Alert”)
        rule5 = Precedence(“Receive Stock”, “Inspect Stock”)
        rule6 = ChainResponse(“Inspect Stock”, “Record Stock”)
        rule7 = NotCoExistence(“Place Stock on Shelves”, “Place Stock in Storage”)
        rule8 = End(“Update Inventory Levels”)

        Input: A support ticket must start with ticket creation. Ticket classification must occur directly after ticket creation. A ticket can only be assigned after it has been classified. If a ticket is assigned to a specialist, that specialist must eventually provide a resolution. A ticket cannot be reopened unless it has previously been closed. Whenever a ticket is reopened, it must eventually be assigned again.
        Activities: ‘Create Ticket’, ‘Classify Ticket’, ‘Assign Ticket’, ‘Assign to Specialist’, ‘Provide Resolution’, ‘Close Ticket’, ‘Reopen Ticket’
        Output:
        rule1 = Init(“Create Ticket”)
        rule2 = ChainResponse(“Create Ticket”, “Classify Ticket”)
        rule3 = Precedence(“Classify Ticket”, “Assign Ticket”)
        rule4 = Response(“Assign to Specialist”, “Provide Resolution”)
        rule5 = Precedence(“Close Ticket”, “Reopen Ticket”)
        rule6 = Response(“Reopen Ticket”, “Assign Ticket”)
    """


def generate_declare_prompt(process_description, activities, include_examples=True):

    system_instructions = (
        "You are an expert in Process Mining and DECLARE modeling. Your task is to derive "
        "DECLARE rules based on a description of a process or its constraints.\n\n"
        "The activities involved in the process are: " + ", ".join(activities) + ".\n\n"
        "Use only the following rules:\n"
        "- AtMostOnce(A): Activity A occurs at most once in every trace.\n"
        "- Init(A): Each trace starts with activity A.\n"
        "- End(A): Each trace ends with activity A.\n"
        "- Existence(A): Activity A occurs at least once per trace.\n"
        "- CoExistence(A, B): If A occurs, B must occur; if B occurs, A must occur.\n"
        "- NotCoExistence(A, B): Activities A and B cannot coexist in the same trace.\n"
        "- NotSuccession(A, B): Activity B never follows activity A in the same trace.\n"
        "- Precedence(A, B): Activity B can only occur if activity A has occurred before it. Use Precedence if it is stated something like 'Y cannot happen before X'.\n"
        "- ChainPrecedence(A, B): Activity B can only occur if activity A has occurred **directly** before it.\n"
        "- RespondedExistence(A, B): If activity A occurs, activity B must also occur (anywhere in the trace).\n"
        "- Response(A, B): If activity A occurs, activity B must eventually follow it. Use Response if the text describes process state progression, e.g., 'After X, Y happens',  'Once X, Y starts', etc. \n"
        "- ChainResponse(A, B): If activity A occurs, activity B must **directly** follow it.\n\n"
        "The expected output must be a Python code snippet with the following format:\n"
        "```python\n"
        'rule1 = RuleName("ActivityA")\n'
        'rule2 = RuleName("ActivityA", "ActivityB")\n'
        "```\n"
        "Return ONLY the code block."
    )

    # Combine instructions with the specific process description
    full_prompt = (
        f"{system_instructions}\n\n{add_few_shot_examples}\n\nProcess Description:\n{process_description}"
        if include_examples
        else f"{system_instructions}\n\nProcess Description:\n{process_description}"
    )

    return full_prompt


def feedback_prompt(feedback):
    return f"The user has provided the following feedback: {feedback}. Use it to refine the previous results."
