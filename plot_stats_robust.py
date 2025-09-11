import sys
from datetime import datetime
import matplotlib.pyplot as plt

LOG_FILE = sys.argv[1] if len(sys.argv) > 1 else "benchmark_containerd_1756888754.log"
NAME_FILTER = sys.argv[2] if len(sys.argv) > 2 else "flask-bgcolor"
SAVE = True  # always save PNGs for headless servers

def parse_memory(mem_str):
    s = mem_str.strip()
    try:
        if s.endswith("MB"):
            return float(s[:-2])
        if s.endswith("KB"):
            return float(s[:-2]) / 1024.0
        if s.endswith("GB"):
            return float(s[:-2]) * 1024.0
        if s.endswith("B"):
            return 0.0
        return float(s)  # last resort
    except:
        return 0.0

timestamps = []
total_cpu = []   # sum of CPU across replicas (in "cores" or "%-like" depending on crictl format)
total_mem = []   # sum of memory MB across replicas

with open(LOG_FILE) as f:
    lines = [ln.rstrip("\n") for ln in f]

current_ts = None
agg_cpu = 0.0
agg_mem = 0.0
agg_count = 0
seen_any_timestamp = False

def flush_bucket():
    if current_ts is not None and agg_count > 0:
        timestamps.append(current_ts)
        total_cpu.append(agg_cpu)
        total_mem.append(agg_mem)

i = 0
while i < len(lines):
    line = lines[i].strip()
    i += 1
    if not line:
        continue

    # Timestamp header?
    if line.startswith("Timestamp:"):
        # close previous bucket
        flush_bucket()
        seen_any_timestamp = True
        ts_text = line.replace("Timestamp:", "", 1).strip()
        # Format example: Thu Aug 28 07:07:37 AM UTC 2025
        try:
            current_ts = datetime.strptime(ts_text, "%a %b %d %I:%M:%S %p UTC %Y")
        except ValueError:
            # If format differs, store raw text (string) so we can still plot categorical x-axis
            current_ts = ts_text
        agg_cpu = 0.0
        agg_mem = 0.0
        agg_count = 0
        continue

    # Otherwise, it's a stats line (containerID name cpu mem net pids ...)
    # Example columns:
    # 0:containerID 1:name 2:CPU 3:MEM 4:NET 5:PIDS
    parts = line.split()
    if len(parts) < 4:
        continue

    name = parts[1]
    if NAME_FILTER.lower() not in name.lower():
        # some crictl builds put NAME at a different index; try to recover:
        # Find the column that equals NAME_FILTER
        if NAME_FILTER.lower() not in line.lower():
            continue

    # Find CPU and MEM columns robustly:
    # Heuristic: first token that can be float is CPU; the next token is MEM string
    cpu_val = None
    mem_val = None
    # Try normal indices first (2 and 3)
    try:
        cpu_val = float(parts[2])
        mem_val = parse_memory(parts[3])
    except:
        # Fallback: scan tokens
        for idx in range(2, len(parts)):
            try:
                cpu_val = float(parts[idx])
                if idx + 1 < len(parts):
                    mem_val = parse_memory(parts[idx + 1])
                break
            except:
                continue

    if cpu_val is None or mem_val is None:
        continue

    # If we never saw a timestamp, emulate buckets per line
    if not seen_any_timestamp and current_ts is None:
        current_ts = len(timestamps)  # sample index
        agg_cpu = 0.0
        agg_mem = 0.0
        agg_count = 0

    agg_cpu += cpu_val
    agg_mem += mem_val
    agg_count += 1

# flush last bucket
flush_bucket()

if not timestamps:
    print("No data parsed. Check your log content or filters.")
    sys.exit(1)

# ---- Plot ----
# If timestamps contain datetimes, they’ll plot as time; otherwise as categories/indices.
plt.figure(figsize=(10, 4))
plt.plot(timestamps, total_cpu, marker="o", label=f"Total CPU ({NAME_FILTER})")
plt.xlabel("Time" if seen_any_timestamp else "Sample #")
plt.ylabel("CPU (crictl units)")
plt.title("Aggregated Container CPU Over Time")
plt.grid(True)
plt.tight_layout()
if SAVE:
    plt.savefig("cpu_total1.png")
    print("Saved cpu_total1.png")
else:
    plt.show()

plt.figure(figsize=(10, 4))
plt.plot(timestamps, total_mem, marker="o", label=f"Total Memory MB ({NAME_FILTER})")
plt.xlabel("Time" if seen_any_timestamp else "Sample #")
plt.ylabel("Memory (MB)")
plt.title("Aggregated Container Memory Over Time")
plt.grid(True)
plt.tight_layout()
if SAVE:
    plt.savefig("mem_total1.png")
    print("Saved mem_total1.png")
else:
    plt.show()
