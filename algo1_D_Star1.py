import traci
import time
import math
import networkx as nx
import os
import matplotlib.pyplot as plt
import csv
from dstar_lite import DStarLite  # Ensure this module is implemented or available

# ----- Configuration -----
SUMO_CONFIG_FILE = "osm.sumocfg"
AMBULANCE_ID = "ambulance_trip"
WAIT_TIME = 100
PREEMPTION_GREEN_STATE = "G"
SOURCE_EDGE = "-1285481595"
DEST_EDGE = "-1180132072#1"
ALGORITHM_FOLDER = "DstarLite"
REPLAN_INTERVAL = 5  # seconds
# --------------------------

def get_lane_ids(edge):
    try:
        num = traci.edge.getLaneNumber(edge)
        return [f"{edge}_{i}" for i in range(num)]
    except:
        return []

def build_network_graph():
    G = nx.DiGraph()
    for edge in traci.edge.getIDList():
        if edge.startswith(":"):
            continue
        G.add_node(edge)
        for lane_id in get_lane_ids(edge):
            try:
                links = traci.lane.getLinks(lane_id)
            except Exception:
                continue
            for link in links:
                target_lane_id = link[0]
                target_edge = traci.lane.getEdgeID(target_lane_id)
                if target_edge.startswith(":"):
                    continue
                try:
                    lane_ids = get_lane_ids(edge)
                    length = traci.lane.getLength(lane_ids[0]) if lane_ids else 1.0
                except Exception:
                    length = 1.0
                G.add_edge(edge, target_edge, weight=length)
    return G

def get_edge_coords():
    coords = {}
    for edge_id in traci.edge.getIDList():
        if edge_id.startswith(":"):
            continue
        try:
            shape = traci.edge.getShape(edge_id)
            if shape:
                x, y = shape[0]
                coords[edge_id] = (x, y)
        except:
            continue
    return coords

def euclidean_heuristic(u, v, coords):
    x1, y1 = coords.get(u, (0, 0))
    x2, y2 = coords.get(v, (0, 0))
    return math.hypot(x2 - x1, y2 - y1)

def preempt_traffic_signals(route, preempted_signals):
    for tls in traci.trafficlight.getIDList():
        try:
            controlled_lanes = traci.trafficlight.getControlledLanes(tls)
            for lane in controlled_lanes:
                edge_id = traci.lane.getEdgeID(lane)
                if edge_id in route:
                    current_state = traci.trafficlight.getRedYellowGreenState(tls)
                    green_state = PREEMPTION_GREEN_STATE * len(current_state)
                    traci.trafficlight.setRedYellowGreenState(tls, green_state)
                    if tls not in preempted_signals:
                        print(f"🚦 Preempted signal {tls} (edge: {edge_id})")
                        preempted_signals.add(tls)
                    break
        except:
            continue

