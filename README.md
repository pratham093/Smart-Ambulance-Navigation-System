# Smart-Ambulance-Navigation-System

The **Smart Ambulance Navigation System** is an intelligent simulation designed to optimize ambulance routing by minimizing travel time and avoiding traffic congestion. It uses real-time traffic data, dynamic rerouting algorithms, and traffic light control to ensure ambulances reach destinations as fast as possible.

---

## Features

- Real-time ambulance rerouting based on traffic conditions
- Traffic congestion detection and avoidance
- Traffic light preemption for ambulances
- Dynamic selection of destination points
- Supports multiple routing algorithms:
  - Dijkstra's Algorithm
  - A* Search
  - Bellman-Ford (BHK variant)
  - A* with Bee Colony Optimization (A* + BCO)

---

## Technologies Used

- **Python** (Core simulation)
- **SUMO** (Simulation of Urban Mobility)
- **TraCI** (Traffic Control Interface)
- **NetworkX** (Graph processing)
- **Matplotlib** (Data visualization)

---

## Installation

1. Install [SUMO](https://sumo.dlr.de/docs/Installing.html) and ensure it is added to your system PATH.
2. Install Python dependencies:

```bash
pip install networkx matplotlib
```

---

## How to Run

1. Configure your SUMO environment with your `.sumocfg` file.
2. Update the ambulance settings in the script:

```python
SUMO_CONFIG_FILE = "your_network.sumocfg"
AMBULANCE_ID = "ambulance_trip"
DEST_EDGE = "destination_edge_id"
```

3. Run the simulation:

```bash
python your_script.py
```

4. Output graphs and a metrics CSV will be generated automatically.

---

## Output Files

- `metrics.csv` - Stores time, speed, distance, and traffic volume data
- `speed_vs_time.png` - Graph of Ambulance Speed vs Time
- `distance_vs_time.png` - Graph of Distance Covered vs Time
- `vehicles_vs_time.png` - Graph of Traffic Volume vs Time

---

## Project Structure

```
Smart-Ambulance-Navigation-System/
├── your_script.py
├── metrics.csv
├── speed_vs_time.png
├── distance_vs_time.png
├── vehicles_vs_time.png
└── README.md
```

---

## Future Improvements

- Integrate real-time traffic API data (Google Maps, OpenStreetMap)
- Multi-ambulance coordination
- Dynamic hospital selection based on availability
- Predictive traffic analysis using machine learning


