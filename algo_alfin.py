import traci
import time
import math
import networkx as nx
import random
import pandas as pd
import matplotlib.pyplot as plt

# Enable interactive plotting
plt.ion()

# ----- Configuration -----
SUMO_CONFIG_FILE       = "osm.sumocfg"
AMBULANCE_ID           = "ambulance_trip"  # Single ambulance for this example
WAIT_TIME              = 100
PREEMPTION_GREEN_STATE = "G"
DEST_EDGE              = "-181613191#0"
RECALCULATE_INTERVAL   = 10  # seconds
ALPHA                  = 0.5  # weight factor for congestion metric
# --------------------------

def get_lane_ids(edge):
    try:
        num = traci.edge.getLaneNumber(edge)
        return [f"{edge}_{i}" for i in range(num)]
    except Exception as e:
        print(f"[❌] Getting lane IDs for {edge}: {e}")
        return []


def build_network_graph():
    G = nx.DiGraph()
    for edge in traci.edge.getIDList():
        if edge.startswith(":"):
            continue
        G.add_node(edge)
        for lane in get_lane_ids(edge):
            try:
                links = traci.lane.getLinks(lane)
            except Exception as e:
                print(f"[⚠] Getting links for lane {lane}: {e}")
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


def edge_center(e):
    try:
        lanes = get_lane_ids(e)
        if not lanes:
            return (0.0, 0.0)
        shp = traci.lane.getShape(lanes[0])
        x = (shp[0][0] + shp[-1][0]) / 2.0
        y = (shp[0][1] + shp[-1][1]) / 2.0
        return (x, y)
    except Exception as e:
        print(f"[❌] Computing center for {e}: {e}")
        return (0.0, 0.0)


def find_nearest_reachable_edge(G, src):
    src_x, src_y = edge_center(src)
    best, bd = src, float("inf")
    for e in G.nodes():
        if nx.has_path(G, src, e):
            ex, ey = edge_center(e)
            d = math.hypot(src_x - ex, src_y - ey)
            if d < bd:
                best, bd = e, d
    return best


def heuristic(u, v):
    ux, uy = edge_center(u)
    vx, vy = edge_center(v)
    return math.hypot(ux - vx, uy - vy)

# --------------------------
# Routing Algorithms
# --------------------------
def compute_route_dijkstra(G, src, dst):
    try:
        path = nx.dijkstra_path(G, src, dst, weight='weight')
        cost = nx.dijkstra_path_length(G, src, dst, weight='weight')
        print(f"🚀 Dijkstra: cost = {cost:.2f} | edges = {len(path)}")
        return path, cost
    except Exception as e:
        print(f"[❌] Dijkstra error: {e}")
        return [], float("inf")


def compute_route_astar(G, src, dst):
    try:
        path = nx.astar_path(G, src, dst, heuristic=heuristic, weight='weight')
        cost = nx.astar_path_length(G, src, dst, heuristic=heuristic, weight='weight')
        print(f"🚀 A*: cost = {cost:.2f} | edges = {len(path)}")
        return path, cost
    except Exception as e:
        print(f"[❌] A* error: {e}")
        return [], float("inf")


def compute_route_bellman_hedkamp(G, src, dst):
    try:
        path = nx.bellman_ford_path(G, src, dst, weight='weight')
        cost = nx.bellman_ford_path_length(G, src, dst, weight='weight')
        print(f"🔁 Bellman-Hedkamp: cost = {cost:.2f} | edges = {len(path)}")
        return path, cost
    except Exception as e:
        print(f"[❌] Bellman-Hedkamp error: {e}")
        return [], float("inf")


def compute_route_astar_bco(G, src, dst, n_bees=5):
    print("🚀 A*+BCO hybrid")
    base_path, base_cost = compute_route_astar(G, src, dst)
    best_path, best_cost = base_path, base_cost
    def noisy_weight(u, v, d):
        return d['weight'] * random.uniform(0.9, 1.1)
    for _ in range(n_bees):
        try:
            p = nx.astar_path(G, src, dst, heuristic=heuristic, weight=lambda u,v,d: noisy_weight(u,v,d))
            c = nx.astar_path_length(G, src, dst, heuristic=heuristic, weight=lambda u,v,d: noisy_weight(u,v,d))
            if c < best_cost:
                best_path, best_cost = p, c
        except Exception:
            continue
    print(f"🚀 A*+BCO: cost = {best_cost:.2f} | edges = {len(best_path)}")
    return best_path, best_cost


