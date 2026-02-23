"""Math, unit conversion, and statistics skill — pure Python, no external dependencies."""

META = {
    "name": "math_tools",
    "version": "1.0.0",
    "description": "数学计算、单位换算、统计分析（纯 Python，无外部依赖）",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "安全计算数学表达式。支持：四则运算、幂运算、取余、括号嵌套、"
                "常用函数（sqrt/sin/cos/tan/log/log2/log10/abs/ceil/floor/round）、"
                "常量（pi/e/inf），例：sqrt(2) * sin(pi/4)、2**32、log(1000, 10)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式字符串"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_unit",
            "description": (
                "单位换算。支持：长度、重量、温度、速度、面积、体积、时间、数据存储、能量、压强。"
                "示例：100 km → miles，32 fahrenheit → celsius，1 GB → MB"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "number", "description": "要换算的数值"},
                    "from_unit": {"type": "string", "description": "源单位，如 km、lb、F、GB"},
                    "to_unit": {"type": "string", "description": "目标单位，如 miles、kg、C、MB"},
                },
                "required": ["value", "from_unit", "to_unit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "statistics_calc",
            "description": "对一组数字进行统计分析：均值、中位数、众数、标准差、方差、百分位数等",
            "parameters": {
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "数字列表",
                    },
                    "operations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要计算的统计量，留空则返回全部：mean/median/mode/std/var/min/max/sum/range/percentile",
                    },
                },
                "required": ["numbers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "number_base_convert",
            "description": "数字进制转换：二进制、八进制、十进制、十六进制互转",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "要转换的数值（字符串形式）"},
                    "from_base": {
                        "type": "integer",
                        "description": "源进制：2/8/10/16",
                    },
                    "to_base": {
                        "type": "integer",
                        "description": "目标进制：2/8/10/16",
                    },
                },
                "required": ["value", "from_base", "to_base"],
            },
        },
    },
]

import ast
import math
import operator as op

# ── Safe expression evaluator ────────────────────────────────────────────────

_SAFE_FUNCS = {
    "sqrt": math.sqrt, "cbrt": lambda x: x ** (1/3),
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log, "log2": math.log2, "log10": math.log10, "exp": math.exp,
    "abs": abs, "ceil": math.ceil, "floor": math.floor, "round": round,
    "pow": math.pow, "hypot": math.hypot, "gcd": math.gcd,
    "factorial": math.factorial, "comb": math.comb, "perm": math.perm,
    "degrees": math.degrees, "radians": math.radians,
    "pi": math.pi, "e": math.e, "inf": math.inf, "tau": math.tau,
}

_ALLOWED_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.FloorDiv: op.floordiv,
    ast.Pow: op.pow, ast.Mod: op.mod,
    ast.USub: op.neg, ast.UAdd: op.pos,
    ast.BitAnd: op.and_, ast.BitOr: op.or_, ast.BitXor: op.xor,
    ast.LShift: op.lshift, ast.RShift: op.rshift,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"不支持的常量类型: {type(node.value)}")

    if isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCS:
            return _SAFE_FUNCS[node.id]
        raise ValueError(f"未知名称: {node.id}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _ALLOWED_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
        return _ALLOWED_OPS[op_type](_eval_node(node.operand))

    if isinstance(node, ast.Call):
        func = _eval_node(node.func)
        if not callable(func):
            raise ValueError("不可调用的对象")
        args_vals = [_eval_node(a) for a in node.args]
        return func(*args_vals)

    raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


def safe_eval(expr: str):
    expr = expr.strip().replace("^", "**")  # allow ^ as power
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body)


# ── Unit conversion tables ────────────────────────────────────────────────────

