"""
Simple bytecode to Python reconstructor using xdis.
"""
import xdis.load as load
import types
import dis as pydis
import sys

pyc_path = sys.argv[1] if len(sys.argv) > 1 else 'xploit.pyc'
(version, timestamp, magic_int, code, is_pypy, source_size, sip_hash) = load.load_module(pyc_path)

def decode_instructions(co):
    bytecode = co.co_code
    result = []
    i = 0
    extended_arg = 0
    while i < len(bytecode):
        op = bytecode[i]
        arg = bytecode[i+1] if i + 1 < len(bytecode) else 0
        real_arg = arg | extended_arg
        if op == 144:  # EXTENDED_ARG
            extended_arg = real_arg << 8
            i += 2
            continue
        else:
            extended_arg = 0
        opname = pydis.opname[op]
        argval = real_arg
        if op in pydis.hasconst:
            argval = co.co_consts[real_arg] if real_arg < len(co.co_consts) else real_arg
        elif op in pydis.hasname:
            argval = co.co_names[real_arg] if real_arg < len(co.co_names) else real_arg
        elif op in pydis.haslocal:
            argval = co.co_varnames[real_arg] if real_arg < len(co.co_varnames) else real_arg
        elif op in pydis.hasfree:
            free = co.co_cellvars + co.co_freevars
            argval = free[real_arg] if real_arg < len(free) else real_arg
        result.append((i, opname, op, real_arg, argval))
        i += 2
    return result