def compute_all_routes(G, src, dst):
    routes = {}
    for name, func in [
        ("Dijkstra", compute_route_dijkstra),
        ("A*", compute_route_astar),
        ("BHK", compute_route_bellman_hedkamp),
        ("A* BCO", compute_route_astar_bco)
    ]:
        path, cost = func(G, src, dst)
        if path and len(path) > 1:
            routes[name] = (path, cost)
    return routes

# --------------------------
# Congestion Metric
# --------------------------
def compute_route_congestion(route):
    total_congestion = 0
    for edge in route:
        try:
            num_vehicles = traci.edge.getLastStepVehicleNumber(edge)
            total_congestion += num_vehicles
        except Exception as e:
            print(f"[⚠] Could not get vehicle count for edge {edge}: {e}")
    return total_congestion

# --------------------------
# Traffic Signal Preemption
# --------------------------
def preempt_traffic_signals(route, preempted_signals):
    for tls in traci.trafficlight.getIDList():
        try:
            state = traci.trafficlight.getRedYellowGreenState(tls)
            green_state = PREEMPTION_GREEN_STATE * len(state)
            for ln in traci.trafficlight.getControlledLanes(tls):
                if traci.lane.getEdgeID(ln) in route and tls not in preempted_signals:
                    traci.trafficlight.setRedYellowGreenState(tls, green_state)
                    preempted_signals.add(tls)
                    print(f"[🚦] {tls} set to green")
                    break
        except Exception as e:
            print(f"[⚠] Signal error for {tls}: {e}")

# --------------------------
# Metrics & Plotting
# --------------------------
def compute_total_distance(route):
    total = 0.0
    for e in route:
        try:
            total += traci.edge.getLength(e)
        except Exception:
            continue
    return total


def plot_speed_graph(log, amb_id):
    plt.figure()
    plt.plot(log["time"], log["speed"], marker="o")
    plt.xlabel("Time (s)")
    plt.ylabel("Speed (m/s)")
    plt.title(f"Speed vs Time for {amb_id}")
    plt.grid(True)
    plt.savefig(f"{amb_id}_speed.png")
    plt.show()

