set -euo pipefail #stop on first error, in undefined variable and if pipeline fail
#---Power on variables---
NODE="cc2"
WOL_BROADCAST="192.168.90.255"
cc3_MAC="50:9a:4c:23:01:81"
CPU_TH=80                      		#Threshold in percent form
REQUIRED_CONSECUTIVE=2                	# hysteresis: checks must be high in a row
COOLDOWN=180                  		# in seconds (15 min)
STATE_DIR="/var/run/wol_autoscale" 	#state files-avoid sending wol every run
CAP_FILE="$STATE_DIR/capacity_cores" 	#stores CPU capacity - the script doesn’t query Kubernetes for CPU's core number every run
COUNT_FILE="$STATE_DIR/high_count" 	#how many times in a row CPU usage has been above the threshold - file resets to 0 if CPU is behind the thresshold - prevents waking cc3 on a single noisy spike
LASTWAKE_FILE="$STATE_DIR/lastwake" 	#timestamp of the last Wake-on-LAN event
#---Power off variables---
LOW_CPU_TH=35                           #Power-off threshold
REQUIRED_CONSECUTIVE_LOW=3              #hysteresis: lows must be consecutive to act
POWEROFF_COOLDOWN=180                   #time between poweroff attempts, in seconds (15 min)
CC3_HOST="192.168.90.249"                          #hostname or IP of cc3
CC3_USER="poweroff_user"                         #SSH user on cc3 (nopasswd sudo for poweroff)
SSH_KEY="/home/nfragos/.ssh/cc3_key"            #path to ssh private key for cc3
SSH_OPTS="-i ${SSH_KEY} -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=5"
LOW_COUNT_FILE="$STATE_DIR/low_count"
LASTPOWEROFF_FILE="$STATE_DIR/lastpoweroff"

mkdir -p "$STATE_DIR"


#If kubectl isn’t available quits silently (not as a failure). Usefull if metrics-server isn’t ready yet
command -v kubectl >/dev/null || { echo "kubectl not found" >&2; exit 0; }

#--- Get CPU usage
#-l1 runs kubectl top cc# without the header line and prints the CPU usage in millicores
#-l2 test if the string is empty. If yes exit 0. If not continue
#-l3 removes the m suffix [example: 850m -> 850]
#---
usage_m=$(kubectl top node "$NODE" --no-headers 2>/dev/null | awk '{print $2}')
[[ -z "${usage_m:-}" ]] && exit 0
usage_m=${usage_m%m}

#--- Cache capacity
#-l2 If the cache file doesn’t exist get the node’s CPU capacity.cap becomes empty if kubectl fails
#-l3 test if cap is empty
#-l4 writes capacity into the cache file
#---
if [[ ! -s "$CAP_FILE" ]]; then
  cap=$(kubectl get node "$NODE" -o jsonpath='{.status.capacity.cpu}' 2>/dev/null || echo "")
  [[ -z "$cap" ]] && exit 0
  echo "$cap" > "$CAP_FILE"
fi
capacity_cores=$(cat "$CAP_FILE") #reads the saved value

#--- Convert the millicores value into percentage of capacity
percent=$(awk -v u="$usage_m" -v c="$capacity_cores" 'BEGIN{printf "%.0f", (u/(c*1000))*100}')

#--- Update consecutive-high counter
#-l2 If file exists overwrite count with the number saved in the file.
#-l3 If cpu is above threshold increase counter, else reset to zero
#-l8 Write the updated counter into the state file
# ---
count=0
[[ -s "$COUNT_FILE" ]] && count="$(cat "$COUNT_FILE")"
if (( percent >= CPU_TH )); then
  ((++count))    # or: ((count+=1))
else
  count=0
fi
echo "$count" > "$COUNT_FILE"

# --- Update poweroff-counter ---
low_count=0
[[ -s "$LOW_COUNT_FILE" ]] && low_count="$(cat "$LOW_COUNT_FILE")"
if (( percent < LOW_CPU_TH )); then
  ((++low_count))
else
  low_count=0
fi
echo "$low_count" > "$LOW_COUNT_FILE"

#--- Cooldown
#-l1 prints the current timestamp
#-l2 wol number default to 0
#-l3 If file does not exist lastwake=0, else it reads the timestamp
#---
now=$(date +%s)
lastwake=0
[[ -s "$LASTWAKE_FILE" ]] && lastwake=$(cat "$LASTWAKE_FILE")
lastpoweroff=0
[[ -s "$LASTPOWEROFF_FILE" ]] && lastpoweroff=$(cat "$LASTPOWEROFF_FILE")

#--- Send the WOL packet
if (( count >= REQUIRED_CONSECUTIVE )) && (( now - lastwake >= COOLDOWN )); then
  if command -v wakeonlan >/dev/null 2>&1; then
    wakeonlan -i "$WOL_BROADCAST" "$cc3_MAC"
  elif command -v etherwake >/dev/null 2>&1; then
    etherwake "$cc3_MAC"
  else
    echo "No wakeonlan/etherwake installed" >&2
    exit 0
  fi
  echo "$now" > "$LASTWAKE_FILE"
  echo "$now" > "$LASTPOWEROFF_FILE"
fi

#--- Send ssh poweroff command
if (( low_count >= REQUIRED_CONSECUTIVE_LOW )) && (( now - lastpoweroff >= POWEROFF_COOLDOWN )); then
  # log attempt
  echo "autoscaler: low_count=$low_count; powering off ${CC3_HOST} as ${CC3_USER}" >&2
  if ssh $SSH_OPTS "${CC3_USER}@${CC3_HOST}" 'poweroff || /sbin/poweroff || systemctl poweroff || shutdown -h now'; then
    echo "$now" > "$LASTPOWEROFF_FILE"
  else
    echo "autoscaler: SSH to ${CC3_HOST} failed or poweroff not permitted." >&2
  fi
fi
