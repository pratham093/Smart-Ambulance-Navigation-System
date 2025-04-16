import traci
import time
import math
import networkx as nx
import os
import matplotlib.pyplot as plt
import csv

# ----- Configuration -----
SUMO_CONFIG_FILE = "osm.sumocfg"
AMBULANCE_ID = "ambulance_trip"
WAIT_TIME = 100
PREEMPTION_GREEN_STATE = "G"
SOURCE_EDGE = "-1285481595"
DEST_EDGE = "-1180132072#1"
ALGORITHM_FOLDER = "Astar"
# --------------------------

def get_lane_ids(edge):
    try:
        num = traci.edge.getLaneNumber(edge)
        return [f"{edge}_{i}" for i in range(num)]
    except Exception:
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
                    length = traci.edge.getLength(edge)
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
                x, y = shape[0]  # Use first coordinate for simplicity
                coords[edge_id] = (x, y)
        except Exception:
            continue
    return coords

def euclidean_heuristic(u, v, coords):
    try:
        x1, y1 = coords.get(u, (0, 0))
        x2, y2 = coords.get(v, (0, 0))
        return math.hypot(x2 - x1, y2 - y1)
    except Exception:
        return 1.0

def compute_route_astar(graph, source, destination, coords):
    try:
        route = nx.astar_path(
            graph,
            source,
            destination,
            heuristic=lambda u, v: euclidean_heuristic(u, v, coords),
            weight='weight'
        )
        print("🔀 A* algorithm has been used.")
        print("🗺️  A* computed route:", route)
        return route
    except Exception as e:
        print("❌ A* route error:", e)
        return None

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
                        print(f"🚦 [SIGNAL] Signal {tls} on edge {edge_id} set to green.")
                        preempted_signals.add(tls)
                    break
        except Exception:
            pass

