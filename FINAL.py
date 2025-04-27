import traci
import time
import math
import networkx as nx
import random
import itertools
import csv
import os

# ----- Configuration -----
SUMO_CONFIG_FILE = "osm.sumocfg"
AMBULANCE_ID = "ambulance_trip"
WAIT_TIME = 100
PREEMPTION_GREEN_STATE = "G"
SOURCE_EDGE = "-1285481595"
DEST_EDGE = "-181613191#0"
METRICS_CSV = "route_metrics.csv"
# --------------------------

def get_lane_ids(edge):
    try:
        num = traci.edge.getLaneNumber(edge)
        return [f"{edge}_{i}" for i in range(num)]
    except Exception as e:
        print(f"[ERROR] Getting lane IDs for edge {edge}: {e}")
        return []


def build_network_graph():
    """
    Build a directed graph with time-based weights: length_of_edge / max(mean_speed,0.1)
    """
    G = nx.DiGraph()
    for edge in traci.edge.getIDList():
        if edge.startswith(":"):
            continue
        lane_ids = get_lane_ids(edge)
        if lane_ids:
            try:
                length = traci.lane.getLength(lane_ids[0])
            except:
                length = 1.0
        else:
            length = 1.0
        try:
            speed = traci.edge.getLastStepMeanSpeed(edge)
        except:
            speed = 0.1
        speed = max(speed, 0.1)
        weight = length / speed
        G.add_node(edge)
        for lane in lane_ids:
            try:
                links = traci.lane.getLinks(lane)
            except Exception:
                continue
            for link in links:
                tgt = traci.lane.getEdgeID(link[0])
                if tgt.startswith(":"):
                    continue
                G.add_edge(edge, tgt, weight=weight)
    return G


def print_algo(name, route, cost):
    if route:
        print(f"🚀 {name}: cost = {cost:.2f} | edges = {len(route)}")
    else:
        print(f"🚀 {name}: failed")


def compute_route_dijkstra(graph, source, destination):
    try:
        r = nx.dijkstra_path(graph, source, destination, weight='weight')
        c = nx.dijkstra_path_length(graph, source, destination, weight='weight')
        print_algo("Dijkstra", r, c)
        return r, c
    except:
        print_algo("Dijkstra", None, 0)
        return None, float('inf')


def compute_route_astar(graph, source, destination):
    try:
        r = nx.astar_path(graph, source, destination, heuristic=lambda u,v:0, weight='weight')
        c = nx.astar_path_length(graph, source, destination, heuristic=lambda u,v:0, weight='weight')
        print_algo("A*", r, c)
        return r, c
    except:
        print_algo("A*", None, 0)
        return None, float('inf')


def compute_route_astar_bco(graph, source, destination, n_bees=5):
    print("🚀 A*+BCO hybrid")
    base_r, base_c = compute_route_astar(graph, source, destination)
    best_r, best_c = base_r, base_c
    def noisy(u,v,d): return d['weight'] * random.uniform(0.9, 1.1)
    for _ in range(n_bees):
        try:
            r = nx.astar_path(graph, source, destination, weight=noisy)
            c = nx.astar_path_length(graph, source, destination, weight=noisy)
            if c < best_c:
                best_r, best_c = r, c
        except:
            pass
    print(f"🚀 A*+BCO: cost = {best_c:.2f} | edges = {len(best_r) if best_r else 0}")
    return best_r, best_c


def bellman_held_karp_tsp(G, nodes):
    n = len(nodes)
    dist, dp, parent = {}, {}, {}
    for i,j in itertools.permutations(range(n),2):
        try: dist[(i,j)] = nx.shortest_path_length(G, nodes[i], nodes[j], weight='weight')
        except: dist[(i,j)] = float('inf')
    for k in range(1,n): dp[(1<<k,k)] = dist[(0,k)]; parent[(1<<k,k)] = 0
    for sz in range(2,n):
        for subset in itertools.combinations(range(1,n), sz):
            bits = sum(1<<s for s in subset)
            for k in subset:
                prev = bits & ~(1<<k)
                vals = [(dp[(prev,m)] + dist[(m,k)], m) for m in subset if m!=k]
                dp[(bits,k)], parent[(bits,k)] = min(vals)
    full = (1<<n)-1 - 1
    vals = [(dp[(full,k)] + dist[(k,0)], k) for k in range(1,n)]
    cost, last = min(vals)
    path, bits = [0], full
    for _ in range(n-1): path.append(last); bits, last = bits & ~(1<<last), parent[(bits,last)]
    path.reverse()
    return [nodes[i] for i in path], cost

def compute_route_bhk(graph, source, destination):
    r, c = bellman_held_karp_tsp(graph, [source, destination])
    print_algo("BHK", r, c)
    return r, c


