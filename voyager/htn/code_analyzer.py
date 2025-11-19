"""
JavaScript code analyzer using Babel AST parser.

This module provides functionality to parse JavaScript code and extract
function calls for validation against known skills and primitives.
"""

import re
from javascript import require
from javascript.proxy import Proxy


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

    @staticmethod
    def _is_dict_like(obj):
        """Check if object is dict-like (dict or Proxy)."""
        return isinstance(obj, (dict, Proxy))

    @staticmethod
    def _safe_get(obj, key, default=None):
        """
        Safely get value from dict or Proxy object with default.

        Args:
            obj: dict or Proxy object
            key: Key to retrieve
            default: Default value if key not found

        Returns:
            Value at key, or default if not found
        """
        return obj[key] if key in obj else default

    @staticmethod
    def _get_length(obj):
        """
        Get length of array-like object (list or Proxy array).

        Args:
            obj: list or Proxy array

        Returns:
            int: Length of the array
        """
        if isinstance(obj, list):
            return len(obj)
        elif hasattr(obj, 'length'):
            return obj.length
        return 0

    @staticmethod
    def _iterate_values(obj):
        """
        Iterate over values in dict or Proxy object.

        Args:
            obj: dict or Proxy object

        Yields:
            Values from the object
        """
        if isinstance(obj, dict):
            for value in obj.values():
                yield value
        elif isinstance(obj, Proxy):
            # For Proxy objects, we need to get keys first
            # Try common AST keys
            for key in ['type', 'body', 'program', 'expression', 'argument',
                       'callee', 'arguments', 'id', 'name', 'value', 'left',
                       'right', 'operator', 'object', 'property', 'computed',
                       'loc', 'start', 'end', 'line', 'column', 'params',
                       'declarations', 'init', 'test', 'consequent', 'alternate',
                       'elements', 'properties', 'key', 'method', 'async', 'generator']:
                if key in obj:
                    yield obj[key]

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
                "sourceType": "module"
            })

            # Walk AST and find CallExpression nodes
            calls = []
            self._visit_ast(ast, calls)

            # Deduplicate and return
            return list(set(calls))

        except Exception as e:
            raise ValueError(f"JavaScript parse error: {e}")

    def extract_function_calls_with_args(self, code):
        """
        Parse JavaScript and extract all function calls WITH their arguments.

        Args:
            code (str): JavaScript code to analyze

        Returns:
            list: List of dicts with {function: str, args: list, line: int}
                Example: [
                    {"function": "mineBlock", "args": ["bot", "'stone'", "3"], "line": 5},
                    {"function": "craftItem", "args": ["bot", "'stick'", "2"], "line": 8}
                ]

        Raises:
            ValueError: If JavaScript parsing fails
        """
        try:
            # Parse to AST
            ast = self.babel.parse(code, {
                "sourceType": "module"
            })

            # Walk AST and extract calls with arguments
            calls_with_args = []
            self._visit_ast_with_args(ast, calls_with_args)

            # Deduplicate based on function name, args, and line number
            seen = set()
            deduplicated = []
            for call in calls_with_args:
                # Create unique key from function, args, and line
                key = (call['function'], tuple(call['args']), call['line'])
                if key not in seen:
                    seen.add(key)
                    deduplicated.append(call)

            return deduplicated

        except Exception as e:
            raise ValueError(f"JavaScript parse error: {e}")

    def _visit_ast(self, node, calls):
        """
        Recursively visit AST nodes to find function calls.

        Args:
            node: AST node (dict or Proxy)
            calls (list): Accumulator for function names
        """
        # Handle Proxy arrays first (before dict-like check)
        if isinstance(node, Proxy) and hasattr(node, 'length') and node.length is not None and 'type' not in node:
            # This is an array-like Proxy
            for i in range(node.length):
                self._visit_ast(node[i], calls)
            return

        if self._is_dict_like(node):
            node_type = self._safe_get(node, 'type')

            # Check for function calls: await foo() or foo()
            if node_type == 'CallExpression':
                callee = self._safe_get(node, 'callee', {})

                # Handle direct function call: foo()
                if self._safe_get(callee, 'type') == 'Identifier':
                    function_name = self._safe_get(callee, 'name')
                    if function_name:
                        calls.append(function_name)

                # Handle member expression: obj.method()
                # Since prompts forbid bot.* calls, we can skip ALL member expressions
                # Only standalone function calls (primitives/skills) are allowed
                elif self._safe_get(callee, 'type') == 'MemberExpression':
                    # Skip all member expressions - not allowed in skill code
                    pass

            # Also check AwaitExpression (await foo())
            elif node_type == 'AwaitExpression':
                argument = self._safe_get(node, 'argument', {})
                self._visit_ast(argument, calls)

            # Recursively visit all child nodes
            for value in self._iterate_values(node):
                self._visit_ast(value, calls)

        elif isinstance(node, list):
            # Handle regular Python lists
            for item in node:
                self._visit_ast(item, calls)

    def _visit_ast_with_args(self, node, calls_with_args):
        """
        Recursively visit AST nodes to find function calls WITH arguments.

        Args:
            node: AST node (dict or Proxy)
            calls_with_args (list): Accumulator for {function, args, line} dicts
        """
        # Handle Proxy arrays first (before dict-like check)
        if isinstance(node, Proxy) and hasattr(node, 'length') and node.length is not None and 'type' not in node:
            # This is an array-like Proxy
            for i in range(node.length):
                self._visit_ast_with_args(node[i], calls_with_args)
            return

        if self._is_dict_like(node):
            node_type = self._safe_get(node, 'type')

            # Check for function calls
            if node_type == 'CallExpression':
                callee = self._safe_get(node, 'callee', {})
                arguments = self._safe_get(node, 'arguments', [])
                loc = self._safe_get(node, 'loc', {})
                start = self._safe_get(loc, 'start', {}) if loc else {}
                line = self._safe_get(start, 'line', 0) if start else 0

                # Handle direct function call: foo(arg1, arg2)
                if self._safe_get(callee, 'type') == 'Identifier':
                    function_name = self._safe_get(callee, 'name')
                    if function_name:
                        # Parse arguments - handle both list and Proxy arrays
                        parsed_args = []
                        if isinstance(arguments, list):
                            parsed_args = [self._parse_argument(arg) for arg in arguments]
                        elif isinstance(arguments, Proxy) and hasattr(arguments, 'length'):
                            for i in range(arguments.length):
                                parsed_args.append(self._parse_argument(arguments[i]))

                        calls_with_args.append({
                            'function': function_name,
                            'args': parsed_args,
                            'line': line
                        })

                # Handle member expression: obj.method(arg1, arg2)
                # For now, skip these as they're usually bot.* or mcData.*

            # Also check AwaitExpression (await foo())
            elif node_type == 'AwaitExpression':
                argument = self._safe_get(node, 'argument', {})
                self._visit_ast_with_args(argument, calls_with_args)

            # Recursively visit all child nodes
            for value in self._iterate_values(node):
                self._visit_ast_with_args(value, calls_with_args)

        elif isinstance(node, list):
            # Handle regular Python lists
            for item in node:
                self._visit_ast_with_args(item, calls_with_args)

    def _parse_argument(self, arg_node):
        """
        Parse an argument AST node into a string representation.

        Args:
            arg_node (dict or Proxy): AST node representing an argument

        Returns:
            str: String representation of the argument
        """
        if not self._is_dict_like(arg_node):
            return str(arg_node)

        node_type = self._safe_get(arg_node, 'type')

        # Identifier: bot, variable names
        if node_type == 'Identifier':
            return self._safe_get(arg_node, 'name', 'unknown')

        # String literal: 'stone', "oak_log"
        elif node_type == 'StringLiteral':
            value = self._safe_get(arg_node, 'value', '')
            return f"'{value}'"  # Return with quotes

        # Numeric literal: 3, 5.5
        elif node_type == 'NumericLiteral':
            return str(self._safe_get(arg_node, 'value', 0))

        # Boolean literal: true, false
        elif node_type == 'BooleanLiteral':
            return 'true' if self._safe_get(arg_node, 'value') else 'false'

        # Binary expression: 3 - cobblestoneCount
        elif node_type == 'BinaryExpression':
            left = self._parse_argument(self._safe_get(arg_node, 'left', {}))
            right = self._parse_argument(self._safe_get(arg_node, 'right', {}))
            operator = self._safe_get(arg_node, 'operator', '+')
            return f"{left} {operator} {right}"

        # Member expression: mcData.itemsByName.stone.id
        elif node_type == 'MemberExpression':
            obj = self._parse_argument(self._safe_get(arg_node, 'object', {}))
            prop = self._safe_get(arg_node, 'property', {})
            if self._safe_get(prop, 'type') == 'Identifier':
                prop_name = self._safe_get(prop, 'name', 'unknown')
                computed = self._safe_get(arg_node, 'computed', False)
                if computed:
                    return f"{obj}[{prop_name}]"
                else:
                    return f"{obj}.{prop_name}"
            return obj

        # Call expression: bot.inventory.count(...)
        elif node_type == 'CallExpression':
            callee = self._safe_get(arg_node, 'callee', {})
            callee_str = self._parse_argument(callee)
            args = self._safe_get(arg_node, 'arguments', [])

            # Handle both list and Proxy arrays
            args_list = []
            if isinstance(args, list):
                args_list = [self._parse_argument(a) for a in args]
            elif isinstance(args, Proxy) and hasattr(args, 'length'):
                for i in range(args.length):
                    args_list.append(self._parse_argument(args[i]))

            args_str = ', '.join(args_list)
            return f"{callee_str}({args_str})"

        # Unary expression: -5, !flag
        elif node_type == 'UnaryExpression':
            operator = self._safe_get(arg_node, 'operator', '!')
            argument = self._parse_argument(self._safe_get(arg_node, 'argument', {}))
            return f"{operator}{argument}"

        # Unknown node type - try to generate code with babel generator
        else:
            try:
                generated = self.babel_generator(arg_node)
                return self._safe_get(generated, 'code', str(arg_node))
            except Exception:
                return f"<unparsed:{node_type}>"

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
                "sourceType": "module"
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
        if self._is_dict_like(node):
            node_type = self._safe_get(node, 'type')

            # Check for function declarations
            if node_type in ('FunctionDeclaration', 'FunctionExpression'):
                id_node = self._safe_get(node, 'id', {})
                if id_node and self._safe_get(id_node, 'type') == 'Identifier':
                    return self._safe_get(id_node, 'name')

            # Recursively search children
            for value in self._iterate_values(node):
                if self._is_dict_like(value) or isinstance(value, list):
                    name = self._find_function_name(value)
                    if name:
                        return name

        elif isinstance(node, list):
            # Handle regular Python lists
            for item in node:
                name = self._find_function_name(item)
                if name:
                    return name
        elif isinstance(node, Proxy) and hasattr(node, 'length'):
            # Handle Proxy arrays
            for i in range(node.length):
                name = self._find_function_name(node[i])
                if name:
                    return name

        return None
