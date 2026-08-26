import ast
import re
from typing import Any, Callable, List, Optional, TypeVar

from llm_connection.prompting import generate_declare_prompt
from promoai.general_utils.llm_connection import (
    generate_result_with_error_handling,
    LLMConnection,
    query_llm,
)
from promoai.model_generation.code_extraction import execute_code_and_get_variable
from promoai.prompting.prompt_engineering import ERROR_MESSAGE_FOR_MODEL_GENERATION
from rules import (
    AtMostOnceRule,
    ChainPrecedenceRule,
    ChainResponseRule,
    CoExistenceRule,
    EndRule,
    ExistenceRule,
    InitializationRule,
    NotCoExistenceRule,
    NotSuccessionRule,
    PrecedenceRule,
    RespondedExistenceRule,
    ResponseRule,
)

T = TypeVar("T")

ERROR_MESSAGE_CODE_GENERATION_DECLARE = (
    "Failed to generate DECLARE rules. Follow strictly the output format, e.g.,"
    " ```python"
    "rule1 = AtMostOnce('A') "
    "```."
)


def generate_result_with_error_handling(
    conversation: List[dict[str:str]],
    extraction_function: Callable[[str, Any], T],
    api_key: str,
    llm_name: str,
    ai_provider: str,
    llm_args: Optional[dict] = {},
    max_iterations=5,
    additional_iterations=5,
    standard_error_message=ERROR_MESSAGE_FOR_MODEL_GENERATION,
) -> tuple[str, any, list[Any]]:
    error_history = []
    for iteration in range(max_iterations + additional_iterations):
        response = query_llm(conversation, api_key, llm_name, ai_provider, llm_args)
        try:
            conversation.append({"role": "assistant", "content": response})
            auto_duplicate = iteration >= max_iterations
            code, result = extraction_function(response, auto_duplicate)
            return code, result, conversation  # Break loop if execution is successful
        except Exception as e:
            error_description = str(e)
            error_history.append(error_description)
            if True:
                print("Error detected in iteration " + str(iteration + 1))
                print("\t" + error_description.replace("\n", " ").replace("\r", " "))
            new_message = (
                f"Executing your code led to an error! "
                + standard_error_message
                + "This is the error"
                f" message: {error_description}"
            )
            conversation.append(
                {"role": "user", "content": new_message, "type": "error"}
            )

    raise Exception(
        llm_name
        + " failed to fix the errors after "
        + str(max_iterations + 5)
        + " iterations! This is the error history: "
        + str(error_history)
    )


def query_llm_for_declare_rules(
    process_description, activities, llm_connection: LLMConnection
):
    prompt = generate_declare_prompt(process_description, activities)
    msg_history = [{"role": "user", "content": prompt}]

    def partial_code_extraction(code, auto_duplicate=False):
        return code_extraction(code, activities=activities)

    args = llm_connection.args if llm_connection.args is not None else {}
    try:
        code, rules, convo = generate_result_with_error_handling(
            msg_history,
            extraction_function=partial_code_extraction,
            llm_name=llm_connection.llm_name,
            ai_provider=llm_connection.ai_provider,
            api_key=llm_connection.api_key,
            max_iterations=3,
            additional_iterations=2,
            standard_error_message=ERROR_MESSAGE_CODE_GENERATION_DECLARE,
            llm_args=args,
        )
        errors = sum(msg.get("type") == "error" for msg in convo)
        return rules, errors, code
    except ValueError as e:
        raise ValueError(f"Error during LLM query: {str(e)}")
    except ValueError as e:
        error_message = f"Error extracting code: {str(e)}."
        raise ValueError(error_message)


def code_extraction(code_snippet: str, activities=None):
    """
    Extracts code from a given code snippet, removing any markdown formatting.
    """
    # Check that the code is wrapped in ```python ... ```
    pattern = r"```python\s*(.*?)\s*```"
    match = re.search(pattern, code_snippet, re.DOTALL)

    if not match:
        raise ValueError(
            "Code snippet is not properly formatted with ```python ... ```"
        )
    code = match.group(1).strip()
    code = sanitize_activity_literals(code, activities)
    if has_imports(code):
        raise ValueError("Code snippet should not contain any import statements!")
    namespace = {
        "AtMostOnce": AtMostOnceRule,
        "CoExistence": CoExistenceRule,
        "End": EndRule,
        "Existence": ExistenceRule,
        "Init": InitializationRule,
        "Initialization": InitializationRule,
        "Precedence": PrecedenceRule,
        "RespondedExistence": RespondedExistenceRule,
        "Response": ResponseRule,
        "NotCoExistence": NotCoExistenceRule,
        "NotSuccession": NotSuccessionRule,
        "ChainResponse": ChainResponseRule,
        "ChainPrecedence": ChainPrecedenceRule,
    }
    print(f"Extracted code snippet:\n{code}")
    # remove all leading indentation from the code
    code = process_code(code, activities=activities)
    print(f"Processed code:\n{code}")
    code = re.sub(r"^\s+", "", code, flags=re.MULTILINE)
    print(f"Extracted code:\n{code}")

    return code, execute_code_and_get_variable(code, "result", namespace=namespace)


def has_imports(code: str):
    tree = ast.parse(code)
    return any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def sanitize_activity_literals(code: str, activities=None) -> str:
    if not activities:
        return code

    for activity in sorted(activities, key=len, reverse=True):
        safe = repr(activity)

        # Normal correctly quoted variants.
        candidates = {
            f"'{activity}'",
            f'"{activity}"',
        }

        # Common LLM mistake for apostrophes:
        # B'D -> 'B'D'' or similar broken single-quote representation.
        if "'" in activity:
            candidates.add("'" + activity + "''")

        for candidate in candidates:
            if candidate != safe:
                code = code.replace(candidate, safe)

    return code


def process_code(code, activities=None):
    tree = ast.parse(code)

    rules = []

    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            var_name = (
                node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            )
            rule_type = (
                node.value.func.id if isinstance(node.value.func, ast.Name) else None
            )
            if rule_type not in [
                "AtMostOnce",
                "CoExistence",
                "End",
                "Existence",
                "Init",
                "Initialization",
                "Precedence",
                "RespondedExistence",
                "Response",
                "NotCoExistence",
                "NotSuccession",
                "ChainResponse",
                "ChainPrecedence",
            ]:
                raise ValueError(
                    f"Invalid rule type: {rule_type}. Allowed types are: AtMostOnce, CoExistence, End, Existence, Init, Precedence, RespondedExistence, Response, NotCoExistence, ChainResponse, ChainPrecedence."
                )

            args = []
            for arg in node.value.args:
                if isinstance(arg, ast.Constant):
                    args.append(arg.value)
                    if activities is not None and arg.value not in activities:
                        raise ValueError(
                            f"Invalid activity: {arg.value}. Allowed activities are: {', '.join(activities)}."
                        )

            rules.append(
                {
                    "name": var_name,
                    "type": rule_type,
                    "args": args,
                }
            )
    sanitized_code = "\n".join(
        f"{rule['name']} = {rule['type']}({', '.join(repr(arg) for arg in rule['args'])})"
        for rule in rules
    )
    names = [rule["name"] for rule in rules]
    sanitized_code += "\nresult = [" + ", ".join(names) + "]"
    return sanitized_code


if __name__ == "__main__":
    import textwrap

    code = textwrap.dedent("""
    ```python
    r1 = ChainResponse('A', 'B'D'')
    r2 = Initialization('A')
    ```""")
    _, rules = code_extraction(code, ["A", "B'D"])
    for r in rules:
        print(r)
