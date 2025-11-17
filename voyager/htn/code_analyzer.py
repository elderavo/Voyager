"""
JavaScript code analyzer using Babel AST parser.

This module provides functionality to parse JavaScript code and extract
function calls for validation against known skills and primitives.
"""

import re
from javascript import require


class JavaScriptAnalyzer:
    """Analyze JavaScript code using Babel AST parser."""

    def __init__(self):
        """Initialize Babel parser."""
        try:
            self.babel = require("@babel/core")
            self.babel_generator = require("@babel/generator").default
        except Exception as e:
            print(f"\033[31m[JavaScriptAnalyzer] Failed to load Babel: {e}\033[0m")
            print("\033[31mMake sure @babel/core and @babel/generator are installed:\033[0m")
            print("\033[31m  npm install -g @babel/core @babel/generator\033[0m")
            raise

    def extract_function_calls(self, code):
        """
        Parse JavaScript and extract all function calls.

        Args:
            code (str): JavaScript code to analyze

        Returns:
            list: Function names called in the code (deduplicated)

        Raises:
            ValueError: If JavaScript parsing fails
        """
        try:
            # Parse to AST
            ast = self.babel.parse(code, {
                "sourceType": "module",
                "plugins": ["jsx"]
            })

            # Walk AST and find CallExpression nodes
            calls = []
            self._visit_ast(ast, calls)

            # Deduplicate and return
            return list(set(calls))

        except Exception as e:
            raise ValueError(f"JavaScript parse error: {e}")

    def _visit_ast(self, node, calls):
        """
        Recursively visit AST nodes to find function calls.

        Args:
            node: AST node (dict or list)
            calls (list): Accumulator for function names
        """
        if isinstance(node, dict):
            node_type = node.get('type')

            # Check for function calls: await foo() or foo()
            if node_type == 'CallExpression':
                callee = node.get('callee', {})

                # Handle direct function call: foo()
                if callee.get('type') == 'Identifier':
                    function_name = callee.get('name')
                    if function_name:
                        calls.append(function_name)

                # Handle member expression: obj.method()
                elif callee.get('type') == 'MemberExpression':
                    obj = callee.get('object', {})
                    prop = callee.get('property', {})

                    # Skip bot.* methods (built-in mineflayer API)
                    if obj.get('name') == 'bot':
                        pass
                    # Skip mcData.* methods (built-in minecraft-data)
                    elif obj.get('name') == 'mcData':
                        pass
                    # Other object methods might be custom functions
                    elif prop.get('type') == 'Identifier':
                        method_name = prop.get('name')
                        if method_name:
                            calls.append(method_name)

            # Also check AwaitExpression (await foo())
            elif node_type == 'AwaitExpression':
                argument = node.get('argument', {})
                self._visit_ast(argument, calls)

            # Recursively visit all child nodes
            for value in node.values():
                if isinstance(value, (dict, list)):
                    self._visit_ast(value, calls)

        elif isinstance(node, list):
            for item in node:
                self._visit_ast(item, calls)

    def validate_function_calls(self, code, available_functions):
        """
        Validate that all function calls in code exist in available functions.

        Args:
            code (str): JavaScript code to validate
            available_functions (set): Set of valid function names

        Returns:
            tuple: (is_valid, errors, function_calls)
                is_valid (bool): True if all functions are valid
                errors (str): Error message if invalid, None otherwise
                function_calls (list): All function calls found in code
        """
        try:
            function_calls = self.extract_function_calls(code)

            # Check each call against available functions
            invalid_calls = [f for f in function_calls if f not in available_functions]

            if invalid_calls:
                error_msg = (
                    f"Unknown functions: {invalid_calls}\n"
                    f"Available functions: {sorted(available_functions)}"
                )
                return False, error_msg, function_calls

            return True, None, function_calls

        except ValueError as e:
            return False, str(e), []

    def extract_function_name(self, code):
        """
        Extract the function name from a function declaration.

        Args:
            code (str): JavaScript function code

        Returns:
            str: Function name, or None if not found
        """
        # Try to parse with Babel
        try:
            ast = self.babel.parse(code, {
                "sourceType": "module",
                "plugins": ["jsx"]
            })

            # Look for FunctionDeclaration or FunctionExpression
            name = self._find_function_name(ast)
            if name:
                return name

        except Exception:
            pass

        # Fallback: regex extraction
        # Match: async function functionName(
        match = re.search(r'async\s+function\s+(\w+)\s*\(', code)
        if match:
            return match.group(1)

        # Match: function functionName(
        match = re.search(r'function\s+(\w+)\s*\(', code)
        if match:
            return match.group(1)

        return None

    def _find_function_name(self, node):
        """
        Recursively find function name in AST.

        Args:
            node: AST node

        Returns:
            str: Function name if found, None otherwise
        """
        if isinstance(node, dict):
            node_type = node.get('type')

            # Check for function declarations
            if node_type in ('FunctionDeclaration', 'FunctionExpression'):
                id_node = node.get('id', {})
                if id_node and id_node.get('type') == 'Identifier':
                    return id_node.get('name')

            # Recursively search children
            for value in node.values():
                if isinstance(value, (dict, list)):
                    name = self._find_function_name(value)
                    if name:
                        return name

        elif isinstance(node, list):
            for item in node:
                name = self._find_function_name(item)
                if name:
                    return name

        return None