# All units expressed as multiples of a base unit
_UNITS: dict[str, dict[str, float]] = {
    # Length (base: meter)
    "length": {
        "m": 1, "meter": 1, "meters": 1, "metre": 1,
        "km": 1000, "kilometer": 1000, "kilometres": 1000,
        "cm": 0.01, "centimeter": 0.01,
        "mm": 0.001, "millimeter": 0.001,
        "um": 1e-6, "micrometer": 1e-6,
        "nm": 1e-9, "nanometer": 1e-9,
        "mile": 1609.344, "miles": 1609.344, "mi": 1609.344,
        "yard": 0.9144, "yards": 0.9144, "yd": 0.9144,
        "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
        "inch": 0.0254, "inches": 0.0254, "in": 0.0254,
        "nautical_mile": 1852, "nm_sea": 1852,
        "光年": 9.461e15, "light_year": 9.461e15,
    },
    # Weight / mass (base: kg)
    "mass": {
        "kg": 1, "kilogram": 1, "kilograms": 1,
        "g": 0.001, "gram": 0.001, "grams": 0.001,
        "mg": 1e-6, "milligram": 1e-6,
        "t": 1000, "ton": 1000, "tonne": 1000, "metric_ton": 1000,
        "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592, "pounds": 0.453592,
        "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
        "stone": 6.35029,
        "斤": 0.5, "两": 0.05, "克": 0.001, "千克": 1,
    },
    # Speed (base: m/s)
    "speed": {
        "m/s": 1, "ms": 1,
        "km/h": 1/3.6, "kmh": 1/3.6, "kph": 1/3.6,
        "mph": 0.44704, "miles/h": 0.44704,
        "knot": 0.514444, "knots": 0.514444,
        "ft/s": 0.3048,
        "mach": 343,
    },
    # Area (base: m²)
    "area": {
        "m2": 1, "m²": 1, "sqm": 1,
        "km2": 1e6, "km²": 1e6,
        "cm2": 1e-4, "cm²": 1e-4,
        "mm2": 1e-6, "mm²": 1e-6,
        "ha": 1e4, "hectare": 1e4, "公顷": 1e4,
        "acre": 4046.86, "acres": 4046.86,
        "sqft": 0.092903, "ft2": 0.092903,
        "sqmi": 2.59e6, "mi2": 2.59e6,
        "亩": 666.67,
    },
    # Volume (base: liter)
    "volume": {
        "l": 1, "liter": 1, "litre": 1, "liters": 1,
        "ml": 0.001, "milliliter": 0.001, "millilitre": 0.001,
        "m3": 1000, "m³": 1000, "cubic_meter": 1000,
        "cm3": 0.001, "cm³": 0.001, "cc": 0.001,
        "gallon": 3.78541, "gal": 3.78541, "gallons": 3.78541,
        "quart": 0.946353, "qt": 0.946353,
        "pint": 0.473176, "pt": 0.473176,
        "cup": 0.236588, "fl_oz": 0.0295735,
        "tbsp": 0.0147868, "tsp": 0.00492892,
    },
    # Time (base: second)
    "time": {
        "s": 1, "sec": 1, "second": 1, "seconds": 1,
        "ms": 0.001, "millisecond": 0.001,
        "us": 1e-6, "microsecond": 1e-6,
        "min": 60, "minute": 60, "minutes": 60,
        "h": 3600, "hour": 3600, "hours": 3600, "hr": 3600,
        "day": 86400, "days": 86400,
        "week": 604800, "weeks": 604800,
        "month": 2592000, "months": 2592000,
        "year": 31536000, "years": 31536000,
    },
    # Data (base: byte)
    "data": {
        "b": 1, "byte": 1, "bytes": 1,
        "kb": 1024, "kilobyte": 1024,
        "mb": 1024**2, "megabyte": 1024**2,
        "gb": 1024**3, "gigabyte": 1024**3,
        "tb": 1024**4, "terabyte": 1024**4,
        "pb": 1024**5, "petabyte": 1024**5,
        "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4,
        "bit": 0.125, "bits": 0.125,
        "kbps": 125, "mbps": 125000,
    },
    # Energy (base: joule)
    "energy": {
        "j": 1, "joule": 1, "joules": 1,
        "kj": 1000, "kilojoule": 1000,
        "mj": 1e6, "megajoule": 1e6,
        "cal": 4.184, "calorie": 4.184, "calories": 4.184,
        "kcal": 4184, "kilocalorie": 4184,
        "wh": 3600, "kwh": 3.6e6,
        "ev": 1.602e-19, "electronvolt": 1.602e-19,
        "btu": 1055.06,
    },
    # Pressure (base: pascal)
    "pressure": {
        "pa": 1, "pascal": 1,
        "kpa": 1000, "kilopascal": 1000,
        "mpa": 1e6, "megapascal": 1e6,
        "bar": 1e5,
        "mbar": 100,
        "atm": 101325, "atmosphere": 101325,
        "psi": 6894.76,
        "mmhg": 133.322, "torr": 133.322,
        "inhg": 3386.39,
    },
}

