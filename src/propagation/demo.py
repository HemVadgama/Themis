from tle_loader import load_satellites
from propagator import get_position, get_positions, get_position_table
from datetime import datetime, timezone, timedelta
import pandas as pd

now = datetime.now(timezone.utc)
times = []

for i in range(145):
    time = now + timedelta(minutes=10 * i)
    times.append(time)

satellites = load_satellites()
for sat in satellites[:5]:
    print(sat.name)

cal1 = satellites[0]
cal1_pos = get_positions(cal1, times)

df = pd.DataFrame(cal1_pos)
df.to_csv("results/CALSPHERE1_positions_24h.csv", index = False)