def save_metrics_csv(metrics, folder, resume_time):
    os.makedirs(folder, exist_ok=True)
    csv_file = os.path.join(folder, "metrics.csv")
    fieldnames = ["simulation_time", "ambulance_edge", "ambulance_speed",
                  "ambulance_distance_covered", "num_vehicles"]
    with open(csv_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for metric in metrics:
            if metric["simulation_time"] >= resume_time:
                writer.writerow(metric)
    print(f"📄 Metrics CSV saved to: {csv_file}")

def save_metric_graphs(metrics, folder, resume_time):
    os.makedirs(folder, exist_ok=True)
    filtered_metrics = [m for m in metrics if m["simulation_time"] >= resume_time]
    if not filtered_metrics:
        print("⚠️ No metrics to plot after dispatch.")
        return

    times = [m["simulation_time"] - resume_time for m in filtered_metrics]
    speeds = [m["ambulance_speed"] for m in filtered_metrics]
    distances = [m["ambulance_distance_covered"] for m in filtered_metrics]
    vehicles = [m["num_vehicles"] for m in filtered_metrics]

    plt.figure()
    plt.plot(times, speeds, label="Speed (m/s)", color='blue')
    plt.xlabel("Time After Dispatch (s)")
    plt.ylabel("Speed (m/s)")
    plt.title("Ambulance Speed vs Time")
    plt.legend()
    plt.savefig(os.path.join(folder, "speed_vs_time.png"))
    plt.close()

    plt.figure()
    plt.plot(times, distances, label="Distance Covered (m)", color='green')
    plt.xlabel("Time After Dispatch (s)")
    plt.ylabel("Distance (m)")
    plt.title("Ambulance Distance vs Time")
    plt.legend()
    plt.savefig(os.path.join(folder, "distance_vs_time.png"))
    plt.close()

    plt.figure()
    plt.plot(times, vehicles, label="Vehicles in Simulation", color='red')
    plt.xlabel("Time After Dispatch (s)")
    plt.ylabel("Number of Vehicles")
    plt.title("Vehicles vs Time")
    plt.legend()
    plt.savefig(os.path.join(folder, "vehicles_vs_time.png"))
    plt.close()

    print(f"📊 Graphs saved in folder: {folder}")
    print(f"   • 🚀 Speed vs Time")
    print(f"   • 📏 Distance vs Time")
    print(f"   • 🚗 Vehicles vs Time")

def display_summary(metrics, resume_time, reaching_time):
    filtered_metrics = [m for m in metrics if m["simulation_time"] >= resume_time]
    if not filtered_metrics:
        print("⚠️ No post-dispatch data available.")
        return

    speeds = [m["ambulance_speed"] for m in filtered_metrics]
    distances = [m["ambulance_distance_covered"] for m in filtered_metrics]
    vehicles = [m["num_vehicles"] for m in filtered_metrics]

    print("\n📈 Simulation Summary:")
    print(f"   ⏱️  Dispatch-to-Destination Time: {reaching_time - resume_time:.2f} seconds")
    print(f"   📏 Total Distance Covered: {distances[-1]:.2f} meters")
    print(f"   🚀 Average Speed: {sum(speeds)/len(speeds):.2f} m/s")
    print(f"   ⚡ Max Speed: {max(speeds):.2f} m/s")
    print(f"   🚗 Avg Vehicles in Simulation: {sum(vehicles)//len(vehicles)}")
    print("✅ Metrics and plots successfully generated.\n")

def main():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG_FILE])
    metrics = []

    for _ in range(5):
        traci.simulationStep()
        time.sleep(0.1)

    while AMBULANCE_ID not in traci.vehicle.getIDList():
        traci.simulationStep()
        time.sleep(0.1)
    print(f"🚑 Ambulance {AMBULANCE_ID} detected.")

    current_lane = traci.vehicle.getLaneID(AMBULANCE_ID)
    current_edge = traci.lane.getEdgeID(current_lane)
    current_pos = traci.vehicle.getLanePosition(AMBULANCE_ID)
    traci.vehicle.setStop(AMBULANCE_ID, current_edge, pos=current_pos, duration=WAIT_TIME)
    print(f"🛑 Ambulance stopping on {current_edge} at {current_pos:.2f} for {WAIT_TIME} seconds.")

    start_stop_time = traci.simulation.getTime()
    while traci.simulation.getTime() - start_stop_time < WAIT_TIME:
        sim_time = traci.simulation.getTime()
        try:
            lane = traci.vehicle.getLaneID(AMBULANCE_ID)
            edge = traci.lane.getEdgeID(lane)
            speed = traci.vehicle.getSpeed(AMBULANCE_ID)
        except Exception:
            edge, speed = "N/A", 0.0
        num_vehicles = len(traci.vehicle.getIDList())
        metric = {
            "simulation_time": sim_time,
            "ambulance_edge": edge,
            "ambulance_speed": speed,
            "ambulance_distance_covered": 0.0,
            "num_vehicles": num_vehicles
        }
        metrics.append(metric)
        traci.simulationStep()
        time.sleep(0.1)

    graph = build_network_graph()
    coords = get_edge_coords()

    if not nx.has_path(graph, current_edge, DEST_EDGE):
        print("❌ Destination unreachable. Exiting simulation.")
        traci.close()
        return

    new_route = compute_route_astar(graph, current_edge, DEST_EDGE, coords)
    if not new_route or len(new_route) < 2:
        new_route = traci.vehicle.getRoute(AMBULANCE_ID)
    else:
        traci.vehicle.setRoute(AMBULANCE_ID, new_route)
        print("📍 New route set:", new_route)

    resume_time = traci.simulation.getTime()
    traci.vehicle.resume(AMBULANCE_ID)
    print(f"🚑 Ambulance resumed at simulation time {resume_time}.")

    preempted_signals = set()
    reaching_time = None

    while traci.simulation.getMinExpectedNumber() > 0:
        preempt_traffic_signals(new_route, preempted_signals)
        traci.simulationStep()
        sim_time = traci.simulation.getTime()
        try:
            current_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
            speed = traci.vehicle.getSpeed(AMBULANCE_ID)
            pos = traci.vehicle.getLanePosition(AMBULANCE_ID)
        except Exception:
            break
        num_vehicles = len(traci.vehicle.getIDList())
        delta_distance = speed * 0.1
        cumulative_distance = metrics[-1]["ambulance_distance_covered"] + delta_distance if metrics else delta_distance

        metric = {
            "simulation_time": sim_time,
            "ambulance_edge": current_edge,
            "ambulance_speed": speed,
            "ambulance_distance_covered": cumulative_distance,
            "num_vehicles": num_vehicles
        }
        metrics.append(metric)

        if current_edge == DEST_EDGE:
            reaching_time = sim_time
            print(f"🎯 Destination edge {DEST_EDGE} reached at time {reaching_time - 105}")
            break

        time.sleep(0.1)

    traci.close()

    if reaching_time is not None:
        print(f"⏱️  Ambulance travel time (after dispatch): {reaching_time - 105:.2f} seconds")
    else:
        print("⚠️ Ambulance did not reach the destination.")

    save_metrics_csv(metrics, ALGORITHM_FOLDER, resume_time)
    save_metric_graphs(metrics, ALGORITHM_FOLDER, resume_time)
    if reaching_time:
        display_summary(metrics, resume_time, reaching_time)

if __name__ == "__main__":
    main()