_TEMP_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin", "°c", "°f"}


def _find_unit(unit: str):
    u = unit.lower().strip().replace(" ", "_")
    for category, table in _UNITS.items():
        if u in table:
            return category, u
    return None, None


def _convert_temp(value: float, from_u: str, to_u: str) -> float:
    f = from_u.rstrip("elsius").rstrip("ahrenheit").rstrip("elvin").replace("°", "")
    t = to_u.rstrip("elsius").rstrip("ahrenheit").rstrip("elvin").replace("°", "")
    # Normalize
    f = "c" if "c" in f else ("f" if "f" in f else "k")
    t = "c" if "c" in t else ("f" if "f" in t else "k")

    # To Celsius first
    if f == "f":
        celsius = (value - 32) * 5 / 9
    elif f == "k":
        celsius = value - 273.15
    else:
        celsius = value

    if t == "f":
        return celsius * 9 / 5 + 32
    elif t == "k":
        return celsius + 273.15
    return celsius


# ── Statistics ───────────────────────────────────────────────────────────────

def _statistics(numbers: list[float], operations: list[str]) -> dict:
    import statistics as stat

    n = len(numbers)
    sorted_nums = sorted(numbers)
    total = sum(numbers)

    def _percentile(p):
        idx = (n - 1) * p / 100
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        return sorted_nums[lo] + (sorted_nums[hi] - sorted_nums[lo]) * (idx - lo)

    all_ops = {
        "count":  n,
        "sum":    total,
        "mean":   total / n,
        "median": stat.median(numbers),
        "mode":   stat.mode(numbers) if n > 1 else numbers[0],
        "std":    stat.stdev(numbers) if n > 1 else 0,
        "var":    stat.variance(numbers) if n > 1 else 0,
        "min":    sorted_nums[0],
        "max":    sorted_nums[-1],
        "range":  sorted_nums[-1] - sorted_nums[0],
        "q1":     _percentile(25),
        "q3":     _percentile(75),
        "p90":    _percentile(90),
        "p95":    _percentile(95),
        "p99":    _percentile(99),
    }

    if not operations:
        return all_ops
    return {k: all_ops[k] for k in operations if k in all_ops}


# ── Main execute ─────────────────────────────────────────────────────────────