def decompile_function(co, prefix=""):
    instrs = decode_instructions(co)
    stack = []
    lines = []
    for idx, (offset, opname, op, arg, argval) in enumerate(instrs):
        try:
            if opname == 'LOAD_CONST':
                if isinstance(argval, types.CodeType):
                    stack.append(f"<code:{argval.co_name}>")
                elif argval is None:
                    stack.append('None')
                elif isinstance(argval, str):
                    stack.append(repr(argval))
                elif isinstance(argval, tuple):
                    r = repr(argval)
                    if len(r) > 120:
                        r = r[:120] + '...'
                    stack.append(r)
                elif isinstance(argval, bool):
                    stack.append(str(argval))
                else:
                    stack.append(str(argval))
            elif opname in ('LOAD_FAST', 'LOAD_NAME', 'LOAD_GLOBAL', 'LOAD_DEREF'):
                stack.append(str(argval))
            elif opname == 'LOAD_ATTR':
                obj = stack.pop() if stack else '?'
                stack.append(f"{obj}.{argval}")
            elif opname == 'LOAD_METHOD':
                obj = stack.pop() if stack else '?'
                stack.append(f"{obj}.{argval}")
            elif opname in ('STORE_FAST', 'STORE_NAME', 'STORE_GLOBAL', 'STORE_DEREF'):
                val = stack.pop() if stack else '?'
                name = str(argval)
                lines.append(f"{prefix}{name} = {val}")
            elif opname == 'STORE_ATTR':
                obj = stack.pop() if stack else '?'
                val = stack.pop() if stack else '?'
                lines.append(f"{prefix}{obj}.{argval} = {val}")
            elif opname == 'STORE_SUBSCR':
                key = stack.pop() if stack else '?'
                obj = stack.pop() if stack else '?'
                val = stack.pop() if stack else '?'
                lines.append(f"{prefix}{obj}[{key}] = {val}")
            elif opname == 'BINARY_SUBSCR':
                key = stack.pop() if stack else '?'
                obj = stack.pop() if stack else '?'
                stack.append(f"{obj}[{key}]")
            elif opname == 'DELETE_SUBSCR':
                key = stack.pop() if stack else '?'
                obj = stack.pop() if stack else '?'
                lines.append(f"{prefix}del {obj}[{key}]")
            elif opname == 'BINARY_ADD':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} + {b})")
            elif opname == 'BINARY_SUBTRACT':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} - {b})")
            elif opname == 'BINARY_MULTIPLY':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} * {b})")
            elif opname == 'BINARY_TRUE_DIVIDE':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} / {b})")
            elif opname == 'BINARY_FLOOR_DIVIDE':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} // {b})")
            elif opname == 'BINARY_MODULO':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} % {b})")
            elif opname == 'BINARY_AND':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} & {b})")
            elif opname == 'BINARY_OR':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} | {b})")
            elif opname == 'BINARY_XOR':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} ^ {b})")
            elif opname == 'BINARY_LSHIFT':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} << {b})")
            elif opname == 'BINARY_RSHIFT':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} >> {b})")
            elif opname == 'UNARY_NEGATIVE':
                a = stack.pop() if stack else '?'
                stack.append(f"(-{a})")
            elif opname == 'UNARY_NOT':
                a = stack.pop() if stack else '?'
                stack.append(f"(not {a})")
            elif opname.startswith('INPLACE_'):
                ops = {'INPLACE_ADD': '+', 'INPLACE_SUBTRACT': '-', 'INPLACE_MULTIPLY': '*',
                       'INPLACE_TRUE_DIVIDE': '/', 'INPLACE_FLOOR_DIVIDE': '//', 'INPLACE_MODULO': '%'}
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                stack.append(f"({a} {ops.get(opname, '?')}= {b})")
            elif opname == 'COMPARE_OP':
                cmp_ops = ['<', '<=', '==', '!=', '>', '>=', 'in', 'not in', 'is', 'is not']
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                op_str = cmp_ops[arg] if arg < len(cmp_ops) else f'CMP_{arg}'
                stack.append(f"({a} {op_str} {b})")
            elif opname == 'CONTAINS_OP':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                op_str = 'not in' if arg else 'in'
                stack.append(f"({a} {op_str} {b})")
            elif opname == 'IS_OP':
                b, a = stack.pop() if stack else '?', stack.pop() if stack else '?'
                op_str = 'is not' if arg else 'is'
                stack.append(f"({a} {op_str} {b})")
            elif opname in ('CALL_FUNCTION', 'CALL_METHOD'):
                call_args = [stack.pop() if stack else '?' for _ in range(arg)]
                call_args.reverse()
                func = stack.pop() if stack else '?'
                stack.append(f"{func}({', '.join(call_args)})")
            elif opname == 'CALL_FUNCTION_KW':
                kw_names = stack.pop() if stack else ()
                all_args = [stack.pop() if stack else '?' for _ in range(arg)]
                all_args.reverse()
                func = stack.pop() if stack else '?'
                stack.append(f"{func}({', '.join(all_args)})")
            elif opname == 'CALL_FUNCTION_EX':
                if arg & 1:
                    kwargs = stack.pop() if stack else '?'
                    args_val = stack.pop() if stack else '?'
                    func = stack.pop() if stack else '?'
                    stack.append(f"{func}(*{args_val}, **{kwargs})")
                else:
                    args_val = stack.pop() if stack else '?'
                    func = stack.pop() if stack else '?'
                    stack.append(f"{func}(*{args_val})")
            elif opname == 'RETURN_VALUE':
                val = stack.pop() if stack else 'None'
                if val != 'None':
                    lines.append(f"{prefix}return {val}")
            elif opname == 'POP_TOP':
                val = stack.pop() if stack else None
                if val and val != 'None' and not val.startswith('<code:'):
                    lines.append(f"{prefix}{val}")
            elif opname == 'POP_JUMP_IF_FALSE':
                cond = stack.pop() if stack else '?'
                lines.append(f"{prefix}if {cond}:  # -> {argval}")
            elif opname == 'POP_JUMP_IF_TRUE':
                cond = stack.pop() if stack else '?'
                lines.append(f"{prefix}if not {cond}:  # skip -> {argval}")
            elif opname in ('JUMP_FORWARD', 'JUMP_ABSOLUTE'):
                lines.append(f"{prefix}# jump -> {argval}")
            elif opname == 'BUILD_TUPLE':
                items = [stack.pop() if stack else '?' for _ in range(arg)]
                items.reverse()
                stack.append(f"({', '.join(items)})")
            elif opname == 'BUILD_LIST':
                items = [stack.pop() if stack else '?' for _ in range(arg)]
                items.reverse()
                stack.append(f"[{', '.join(items)}]")
            elif opname == 'BUILD_MAP':
                stack.append('{}')
            elif opname == 'LIST_EXTEND':
                ext = stack.pop() if stack else '?'
                lst = stack.pop() if stack else '?'
                stack.append(f"[*{lst}, *{ext}]" if lst != '[]' else f"list({ext})")
            elif opname == 'UNPACK_SEQUENCE':
                seq = stack.pop() if stack else '?'
                for j in range(arg):
                    stack.append(f"UNPACK_{j}_of_{seq}")
            elif opname == 'GET_ITER':
                val = stack.pop() if stack else '?'
                stack.append(f"iter({val})")
            elif opname == 'FOR_ITER':
                lines.append(f"{prefix}# FOR_ITER (iterator on stack)")
            elif opname == 'MAKE_FUNCTION':
                qualname = stack.pop() if stack else '?'
                code_obj = stack.pop() if stack else '?'
                if arg & 0x08:
                    stack.pop() if stack else None  # closure
                if arg & 0x04:
                    stack.pop() if stack else None  # annotations
                if arg & 0x02:
                    stack.pop() if stack else None  # kwdefaults
                if arg & 0x01:
                    stack.pop() if stack else None  # defaults
                stack.append(f"<func:{qualname}>")
            elif opname == 'LOAD_BUILD_CLASS':
                stack.append('__build_class__')
            elif opname == 'IMPORT_NAME':
                stack.pop() if stack else None
                stack.pop() if stack else None
                stack.append(f"__import__({argval!r})")
            elif opname == 'DUP_TOP':
                val = stack[-1] if stack else '?'
                stack.append(val)
            elif opname == 'ROT_TWO':
                if len(stack) >= 2:
                    stack[-1], stack[-2] = stack[-2], stack[-1]
            elif opname == 'ROT_THREE':
                if len(stack) >= 3:
                    stack[-1], stack[-2], stack[-3] = stack[-2], stack[-3], stack[-1]
            elif opname == 'YIELD_VALUE':
                val = stack.pop() if stack else '?'
                stack.append(f"(yield {val})")
            elif opname == 'GEN_START':
                pass
            elif opname == 'LOAD_CLOSURE':
                stack.append(f"<closure:{argval}>")
            elif opname == 'BUILD_CONST_KEY_MAP':
                keys = stack.pop() if stack else '?'
                vals = [stack.pop() if stack else '?' for _ in range(arg)]
                vals.reverse()
                stack.append(f"dict(zip({keys}, [{', '.join(vals)}]))")
            elif opname in ('NOP', 'EXTENDED_ARG', 'PRECALL', 'RESUME', 'COPY_FREE_VARS'):
                pass
            elif opname == 'SETUP_FINALLY':
                lines.append(f"{prefix}# try:  (except at {argval})")
            elif opname == 'POP_EXCEPT':
                lines.append(f"{prefix}# end except")
            elif opname == 'RERAISE':
                lines.append(f"{prefix}# reraise")
            elif opname in ('PUSH_EXC_INFO', 'CHECK_EXC_MATCH', 'CHECK_EG_MATCH'):
                pass
            elif opname == 'FORMAT_VALUE':
                val = stack.pop() if stack else '?'
                stack.append(f"format({val})")
            elif opname == 'BUILD_STRING':
                items = [stack.pop() if stack else '?' for _ in range(arg)]
                items.reverse()
                stack.append(f"f_string({', '.join(items)})")
            else:
                lines.append(f"{prefix}# ?? {opname} arg={arg} stack={len(stack)}")
        except Exception as e:
            lines.append(f"{prefix}# ERROR at {offset}: {opname} - {e}")
            stack = []
    return lines

def decompile_all(co, path=""):
    results = []
    name = co.co_name
    full_path = f"{path}.{name}" if path else name
    args = list(co.co_varnames[:co.co_argcount])
    line_no = getattr(co, 'co_firstlineno', '?')

    results.append(f"\n{'#'*60}")
    results.append(f"# {full_path} (line {line_no})")
    results.append(f"# def {name}({', '.join(args)}):")
    results.append(f"# locals: {list(co.co_varnames)}")
    results.append(f"# names: {list(co.co_names)}")

    # Show non-code constants
    for i, c in enumerate(co.co_consts):
        if isinstance(c, types.CodeType):
            continue
        r = repr(c)
        if len(r) > 200:
            r = r[:200] + '...'
        results.append(f"# const[{i}] = {r}")

    results.append("")
    lines = decompile_function(co)
    results.extend(lines)

    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            results.extend(decompile_all(c, full_path))

    return results

all_lines = decompile_all(code)
output_path = sys.argv[2] if len(sys.argv) > 2 else 'xploit_decompiled.py'
with open(output_path, 'w') as f:
    f.write('\n'.join(all_lines))
print(f"Written {len(all_lines)} lines to {output_path}")
