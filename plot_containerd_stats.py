import matplotlib.pyplot as plt
from datetime import datetime

# File to read
LOG_FILE = "benchmark_containerd_1756807937.log"

# Data containers
timestamps = []
cpu_usages = []
memory_usages = []

# Converts "20.18MB", "167.9kB", etc. to MB
def parse_memory(mem_str):
    try:
        if "MB" in mem_str:
            return float(mem_str.replace("MB", ""))
        elif "KB" in mem_str:
            return float(mem_str.replace("KB", "")) / 1024
        elif "GB" in mem_str:
            return float(mem_str.replace("GB", "")) * 1024
        else:
            return 0.0
    except:
        return 0.0

# Read and parse file
try:
    with open(LOG_FILE) as f:
        lines = f.readlines()

    for i in range(0, len(lines), 2):
        ts_line = lines[i].strip().replace("Timestamp: ", "")
        stat_line = lines[i + 1].strip().split()

        try:
            timestamps.append(datetime.strptime(ts_line, "%a %b %d %I:%M:%S %p %Z %Y"))
            cpu_usages.append(float(stat_line[2]))
            memory_usages.append(parse_memory(stat_line[3]))
        except Exception as e:
            print(f"Skipping invalid line: {e}")

except FileNotFoundError:
    print(f"Log file not found: {LOG_FILE}")
    exit(1)

# Check if data was parsed
if not timestamps:
    print("No data parsed. Check your log format.")
    exit(1)

# Print first few entries for debug
print("Parsed entries:", len(timestamps))
for i in range(min(3, len(timestamps))):
    print(f"  Time: {timestamps[i]}, CPU: {cpu_usages[i]}, Mem: {memory_usages[i]}")

# ----------------- PLOTTING -----------------

# Plot CPU usage
plt.figure(figsize=(10, 4))
plt.plot(timestamps, cpu_usages, marker="o", color="tab:red", label="CPU Usage (cores)")
plt.xlabel("Time")
plt.ylabel("CPU Usage (cores)")
plt.title("Container CPU Usage Over Time")
plt.grid(True)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("cpu_plot1.png")
print("Saved CPU plot to cpu_plot.png")

# Plot Memory usage
plt.figure(figsize=(10, 4))
plt.plot(timestamps, memory_usages, marker="o", color="tab:blue", label="Memory Usage (MB)")
plt.xlabel("Time")
plt.ylabel("Memory Usage (MB)")
plt.title("Container Memory Usage Over Time")
plt.grid(True)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("memory_plot1.png")
print("Saved memory plot to memory_plot.png")
