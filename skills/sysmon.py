"""System monitor skill — CPU, RAM, disk, network, top processes."""

META = {
    "name": "sysmon",
    "version": "1.0.0",
    "description": "系统资源监控：CPU/内存/磁盘/网络/进程排行（基于 psutil）",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "system_stats",
            "description": (
                "获取当前系统资源使用情况：CPU 使用率和频率、"
                "内存、交换分区、磁盘、实时网速"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_processes",
            "description": "列出 CPU 或内存占用最高的进程",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "显示前 N 个进程，默认 5",
                        "default": 5,
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "排序依据：'cpu' 或 'memory'，默认 'cpu'",
                        "default": "cpu",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disk_usage",
            "description": "查看所有磁盘分区的空间使用情况",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "network_stats",
            "description": "查看各网络接口的实时流量、累计收发量和连接数",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _bar(pct: float, width: int = 18) -> str:
    filled = int(pct / 100 * width)
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def execute(name: str, args: dict) -> dict:
    import psutil
    import time

    # ── system_stats ────────────────────────────────────────────────────────
    if name == "system_stats":
        cpu_pct = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()
        cores_logical = psutil.cpu_count(logical=True)
        cores_physical = psutil.cpu_count(logical=False)
        freq_str = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A"

        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        net1 = psutil.net_io_counters()
        time.sleep(0.5)
        net2 = psutil.net_io_counters()
        recv_kbs = (net2.bytes_recv - net1.bytes_recv) / 0.5 / 1024
        sent_kbs = (net2.bytes_sent - net1.bytes_sent) / 0.5 / 1024

        lines = [
            "📊 系统资源监控",
            f"🖥️  CPU    {cpu_pct:5.1f}%  [{_bar(cpu_pct)}]  "
            f"{cores_physical}C/{cores_logical}T @ {freq_str}",
            f"🧠 内存   {mem.percent:5.1f}%  [{_bar(mem.percent)}]  "
            f"{mem.used/1024**3:.1f} / {mem.total/1024**3:.1f} GB",
        ]

        if swap.total > 0:
            lines.append(
                f"💾 交换   {swap.percent:5.1f}%  [{_bar(swap.percent)}]  "
                f"{swap.used/1024**3:.1f} / {swap.total/1024**3:.1f} GB"
            )

        # Primary disk (C: on Windows)
        for mp in ("C:/", "/"):
            try:
                disk = psutil.disk_usage(mp)
                lines.append(
                    f"💿 磁盘   {disk.percent:5.1f}%  [{_bar(disk.percent)}]  "
                    f"{disk.used/1024**3:.1f} / {disk.total/1024**3:.1f} GB"
                )
                break
            except Exception:
                continue

        lines.append(f"🌐 网速   ↓ {recv_kbs:7.1f} KB/s   ↑ {sent_kbs:7.1f} KB/s")

        boot = psutil.boot_time()
        uptime_s = time.time() - boot
        h, rem = divmod(int(uptime_s), 3600)
        m = rem // 60
        lines.append(f"⏱️  运行   {h}h {m:02d}m")

        return {"ok": True, "result": "\n".join(lines)}

    # ── top_processes ────────────────────────────────────────────────────────
    if name == "top_processes":
        n = max(1, int(args.get("n", 5)))
        sort_by = args.get("sort_by", "cpu").lower()

        # First pass — collect
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
            try:
                mi = p.info["memory_info"]
                procs.append({
                    "pid": p.info["pid"],
                    "name": (p.info["name"] or "")[:28],
                    "cpu": p.info["cpu_percent"] or 0.0,
                    "mem_mb": mi.rss / 1024**2 if mi else 0.0,
                    "status": p.info["status"],
                })
            except Exception:
                continue

        # Let cpu_percent settle with a short interval
        time.sleep(0.5)
        pid_cpu: dict[int, float] = {}
        for p in psutil.process_iter(["pid", "cpu_percent"]):
            try:
                pid_cpu[p.pid] = p.cpu_percent() or 0.0
            except Exception:
                pass
        for proc in procs:
            proc["cpu"] = pid_cpu.get(proc["pid"], proc["cpu"])

        key = "cpu" if sort_by != "memory" else "mem_mb"
        top = sorted(procs, key=lambda x: x[key], reverse=True)[:n]
        sort_label = "CPU" if key == "cpu" else "内存"

        header = f"{'PID':>7}  {'进程名':<28}  {'CPU%':>6}  {'内存':>8}  状态"
        rows = [f"🔝 {sort_label} 占用 Top {n}:", header, "─" * 62]
        for p in top:
            rows.append(
                f"{p['pid']:>7}  {p['name']:<28}  {p['cpu']:>5.1f}%  "
                f"{p['mem_mb']:>6.1f} MB  {p['status']}"
            )
        return {"ok": True, "result": "\n".join(rows)}

    # ── disk_usage ───────────────────────────────────────────────────────────
    if name == "disk_usage":
        lines = ["💿 磁盘分区使用情况:"]
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                pct = usage.percent
                lines.append(
                    f"  {part.device:<10} {part.mountpoint:<8}  "
                    f"{pct:5.1f}%  [{_bar(pct, 16)}]  "
                    f"{_fmt_bytes(usage.used):>10} / {_fmt_bytes(usage.total):<10}  "
                    f"({part.fstype})"
                )
            except Exception:
                continue
        return {"ok": True, "result": "\n".join(lines)}

    # ── network_stats ────────────────────────────────────────────────────────
    if name == "network_stats":
        counters = psutil.net_io_counters(pernic=True)
        lines = ["🌐 网络接口统计:"]
        for iface, st in counters.items():
            if st.bytes_sent == 0 and st.bytes_recv == 0:
                continue
            lines.append(
                f"  {iface}:\n"
                f"    ↑ 发送 {_fmt_bytes(st.bytes_sent)}  "
                f"↓ 接收 {_fmt_bytes(st.bytes_recv)}  "
                f"错误 {st.errin + st.errout}  丢包 {st.dropin + st.dropout}"
            )
        try:
            conns = psutil.net_connections()
            established = sum(1 for c in conns if c.status == "ESTABLISHED")
            listen = sum(1 for c in conns if c.status == "LISTEN")
            lines.append(f"\n  TCP 连接：{established} 个已建立  {listen} 个监听中")
        except Exception:
            pass
        return {"ok": True, "result": "\n".join(lines)}

    return {"ok": False, "result": f"Unknown tool: {name}"}
