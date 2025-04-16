import traci
import time
import math
import networkx as nx
import os
import matplotlib.pyplot as plt
import csv

# ----- Configuration -----
SUMO_CONFIG_FILE       = "osm.sumocfg"
AMBULANCE_ID           = "ambulance_trip"
WAIT_TIME              = 100
PREEMPTION_GREEN_STATE = "G"
SOURCE_EDGE            = "-1285481595"
DEST_EDGE              = "-1180132072#1"
ALGORITHM_FOLDER       = "Dijkstra"
# --------------------------

def get_lane_ids(edge):
    try:
        num = traci.edge.getLaneNumber(edge)
        return [f"{edge}_{i}" for i in range(num)]
    except:
        return []

def get_congestion_edge(edge):
    try:
        return len(traci.edge.getLastStepVehicleIDs(edge))
    except:
        return 0

def build_network_graph():
    G = nx.DiGraph()
    for edge in traci.edge.getIDList():
        if edge.startswith(":"):
            continue
        for lane_id in get_lane_ids(edge):
            try:
                links = traci.lane.getLinks(lane_id)
            except:
                continue
            for link in links:
                tgt_lane = link[0]
                tgt_edge = traci.lane.getEdgeID(tgt_lane)
                if tgt_edge.startswith(":"):
                    continue
                try:
                    length = traci.edge.getLength(edge)
                except:
                    length = 1.0
                cong   = get_congestion_edge(edge)
                weight = length + 0.5 * cong
                G.add_edge(edge, tgt_edge, weight=weight)
    return G

def compute_route_dijkstra(graph, source, destination):
    try:
        return nx.dijkstra_path(graph, source, destination, weight='weight')
    except Exception as e:
        print("❌ Dijkstra route error:", e)
        return None

def get_congestion(route):
    congestion = 0
    for edge in route:
        try:
            congestion += len(traci.edge.getLastStepVehicleIDs(edge))
        except:
            continue
    return congestion

def compute_combined_cost(route, graph):
    if not route:
        return float("inf"), float("inf"), float("inf")
    cost = sum(graph[u][v]['weight'] for u, v in zip(route[:-1], route[1:]))
    congestion = get_congestion(route)
    combined = cost + 0.5 * congestion
    return cost, congestion, combined

def preempt_traffic_signals(route, preempted_signals):
    for tls in traci.trafficlight.getIDList():
        try:
            lanes = traci.trafficlight.getControlledLanes(tls)
        except:
            continue
        for lane in lanes:
            try:
                edge_id = traci.lane.getEdgeID(lane)
            except:
                continue
            if edge_id in route and tls not in preempted_signals:
                state = traci.trafficlight.getRedYellowGreenState(tls)
                green = PREEMPTION_GREEN_STATE * len(state)
                traci.trafficlight.setRedYellowGreenState(tls, green)
                print(f"🚦 [SIGNAL] {tls} on {edge_id} → GREEN")
                preempted_signals.add(tls)
                break