# --------------------------
# Main Simulation Routine
# --------------------------
def run_simulation():
    sim_start_time = time.time()
    print("Simulation Starting ")
    traci.start(["sumo-gui", "-c", SUMO_CONFIG_FILE])
    # Warm-up
    for _ in range(5):
        traci.simulationStep()
        time.sleep(0.1)

    G = build_network_graph()
    print(f"\n[Graph] {len(G.nodes())} nodes | {len(G.edges())} edges")

    # Wait for ambulance spawn
    while AMBULANCE_ID not in traci.vehicle.getIDList():
        traci.simulationStep()
        time.sleep(0.1)
    spawn_time = traci.simulation.getTime()
    print(f"\n🚑 {AMBULANCE_ID} spawned at {spawn_time:.1f}s")

    # Stop ambulance to simulate waiting before routing
    ln = traci.vehicle.getLaneID(AMBULANCE_ID)
    src = traci.lane.getEdgeID(ln)
    pos = traci.vehicle.getLanePosition(AMBULANCE_ID)
    traci.vehicle.setStop(AMBULANCE_ID, src, pos=pos, duration=WAIT_TIME)
    print(f"[⏸] {AMBULANCE_ID} stopped at {src} (pos {pos:.2f}) for {WAIT_TIME}s")
    stop_time = traci.simulation.getTime()
    while traci.simulation.getTime() - stop_time < WAIT_TIME:
        traci.simulationStep()
        time.sleep(0.1)

    # Initial Routing
    dst = DEST_EDGE
    if not nx.has_path(G, src, dst):
        dst = find_nearest_reachable_edge(G, src)
        print(f"[⚠] No path to destination. New destination: {dst}")
    routes = compute_all_routes(G, src, dst)
    if not routes:
        print("[⚠] All algorithms failed. Using default route.")
        route = traci.vehicle.getRoute(AMBULANCE_ID)
        best_algo = "Default"
        best_cost = float("inf")
        current_combined = float("inf")
    else:
        best_algo = min(routes, key=lambda k: routes[k][1])
        route, best_cost = routes[best_algo]
        congestion = compute_route_congestion(route)
        current_combined = best_cost + ALPHA * congestion
        print(f"[✅] {best_algo} selected | cost: {best_cost:.2f} | "
              f"congestion: {congestion} | combined: {current_combined:.2f}")

    traci.vehicle.setRoute(AMBULANCE_ID, route)
    traci.vehicle.resume(AMBULANCE_ID)
    resume_time = traci.simulation.getTime()
    print(f"[▶] {AMBULANCE_ID} resumed at {resume_time:.1f}s")

    # Dynamic re-routing & Logging
    speed_log = {"time": [], "speed": []}
    preempted = set()
    last_recalc = resume_time

    while AMBULANCE_ID in traci.vehicle.getIDList():
        now = traci.simulation.getTime()
        current_speed = traci.vehicle.getSpeed(AMBULANCE_ID)
        speed_log["time"].append(now - resume_time)
        speed_log["speed"].append(current_speed)

        # Recalculate routes at intervals
        if now - last_recalc >= RECALCULATE_INTERVAL:
            cur_edge = traci.lane.getEdgeID(traci.vehicle.getLaneID(AMBULANCE_ID))
            if not cur_edge.startswith(":") and cur_edge in G:
                print(f"\n[🔄] t={now:.1f}s | Edge: {cur_edge} | Speed: {current_speed:.2f} m/s")
                try:
                    new_routes = compute_all_routes(G, cur_edge, dst)
                    if new_routes:
                        print("[🔄] Candidate routes:")
                        for name, (p, c) in new_routes.items():
                            print(f"    • {name}: cost = {c:.2f} | edges = {len(p)}")
                        metrics = {}
                        for name, (p, c) in new_routes.items():
                            cong = compute_route_congestion(p)
                            combined = c + ALPHA * cong
                            metrics[name] = (p, c, cong, combined)
                            print(f"    → {name} combined: {combined:.2f} "
                                  f"(cost {c:.2f} + α·cong {cong})")
                        candidate_algo, (candidate_route, candidate_cost,
                                         candidate_congestion,
                                         candidate_combined) = min(
                            metrics.items(), key=lambda item: item[1][3]
                        )
                        print(f"[🔄] Selected {candidate_algo} | cost: {candidate_cost:.2f} | "
                              f"congestion: {candidate_congestion} | combined: {candidate_combined:.2f}")
                        if (candidate_combined < current_combined * 0.9) or (current_speed < 2.0):
                            print(f"[🔄] Re-routing via {candidate_algo} "
                                  f"(new combined: {candidate_combined:.2f})")
                            traci.vehicle.setRoute(AMBULANCE_ID, candidate_route)
                            route = candidate_route
                            best_cost = candidate_cost
                            current_combined = candidate_combined
                except Exception as e:
                    print(f"[⚠] Re-routing error: {e}")
            last_recalc = now

        preempt_traffic_signals(route, preempted)
        traci.simulationStep()
        time.sleep(0.1)

    tend = traci.simulation.getTime()
    travel_time = tend - resume_time
    distance = compute_total_distance(route)
    avg_speed = distance / travel_time if travel_time > 0 else 0.0

    print("\n🏁 [Arrival Metrics]")
    print(f"Ambulance: {AMBULANCE_ID}")
    print(f"Spawn Time: {spawn_time:.1f}s")
    print(f"Resume Time: {resume_time:.1f}s")
    print(f"Arrival Time: {tend:.1f}s")
    print(f"Travel Time: {travel_time:.1f}s")
    print(f"Signals Preempted: {len(preempted)}")
    print("-------------------------------")

    plot_speed_graph(speed_log, AMBULANCE_ID)

    traci.close()
    sim_end_time = time.time()
    total_sim_time = sim_end_time - sim_start_time
    print(f"\n⏱ Simulation Start: {sim_start_time:.1f}s")
    print(f"⏱ Simulation End:   {sim_end_time:.1f}s")
    print(f"⏱ Total Simulation Time: {total_sim_time:.1f}s")
    print("Simulation Finished ")

if __name__ == "__main__":
    run_simulation()