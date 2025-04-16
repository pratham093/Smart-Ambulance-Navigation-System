import traci
import time
import math
import networkx as nx
import random

# ----- Configuration -----
SUMO_CONFIG_FILE = "osm.sumocfg"
AMBULANCE_ID = "ambulance_trip"
WAIT_TIME = 100
SOURCE_EDGE = "-1285481595"
DEST_EDGE = "-1180132072#1"
# --------------------------

def get_lane_ids(edge):
    try:
        num = traci.edge.getLaneNumber(edge)
        return [f"{edge}_{i}" for i in range(num)]
    except Exception as e:
        print(f"[ERROR] Getting lane IDs for edge {edge}: {e}")
        return []

def build_network_graph():
    G = nx.DiGraph()
    all_edges = traci.edge.getIDList()
    for edge in all_edges:
        if edge.startswith(":"):
            continue
        G.add_node(edge)
        for lane_id in get_lane_ids(edge):
            try:
                links = traci.lane.getLinks(lane_id)
            except Exception as e:
                print(f"[WARN] Getting links for lane {lane_id}: {e}")
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

def edge_center(edge_id):
    try:
        lane_ids = get_lane_ids(edge_id)
        if not lane_ids:
            return (0.0, 0.0)
        shape = traci.lane.getShape(lane_ids[0])
        x = (shape[0][0] + shape[-1][0]) / 2.0
        y = (shape[0][1] + shape[-1][1]) / 2.0
        return (x, y)
    except Exception as e:
        print(f"[ERROR] Computing center for edge {edge_id}: {e}")
        return (0.0, 0.0)

def find_nearest_reachable_edge(graph, source):
    source_pos = edge_center(source)
    min_distance = float("inf")
    nearest_edge = source
    for edge in graph.nodes():
        if nx.has_path(graph, source, edge):
            edge_pos = edge_center(edge)
            distance = math.hypot(source_pos[0] - edge_pos[0], source_pos[1] - edge_pos[1])
            if distance < min_distance:
                min_distance = distance
                nearest_edge = edge
    return nearest_edge

def heuristic(u, v):
    pos_u = edge_center(u)
    pos_v = edge_center(v)
    return math.hypot(pos_u[0] - pos_v[0], pos_u[1] - pos_v[1])

def compute_route_dijkstra(graph, source, destination):
    try:
        route = nx.dijkstra_path(graph, source, destination, weight='weight')
        cost = nx.dijkstra_path_length(graph, source, destination, weight='weight')
        print("\n▶ Using Dijkstra Algorithm...")
        print("✅ Dijkstra computed route:", route)
        print("🧮 Dijkstra computed cost:", cost)
        return route, cost
    except Exception as e:
        print("[ERROR] Dijkstra route error:", e)
        return None, float("inf")

def compute_route_astar(graph, source, destination):
    try:
        route = nx.astar_path(graph, source, destination, heuristic=heuristic, weight='weight')
        cost = nx.astar_path_length(graph, source, destination, heuristic=heuristic, weight='weight')
        print("\n▶ Using A* Algorithm...")
        print("✅ A* computed route:", route)
        print("🧮 A* computed cost:", cost)
        return route, cost
    except Exception as e:
        print("[ERROR] A* route error:", e)
        return None, float("inf")

def compute_route_dstar_lite(graph, source, destination):
    try:
        route = nx.astar_path(graph, source, destination, heuristic=heuristic, weight='weight')
        cost = nx.astar_path_length(graph, source, destination, heuristic=heuristic, weight='weight')
        print("\n▶ Using D* Lite Algorithm (placeholder)...")
        print("✅ D* Lite computed route:", route)
        print("🧮 D* Lite computed cost:", cost)
        return route, cost
    except Exception as e:
        print("[ERROR] D* Lite route error:", e)
        return None, float("inf")

