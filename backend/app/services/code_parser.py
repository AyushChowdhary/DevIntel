import ast

def parse_python_file(code):
    tree = ast.parse(code)

    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append({"name": node.name})
        elif isinstance(node, ast.ClassDef):
            classes.append({"name": node.name})

    return {"functions": functions, "classes": classes}


def extract_imports(code):
    tree = ast.parse(code)
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)

    return imports