def execute(name: str, args: dict) -> dict:

    if name == "calculate":
        expr = args["expression"].strip()
        if len(expr) > 500:
            return {"ok": False, "result": "表达式过长"}
        try:
            result = safe_eval(expr)
        except ZeroDivisionError:
            return {"ok": False, "result": "错误：除以零"}
        except (ValueError, TypeError) as e:
            return {"ok": False, "result": f"计算错误: {e}"}
        except Exception as e:
            return {"ok": False, "result": f"无效表达式: {e}"}

        # Format result
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                fmt = str(int(result))
            else:
                fmt = f"{result:.10g}"
        elif isinstance(result, complex):
            fmt = str(result)
        else:
            fmt = str(result)

        return {"ok": True, "result": f"🧮 {expr}\n= {fmt}"}

    if name == "convert_unit":
        value = float(args["value"])
        from_unit = args["from_unit"].strip()
        to_unit = args["to_unit"].strip()

        # Temperature special case
        fu_l = from_unit.lower()
        tu_l = to_unit.lower()
        if any(t in fu_l for t in _TEMP_UNITS) or any(t in tu_l for t in _TEMP_UNITS):
            try:
                result = _convert_temp(value, fu_l, tu_l)
                return {"ok": True, "result": f"🌡️ {value} {from_unit} = {result:.6g} {to_unit}"}
            except Exception as e:
                return {"ok": False, "result": f"温度换算失败: {e}"}

        cat_f, key_f = _find_unit(from_unit)
        cat_t, key_t = _find_unit(to_unit)

        if cat_f is None:
            return {"ok": False, "result": f"未知单位: {from_unit}"}
        if cat_t is None:
            return {"ok": False, "result": f"未知单位: {to_unit}"}
        if cat_f != cat_t:
            return {"ok": False, "result": f"单位类别不匹配：{from_unit}（{cat_f}）≠ {to_unit}（{cat_t}）"}

        table = _UNITS[cat_f]
        base_value = value * table[key_f]
        result = base_value / table[key_t]
        return {"ok": True, "result": f"📐 {value} {from_unit} = {result:.8g} {to_unit}  [{cat_f}]"}

    if name == "statistics_calc":
        numbers = [float(x) for x in args["numbers"]]
        operations = args.get("operations", [])
        if not numbers:
            return {"ok": False, "result": "数字列表不能为空"}
        if len(numbers) > 10000:
            return {"ok": False, "result": "数字过多，最多支持 10000 个"}

        try:
            stats = _statistics(numbers, operations)
        except Exception as e:
            return {"ok": False, "result": f"统计计算失败: {e}"}

        label_map = {
            "count": "数量", "sum": "总和", "mean": "均值", "median": "中位数",
            "mode": "众数", "std": "标准差", "var": "方差", "min": "最小值",
            "max": "最大值", "range": "极差", "q1": "Q1(25%)", "q3": "Q3(75%)",
            "p90": "P90", "p95": "P95", "p99": "P99",
        }
        lines = [f"📊 统计分析（{len(numbers)} 个数字）"]
        for k, v in stats.items():
            label = label_map.get(k, k)
            if isinstance(v, float):
                lines.append(f"  {label:<12}: {v:.6g}")
            else:
                lines.append(f"  {label:<12}: {v}")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "number_base_convert":
        value_str = str(args["value"]).strip()
        from_base = int(args["from_base"])
        to_base = int(args["to_base"])

        if from_base not in (2, 8, 10, 16):
            return {"ok": False, "result": "源进制必须是 2/8/10/16"}
        if to_base not in (2, 8, 10, 16):
            return {"ok": False, "result": "目标进制必须是 2/8/10/16"}

        try:
            decimal = int(value_str, from_base)
        except ValueError:
            return {"ok": False, "result": f"'{value_str}' 不是有效的 {from_base} 进制数"}

        fmt_map = {2: bin, 8: oct, 10: str, 16: hex}
        result = fmt_map[to_base](decimal)

        # Clean prefix
        if result.startswith(("0b", "0o", "0x")):
            result_clean = result[2:].upper() if to_base == 16 else result[2:]
        else:
            result_clean = result

        base_names = {2: "二进制", 8: "八进制", 10: "十进制", 16: "十六进制"}
        prefixes = {2: "0b", 8: "0o", 10: "", 16: "0x"}

        lines = [
            f"🔢 进制转换",
            f"  输入：{prefixes[from_base]}{value_str.upper() if from_base==16 else value_str} ({base_names[from_base]})",
            f"  十进制：{decimal}",
            f"  输出：{result} ({base_names[to_base]})",
        ]
        if to_base == 16:
            lines.append(f"  大写：{prefixes[16]}{result_clean}")
        return {"ok": True, "result": "\n".join(lines)}

    return {"ok": False, "result": f"Unknown tool: {name}"}