def save_metrics_csv(metrics, folder, resume_time):
    os.makedirs(folder, exist_ok=True)
    csv_file = os.path.join(folder, "metrics.csv")
    fieldnames = ["simulation_time", "ambulance_edge", "ambulance_speed",
                  "ambulance_distance_covered", "num_vehicles"]
    with open(csv_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics:
            if m["simulation_time"] >= resume_time:
                writer.writerow(m)
    print(f"📄 Metrics CSV saved to: {csv_file}")

def save_metric_graphs(metrics, folder, resume_time):
    os.makedirs(folder, exist_ok=True)
    filtered = [m for m in metrics if m["simulation_time"] >= resume_time]
    if not filtered:
        print("⚠️ No metrics to plot after dispatch.")
        return

    times     = [m["simulation_time"] - resume_time for m in filtered]
    speeds    = [m["ambulance_speed"] for m in filtered]
    distances = [m["ambulance_distance_covered"] for m in filtered]
    vehicles  = [m["num_vehicles"] for m in filtered]

    # Speed vs Time
    plt.figure()
    plt.plot(times, speeds, label="Speed (m/s)", color='blue')
    plt.xlabel("Time After Dispatch (s)")
    plt.ylabel("Speed (m/s)")
    plt.title("Ambulance Speed vs Time")
    plt.legend()
    plt.savefig(os.path.join(folder, "speed_vs_time.png"))
    plt.close()

    # Distance vs Time
    plt.figure()
    plt.plot(times, distances, label="Distance Covered (m)", color='green')
    plt.xlabel("Time After Dispatch (s)")
    plt.ylabel("Distance (m)")
    plt.title("Ambulance Distance vs Time")
    plt.legend()
    plt.savefig(os.path.join(folder, "distance_vs_time.png"))
    plt.close()

    # Vehicles vs Time
    plt.figure()
    plt.plot(times, vehicles, label="Vehicles in Simulation", color='red')
    plt.xlabel("Time After Dispatch (s)")
    plt.ylabel("Number of Vehicles")
    plt.title("Vehicles vs Time")
    plt.legend()
    plt.savefig(os.path.join(folder, "vehicles_vs_time.png"))
    plt.close()

    print(f"📊 Graphs saved in folder: {folder}")
    print("   • 🚀 Speed vs Time")
    print("   • 📏 Distance vs Time")
    print("   • 🚗 Vehicles vs Time")

def display_summary(metrics, resume_time, reaching_time):
    filtered = [m for m in metrics if m["simulation_time"] >= resume_time]
    if not filtered:
        print("⚠️ No post-dispatch data available.")
        return

    speeds    = [m["ambulance_speed"] for m in filtered]
    distances = [m["ambulance_distance_covered"] for m in filtered]
    vehicles  = [m["num_vehicles"] for m in filtered]

    print("\n📈 Simulation Summary:")
    print(f"   ⏱️  Dispatch-to-Destination Time: {reaching_time - resume_time:.2f} seconds")
    print(f"   📏 Total Distance Covered: {distances[-1]:.2f} meters")
    print(f"   🚀 Average Speed: {sum(speeds)/len(speeds):.2f} m/s")
    print(f"   ⚡ Max Speed: {max(speeds):.2f} m/s")
    print(f"   🚗 Avg Vehicles in Simulation: {sum(vehicles)//len(vehicles)}")
    print("✅ Metrics and plots successfully generated.\n")

def main():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG_FILE])

    # Warm‑up
    for _ in range(5):
        traci.simulationStep()
        time.sleep(0.1)

    # Wait for ambulance
    while AMBULANCE_ID not in traci.vehicle.getIDList():
        traci.simulationStep()
        time.sleep(0.1)
    print(f"🚑 Ambulance {AMBULANCE_ID} detected.")

    # Initial stop
    lane = traci.vehicle.getLaneID(AMBULANCE_ID)
    edge = traci.lane.getEdgeID(lane)
    pos  = traci.vehicle.getLanePosition(AMBULANCE_ID)
    traci.vehicle.setStop(AMBULANCE_ID, edge, pos=pos, duration=WAIT_TIME)

    # Collect metrics during wait
    metrics = []
    t0 = traci.simulation.getTime()
    while traci.simulation.getTime() - t0 < WAIT_TIME:
        now = traci.simulation.getTime()
        try:
            lane  = traci.vehicle.getLaneID(AMBULANCE_ID)
            edge  = traci.lane.getEdgeID(lane)
            speed = traci.vehicle.getSpeed(AMBULANCE_ID)
        except:
            edge, speed = "N/A", 0.0
        numv = len(traci.vehicle.getIDList())
        metrics.append({
            "simulation_time": now,
            "ambulance_edge": edge,
            "ambulance_speed": speed,
            "ambulance_distance_covered": 0.0,
            "num_vehicles": numv
        })
        traci.simulationStep()
        time.sleep(0.1)

    # Build graph & check path
    graph = build_network_graph()
    if edge not in graph or DEST_EDGE not in graph or not nx.has_path(graph, edge, DEST_EDGE):
        print("❌ Destination unreachable. Exiting.")
        traci.close()
        return

    # Initial route
    route = compute_route_dijkstra(graph, edge, DEST_EDGE)
    if route:
        traci.vehicle.setRoute(AMBULANCE_ID, route)
        print("📍 Initial Dijkstra route set.")

    # Resume
    resume_time = traci.simulation.getTime()
    traci.vehicle.resume(AMBULANCE_ID)
    print(f"🚑 Resumed at t={resume_time:.1f}s")

    preempted    = set()
    reaching_time = None
    last_reroute = resume_time

    # Main loop
    while traci.simulation.getMinExpectedNumber() > 0:
        now = traci.simulation.getTime()

        # Reroute every 10s
        if now - last_reroute >= 10:
            cur = traci.vehicle.getRoadID(AMBULANCE_ID)
            new_route = compute_route_dijkstra(graph, cur, DEST_EDGE)
            if new_route:
                cost, cong, comb = compute_combined_cost(new_route, graph)
                print(f"🔄 [Re‑routing @ {now:.1f}s] | cost: {cost:.2f} | congestion: {cong} | combined: {comb:.2f}")
                traci.vehicle.setRoute(AMBULANCE_ID, new_route)
                route = new_route
            else:
                print(f"⚠️ [Re‑routing @ {now:.1f}s] Dijkstra failed, skipping update")
            last_reroute = now

        preempt_traffic_signals(route, preempted)
        traci.simulationStep()

        try:
            edge  = traci.vehicle.getRoadID(AMBULANCE_ID)
            speed = traci.vehicle.getSpeed(AMBULANCE_ID)
            dist  = metrics[-1]["ambulance_distance_covered"] + speed * 0.1
        except:
            break
        numv = len(traci.vehicle.getIDList())
        metrics.append({
            "simulation_time": now,
            "ambulance_edge": edge,
            "ambulance_speed": speed,
            "ambulance_distance_covered": dist,
            "num_vehicles": numv
        })

        if edge == DEST_EDGE:
            reaching_time = now
            print(f"🎯 Reached destination at t={reaching_time - 105}s")
            break

        time.sleep(0.1)

    traci.close()

    if reaching_time:
        print(f"✅ Reached in {reaching_time-resume_time:.2f}s")
        save_metrics_csv(metrics, ALGORITHM_FOLDER, resume_time)
        save_metric_graphs(metrics, ALGORITHM_FOLDER, resume_time)
        display_summary(metrics, resume_time, reaching_time)
    else:
        print("⚠️ Destination not reached.")

if __name__ == "__main__":
    main()
