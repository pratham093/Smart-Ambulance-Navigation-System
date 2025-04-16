import traci
import time
import math
import networkx as nx
import random

# ----- Configuration -----
SUMO_CONFIG_FILE = "osm.sumocfg"
AMBULANCE_ID = "ambulance_trip"
WAIT_TIME = 100
PREEMPTION_GREEN_STATE = "G"
SOURCE_EDGE = "-1285481595"
DEST_EDGE = "-73030702#1"
# --------------------------

def get_lane_ids(edge):
    try:
        num = traci.edge.getLaneNumber(edge)
        return [f"{edge}_{i}" for i in range(num)]
    except Exception as e:
        print(f"Error getting lane ids for edge {edge}: {e}")
        return []

def build_network_graph():
    G = nx.DiGraph()
    all_edges = traci.edge.getIDList()
    for edge in all_edges:
        if edge.startswith(":"):
            continue
        G.add_node(edge)
        lane_ids = get_lane_ids(edge)
        for lane_id in lane_ids:
            try:
                links = traci.lane.getLinks(lane_id)
            except Exception as e:
                print(f"Error getting links for lane {lane_id}: {e}")
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
        print(f"Error computing center for edge {edge_id}: {e}")
        return (0.0, 0.0)

def compute_route_astar(graph, source, destination):
    def heuristic(u, v):
        ux, uy = edge_center(u)
        vx, vy = edge_center(v)
        return math.hypot(ux - vx, uy - vy)
    try:
        route = nx.astar_path(graph, source, destination, heuristic=heuristic, weight='weight')
        cost = nx.astar_path_length(graph, source, destination, heuristic=heuristic, weight='weight')
        return route, cost
    except Exception as e:
        print("A* route error:", e)
        return None, float("inf")

def compute_route_bco(graph, source, destination, iterations=50, bees=10):
    best_route = None
    best_cost = float("inf")
    for _ in range(iterations):
        candidate_route = [source]
        current = source
        while current != destination:
            neighbors = list(graph.successors(current))
            if not neighbors:
                break
            current = random.choice(neighbors)
            candidate_route.append(current)
        cost = sum(graph[u][v]['weight'] for u, v in zip(candidate_route, candidate_route[1:]))
        if cost < best_cost:
            best_cost = cost
            best_route = candidate_route
    return best_route, best_cost

def hybrid_a_star_bco(graph, source, destination):
    astar_route, astar_cost = compute_route_astar(graph, source, destination)
    bco_route, bco_cost = compute_route_bco(graph, source, destination)
    
    if astar_cost < bco_cost:
        return astar_route, astar_cost
    else:
        return bco_route, bco_cost

def preempt_traffic_signals(route):
    tls_ids = traci.trafficlight.getIDList()
    for tls in tls_ids:
        try:
            current_state = traci.trafficlight.getRedYellowGreenState(tls)
            green_state = PREEMPTION_GREEN_STATE * len(current_state)
            controlled_lanes = traci.trafficlight.getControlledLanes(tls)
            for lane in controlled_lanes:
                edge_id = traci.lane.getEdgeID(lane)
                if edge_id in route:
                    traci.trafficlight.setRedYellowGreenState(tls, green_state)
                    break
        except Exception as e:
            print(f"Error updating signal {tls}: {e}")

def main():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG_FILE])
    
    for _ in range(5):
        traci.simulationStep()
        time.sleep(0.1)
    
    while AMBULANCE_ID not in traci.vehicle.getIDList():
        traci.simulationStep()
        time.sleep(0.1)
    
    current_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
    
    traci.vehicle.setStop(AMBULANCE_ID, current_edge, duration=WAIT_TIME)
    time.sleep(WAIT_TIME * 0.1)
    
    graph = build_network_graph()
    
    route, cost = hybrid_a_star_bco(graph, current_edge, DEST_EDGE)
    
    if not route:
        print("Failed to compute a valid route.")
        return
    
    traci.vehicle.setRoute(AMBULANCE_ID, route)
    traci.vehicle.resume(AMBULANCE_ID)
    
    while traci.simulation.getMinExpectedNumber() > 0:
        preempt_traffic_signals(route)
        traci.simulationStep()
        time.sleep(0.1)
    
    print(f"A*-BCO Hybrid Route: {route}")
    print(f"A*-BCO Hybrid Cost: {cost}")
    
    traci.close()

if name == "main":
    main()
@Pratham Shah Dj 

try