def compute_route_astar_bco(graph, source, destination, n_bees=5):
    baseline_route, baseline_cost = compute_route_astar(graph, source, destination)
    best_route = baseline_route
    best_cost = baseline_cost

    def noisy_weight(u, v, d):
        return d['weight'] * random.uniform(0.9, 1.1)

    for _ in range(n_bees):
        try:
            route = nx.astar_path(graph, source, destination, heuristic=heuristic, weight=lambda u, v, d: noisy_weight(u, v, d))
            cost = nx.astar_path_length(graph, source, destination, heuristic=heuristic, weight=lambda u, v, d: noisy_weight(u, v, d))
            if cost < best_cost:
                best_cost = cost
                best_route = route
        except:
            continue

    print("\n▶ Using A* BCO Algorithm (hybrid A*+BCO)...")
    print("✅ A* BCO computed route:", best_route)
    print("🧮 A* BCO computed cost:", best_cost)
    return best_route, best_cost

def main():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG_FILE])
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
    print(f"⏸️ Ambulance stopping on {current_edge} at {current_pos:.2f} for {WAIT_TIME} seconds.")

    start_time = traci.simulation.getTime()
    while traci.simulation.getTime() - start_time < WAIT_TIME:
        traci.simulationStep()
        time.sleep(0.1)

    graph = build_network_graph()
    print(f"\n📡 Graph has {len(graph.nodes())} nodes and {len(graph.edges())} edges.")

    source = current_edge
    destination = DEST_EDGE

    if len(graph.edges()) == 0:
        print("[WARN] Graph has no edges. Using default vehicle route.")
        new_route = traci.vehicle.getRoute(AMBULANCE_ID)
    elif not nx.has_path(graph, source, destination):
        print("❌ Destination unreachable from source. Finding nearest reachable edge.")
        destination = find_nearest_reachable_edge(graph, source)
        print(f"✅ New destination: {destination}")

    if source == destination:
        print("⚠️ Source and destination are the same. No routing needed.")
        new_route = [source]
    else:
        routes = {}
        route_dij, cost_dij = compute_route_dijkstra(graph, source, destination)
        if route_dij and len(route_dij) > 1:
            routes["Dijkstra"] = (route_dij, cost_dij)
        route_astar, cost_astar = compute_route_astar(graph, source, destination)
        if route_astar and len(route_astar) > 1:
            routes["A*"] = (route_astar, cost_astar)
        route_dstar, cost_dstar = compute_route_dstar_lite(graph, source, destination)
        if route_dstar and len(route_dstar) > 1:
            routes["D* Lite"] = (route_dstar, cost_dstar)
        route_bco, cost_bco = compute_route_astar_bco(graph, source, destination)
        if route_bco and len(route_bco) > 1:
            routes["A* BCO"] = (route_bco, cost_bco)

        if not routes:
            print("⚠️ All algorithms failed. Using default vehicle route.")
            new_route = traci.vehicle.getRoute(AMBULANCE_ID)
        else:
            best_algo = min(routes, key=lambda k: routes[k][1])
            new_route, best_cost = routes[best_algo]
            print("\n==================== BEST ROUTE SELECTION ====================")
            print(f"✅ Selected {best_algo} with cost {best_cost}")
            print(f"🛣️ Route: {new_route}")

    traci.vehicle.setRoute(AMBULANCE_ID, new_route)
    print("✅ New route set:", new_route)

    traci.vehicle.resume(AMBULANCE_ID)
    print(f"🚑 Ambulance resumed at simulation time {traci.simulation.getTime()}.")

    start_move_time = traci.simulation.getTime()
    reached = False

    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        try:
            if traci.vehicle.getRoadID(AMBULANCE_ID) == DEST_EDGE:
                reached = True
                break
        except:
            break
        time.sleep(0.1)

    end_time = traci.simulation.getTime()

    if reached:
        print(f"✅ Ambulance reached destination edge {DEST_EDGE}.")
        print(f"⏱️ Time taken to reach: {end_time - start_move_time:.2f} seconds.")
    else:
        print("❌ Ambulance failed to reach the destination.")

    traci.close()

if __name__ == "__main__":
    main()
