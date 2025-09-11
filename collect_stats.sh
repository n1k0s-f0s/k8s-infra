RUNTIME=$1 # e.g., containerd or crio
OUTFILE=benchmark_${RUNTIME}_$(date +%s).log
DURATION=60
INTERVAL=5

echo "Collecting crictl stats for $RUNTIME every $INTERVALs for $DURATIONs..."
end=$((SECONDS + DURATION))
while [ $SECONDS -lt $end ]; do
  echo "Timestamp: $(date)" >> $OUTFILE
  crictl stats | grep flask-bgcolor >> $OUTFILE
  sleep $INTERVAL
done
echo "Stats saved to $OUTFILE"