def save_route_metrics(algo, cost, ttime, route):
    new = not os.path.exists(METRICS_CSV)
    with open(METRICS_CSV, 'a', newline='') as f:
        w = csv.writer(f)
        if new: w.writerow(["Algo", "Cost", "Time", "Route"])
        w.writerow([algo, f"{cost:.2f}", f"{ttime:.2f}", " -> ".join(route)])


def preempt_signals(route, preempted):
    for tls in traci.trafficlight.getIDList():
        for lane in traci.trafficlight.getControlledLanes(tls):
            if traci.lane.getEdgeID(lane) in route and tls not in preempted:
                st = PREEMPTION_GREEN_STATE * len(traci.trafficlight.getRedYellowGreenState(tls))
                traci.trafficlight.setRedYellowGreenState(tls, st)
                preempted.add(tls)
                break


def main():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG_FILE])
    # spawn
    for _ in range(5): traci.simulationStep(); time.sleep(0.1)
    while AMBULANCE_ID not in traci.vehicle.getIDList(): traci.simulationStep(); time.sleep(0.1)
    spawn_time = traci.simulation.getTime()
    print(f"[🔄] Spawn at t={spawn_time:.1f}s")

    # stop
    lane = traci.vehicle.getLaneID(AMBULANCE_ID)
    edge = traci.lane.getEdgeID(lane)
    pos = traci.vehicle.getLanePosition(AMBULANCE_ID)
    traci.vehicle.setStop(AMBULANCE_ID, edge, pos=pos, duration=WAIT_TIME)
    print(f"⏸️ Stopped on {edge}@{pos:.1f} for {WAIT_TIME}s.")
    t0 = traci.simulation.getTime()
    while traci.simulation.getTime() - t0 < WAIT_TIME:
        traci.simulationStep(); time.sleep(0.1)

    G = build_network_graph()
    print(f"📡 Graph: {len(G.nodes())} nodes, {len(G.edges())} edges.")

    src, dst = edge, DEST_EDGE
    if not G.edges():
        new_route, algo, cost = traci.vehicle.getRoute(AMBULANCE_ID), "Default", 0.0
    else:
        if not nx.has_path(G, src, dst):
            dst = min((e for e in G.nodes() if nx.has_path(G, src, e)),
                      key=lambda e: math.hypot(*([sum(x)/len(x) for x in zip(*[edge_center(src), edge_center(e)])])))
        # compute
        r_dij, c_dij = compute_route_dijkstra(G, src, dst)
        r_ast, c_ast = compute_route_astar(G, src, dst)
        r_bco, c_bco = compute_route_astar_bco(G, src, dst)
        r_bhk, c_bhk = compute_route_bhk(G, src, dst)
        # pick best
        candidates = [("Dijkstra", r_dij, c_dij), ("A*", r_ast, c_ast),
                      ("A* BCO", r_bco, c_bco), ("BHK", r_bhk, c_bhk)]
        valid = [(n, r, c) for n, r, c in candidates if r and len(r) > 1]
        algo, new_route, cost = min(valid, key=lambda x: x[2]) if valid else ("Default", traci.vehicle.getRoute(AMBULANCE_ID), 0.0)

    traci.vehicle.setRoute(AMBULANCE_ID, new_route)
    traci.vehicle.resume(AMBULANCE_ID)
    resume_t = traci.simulation.getTime()
    print(f"[🔄] Resume at t={resume_t:.1f}s")

    preempted, reach = set(), None
    while traci.simulation.getMinExpectedNumber() > 0:
        preempt_signals(new_route, preempted)
        traci.simulationStep()
        cur_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
        cur_lane = traci.vehicle.getLaneID(AMBULANCE_ID)
        lp = traci.vehicle.getLanePosition(AMBULANCE_ID)
        ll = traci.lane.getLength(cur_lane)
        if cur_edge == dst and lp >= ll - 0.1:
            reach = traci.simulation.getTime()
            print(f"[🔄] t={reach:.1f}s | Edge: {dst} | Speed: {traci.edge.getLastStepMeanSpeed(dst):.2f} m/s")
            print(f"🎯 Reached end of edge {dst} at t={reach:.1f}s")
            break
        time.sleep(0.1)

    travel = reach - resume_t if reach else 0.0
    print(f"⏱️ Travel time: {travel:.2f}s")
    save_route_metrics(algo, cost, travel, new_route)

    # arrival metrics
    print("\n🏁 [Arrival Metrics]")
    print(f"Ambulance: {AMBULANCE_ID}")
    print(f"Algorithm Used: {algo}")
    print(f"Spawn Time: {spawn_time:.1f}s")
    print(f"Resume Time: {resume_t:.1f}s")
    if reach: print(f"Arrival Time: {reach:.1f}s")
    print(f"Travel Time: {travel:.1f}s")

    print("🔚 Simulation ended.")
    traci.close()

if __name__ == "__main__":
    main()