def save_metrics_csv(metrics, folder, resume_time):
    os.makedirs(folder, exist_ok=True)
    file = os.path.join(folder, "metrics.csv")
    with open(file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
        writer.writeheader()
        for m in metrics:
            if m["simulation_time"] >= resume_time:
                writer.writerow(m)
    print(f"📄 Saved metrics: {file}")

def save_metric_graphs(metrics, folder, resume_time):
    os.makedirs(folder, exist_ok=True)
    filtered = [m for m in metrics if m["simulation_time"] >= resume_time]
    if not filtered:
        print("⚠️ No data to plot.")
        return

    t = [m["simulation_time"] - resume_time for m in filtered]
    s = [m["ambulance_speed"] for m in filtered]
    d = [m["ambulance_distance_covered"] for m in filtered]
    v = [m["num_vehicles"] for m in filtered]

    plt.figure()
    plt.plot(t, s, label="Speed (m/s)", color='blue')
    plt.xlabel("Time (s)"); plt.ylabel("Speed"); plt.title("Speed vs Time")
    plt.savefig(os.path.join(folder, "speed.png")); plt.close()

    plt.figure()
    plt.plot(t, d, label="Distance (m)", color='green')
    plt.xlabel("Time (s)"); plt.ylabel("Distance"); plt.title("Distance vs Time")
    plt.savefig(os.path.join(folder, "distance.png")); plt.close()

    plt.figure()
    plt.plot(t, v, label="Vehicles", color='red')
    plt.xlabel("Time (s)"); plt.ylabel("Vehicles"); plt.title("Vehicles vs Time")
    plt.savefig(os.path.join(folder, "vehicles.png")); plt.close()

    print(f"📊 Plots saved in: {folder}")

def display_summary(metrics, resume_time, reaching_time):
    filtered = [m for m in metrics if m["simulation_time"] >= resume_time]
    speeds = [m["ambulance_speed"] for m in filtered]
    distances = [m["ambulance_distance_covered"] for m in filtered]
    vehicles = [m["num_vehicles"] for m in filtered]

    print("\n📈 Summary:")
    print(f"⏱️  Travel Time: {reaching_time - resume_time:.2f} sec")
    print(f"📏 Distance: {distances[-1]:.2f} m")
    print(f"🚀 Avg Speed: {sum(speeds)/len(speeds):.2f} m/s")
    print(f"⚡ Max Speed: {max(speeds):.2f} m/s")
    print(f"🚗 Avg Vehicles: {sum(vehicles)//len(vehicles)}")

def main():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG_FILE])
    for _ in range(5): traci.simulationStep(); time.sleep(0.1)

    while AMBULANCE_ID not in traci.vehicle.getIDList():
        traci.simulationStep(); time.sleep(0.1)

    current_lane = traci.vehicle.getLaneID(AMBULANCE_ID)
    current_edge = traci.lane.getEdgeID(current_lane)
    current_pos = traci.vehicle.getLanePosition(AMBULANCE_ID)
    traci.vehicle.setStop(AMBULANCE_ID, current_edge, pos=current_pos, duration=WAIT_TIME)
    print(f"🛑 Ambulance holding at {current_edge}, pos={current_pos:.2f}")

    start_stop_time = traci.simulation.getTime()
    metrics = []
    while traci.simulation.getTime() - start_stop_time < WAIT_TIME:
        sim_time = traci.simulation.getTime()
        try:
            lane = traci.vehicle.getLaneID(AMBULANCE_ID)
            edge = traci.lane.getEdgeID(lane)
            speed = traci.vehicle.getSpeed(AMBULANCE_ID)
        except:
            edge, speed = "N/A", 0.0
        num_vehicles = len(traci.vehicle.getIDList())
        metrics.append({
            "simulation_time": sim_time,
            "ambulance_edge": edge,
            "ambulance_speed": speed,
            "ambulance_distance_covered": 0.0,
            "num_vehicles": num_vehicles
        })
        traci.simulationStep(); time.sleep(0.1)

    graph = build_network_graph()
    coords = get_edge_coords()
    planner = DStarLite(graph, coords)
    route = planner.replan(current_edge, DEST_EDGE)
    traci.vehicle.setRoute(AMBULANCE_ID, route)
    print(f"🚑 Initial route: {route}")

    resume_time = traci.simulation.getTime()
    traci.vehicle.resume(AMBULANCE_ID)
    preempted_signals = set()
    reaching_time = None
    last_replan_time = resume_time

    while traci.simulation.getMinExpectedNumber() > 0:
        sim_time = traci.simulation.getTime()
        try:
            current_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
            speed = traci.vehicle.getSpeed(AMBULANCE_ID)
            pos = traci.vehicle.getLanePosition(AMBULANCE_ID)
        except:
            break

        num_vehicles = len(traci.vehicle.getIDList())
        delta = speed * 0.1
        cumulative = metrics[-1]["ambulance_distance_covered"] + delta
        metrics.append({
            "simulation_time": sim_time,
            "ambulance_edge": current_edge,
            "ambulance_speed": speed,
            "ambulance_distance_covered": cumulative,
            "num_vehicles": num_vehicles
        })

        if sim_time - last_replan_time >= REPLAN_INTERVAL:
            new_route = planner.replan(current_edge, DEST_EDGE)
            if new_route:
                traci.vehicle.setRoute(AMBULANCE_ID, new_route)
                print(f"🔄 Replanned route at t={sim_time}: {new_route}")
            last_replan_time = sim_time

        if current_edge == DEST_EDGE:
            reaching_time = sim_time
            print(f"🎯 Destination reached at {reaching_time}")
            break

        preempt_traffic_signals(route, preempted_signals)
        traci.simulationStep(); time.sleep(0.1)

    traci.close()

    if reaching_time:
        display_summary(metrics, resume_time, reaching_time)
    else:
        print("⚠️ Destination not reached.")

    save_metrics_csv(metrics, ALGORITHM_FOLDER, resume_time)
    save_metric_graphs(metrics, ALGORITHM_FOLDER, resume_time)

if __name__ == "__main__":
    main()
