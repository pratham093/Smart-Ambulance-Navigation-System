import traci
import sys
import heapq
import xml.etree.ElementTree as ET

# Set up paths
sys.path.append("E:\\Program Files (x86)\\Eclipse\\Sumo\\tools")
sumoBinary = r"E:\Program Files (x86)\Eclipse\Sumo\bin\sumo-gui.exe"
sumoCmd = [sumoBinary, "-c", r"E:\Program Files (x86)\Eclipse\Sumo\tools\2024-11-03-19-03-47\env\trial1.sumocfg"]

# Connect to SUMO
print("Starting SUMO...")
traci.start(sumoCmd)
print("Connected to SUMO.")

# Define starting position in X and Y coordinates (within the SUMO network)
starting_x = 841.83 
starting_y = 1385.69

#1362.57,1454.83

# Get user input for the destination position in X and Y coordinates
print("Please enter the destination coordinates in X and Y (within the SUMO network):")
destination_x = float(input("Enter the destination X coordinate: "))
destination_y = float(input("Enter the destination Y coordinate: "))
print(f"Destination set to: {destination_x}, {destination_y}")

# Function to load lane lengths from the .net.xml file
def load_lane_lengths_from_network(net_file):
    lane_lengths = {}
    try:
        tree = ET.parse(net_file)
        root = tree.getroot()
        for edge in root.findall('.//edge'):
            edge_id = edge.get('id')
            total_length = 0.0
            for lane in edge.findall('lane'):
                length = float(lane.get('length', 0))
                total_length += length
            lane_lengths[edge_id] = total_length
    except Exception as e:
        print(f"Error loading lane lengths: {e}")
    return lane_lengths

# Path to .net.xml file
net_file = r"E:\Program Files (x86)\Eclipse\Sumo\tools\2024-11-03-19-03-47\env\osm.net.xml\osm.net.xml"
print("Loading lane lengths...")
lane_lengths = load_lane_lengths_from_network(net_file)
if not lane_lengths:
    print("No lane lengths found. Using default values.")
    lane_lengths = {edge: 50.0 for edge in traci.edge.getIDList()}
print(f"Loaded {len(lane_lengths)} edges with lane lengths.")

# Function to find the nearest edge using SUMO
def get_nearest_edge(x, y):
    try:
        edge_ids = traci.simulation.convertRoad(x, y)
        if edge_ids:
            return edge_ids[0]
    except Exception as e:
        print(f"Error finding nearest edge: {e}")
    return None

# Find nearest edges
print("Finding the nearest edges for start and destination...")
starting_edge = get_nearest_edge(starting_x, starting_y)
destination_edge = get_nearest_edge(destination_x, destination_y)
if not starting_edge or not destination_edge:
    print("Could not determine starting or destination edge. Exiting.")
    traci.close()
    sys.exit(1)
print(f"Starting edge: {starting_edge}, Destination edge: {destination_edge}")

# Function to parse the .net.xml file and get the connections
def get_edge_connections(net_file):
    edge_connections = {}
    try:
        tree = ET.parse(net_file)
        root = tree.getroot()
        for edge in root.findall('.//edge'):
            edge_id = edge.get('id')
            from_node = edge.get('from')
            to_node = edge.get('to')
            if from_node not in edge_connections:
                edge_connections[from_node] = []
            if to_node not in edge_connections:
                edge_connections[to_node] = []
            edge_connections[from_node].append(edge_id)
            edge_connections[to_node].append(edge_id)
    except Exception as e:
        print(f"Error loading edge connections: {e}")
    return edge_connections

# Load edge connections from the network
edge_connections = get_edge_connections(net_file)

# Function to find neighbors of an edge (connected edges)
def get_neighbors(edge):
    neighbors = []
    # Extract 'from' and 'to' nodes
    from_node = None
    to_node = None

    tree = ET.parse(net_file)
    root = tree.getroot()
    for e in root.findall('.//edge'):
        if e.get('id') == edge:
            from_node = e.get('from')
            to_node = e.get('to')
            break

    # Find the connected edges by checking the nodes
    if from_node and to_node:
        neighbors = edge_connections.get(from_node, []) + edge_connections.get(to_node, [])
        # Remove the current edge from the neighbors list
        neighbors = [neighbor for neighbor in neighbors if neighbor != edge]
    
    return neighbors

# Heuristic function for A* (Euclidean distance)
def heuristic(edge, destination_edge, net_file):
    try:
        tree = ET.parse(net_file)
        root = tree.getroot()
        edge_positions = {}

        # Extract positions of all edges
        for e in root.findall('.//edge'):
            edge_id = e.get('id')
            lanes = e.findall('lane')
            if lanes:
                mid_x, mid_y = 0.0, 0.0
                for lane in lanes:
                    shape = lane.get('shape')
                    if shape:
                        points = shape.split(" ")
                        mid_idx = len(points) // 2
                        mid_x, mid_y = map(float, points[mid_idx].split(","))
                edge_positions[edge_id] = (mid_x, mid_y)

        # Get positions of current edge and destination edge
        current_pos = edge_positions.get(edge)
        destination_pos = edge_positions.get(destination_edge)

        if current_pos and destination_pos:
            dx = destination_pos[0] - current_pos[0]
            dy = destination_pos[1] - current_pos[1]
            return (dx**2 + dy**2)**0.5  # Euclidean distance

    except Exception as e:
        print(f"Error in heuristic calculation: {e}")

    return float('inf')  # Default heuristic if positions are unavailable

# A* Algorithm
def a_star(edges, lane_lengths, start_edge, destination_edge, net_file):
    # Initialize costs and priority queue
    g_costs = {edge: float('inf') for edge in edges}  
    f_costs = {edge: float('inf') for edge in edges}  
    g_costs[start_edge] = 0
    f_costs[start_edge] = heuristic(start_edge, destination_edge, net_file)

    previous_edges = {edge: None for edge in edges}
    priority_queue = [(f_costs[start_edge], start_edge)]  

    while priority_queue:
        current_f_cost, current_edge = heapq.heappop(priority_queue)

        # Stop if we reach the destination
        if current_edge == destination_edge:
            break

        # Get neighbors (connected edges)
        for neighbor in get_neighbors(current_edge):
            tentative_g_cost = g_costs[current_edge] + lane_lengths.get(neighbor, 0)
            if tentative_g_cost < g_costs[neighbor]:
                g_costs[neighbor] = tentative_g_cost
                f_costs[neighbor] = tentative_g_cost + heuristic(neighbor, destination_edge, net_file)
                previous_edges[neighbor] = current_edge
                heapq.heappush(priority_queue, (f_costs[neighbor], neighbor))

    # Reconstruct the shortest path
    path = []
    current_edge = destination_edge
    while current_edge is not None:
        path.append(current_edge)
        current_edge = previous_edges[current_edge]
    return path[::-1], g_costs[destination_edge]

# Run A* algorithm
print("Running A* algorithm...")
best_route, best_distance = a_star(list(lane_lengths.keys()), lane_lengths, starting_edge, destination_edge, net_file)
if best_route and best_distance != float('inf'):
    print(f"Best route using A*: {best_route}")
    print(f"Best distance using A*: {best_distance:.2f} meters")

def write_trip_to_rou_file(rou_file_path, trip_id, vehicle_type, route):
    """
    Writes a trip to the .rou.xml file using the given route.
    
    :param rou_file_path: Path to the .rou.xml file.
    :param trip_id: ID for the new trip.
    :param vehicle_type: Type of the vehicle (e.g., "car").
    :param route: List of edge IDs representing the route.
    """
    try:
        # Parse the .rou.xml file
        tree = ET.parse(rou_file_path)
        root = tree.getroot()

        # Add the trip
        trip_element = ET.Element(
            'trip', 
            id=trip_id, 
            type=vehicle_type, 
            depart="0", 
            fromEdge=route[0], 
            toEdge=route[-1]
        )
        root.append(trip_element)

        # Write changes back to the file
        tree.write(rou_file_path, encoding="UTF-8", xml_declaration=True)
        print(f"Successfully added trip {trip_id} to route.")
    except Exception as e:
        print(f"Error writing trip to .rou.xml file: {e}")

# Path to your .rou.xml file
rou_file_path = r"E:\Program Files (x86)\Eclipse\Sumo\tools\2024-11-03-19-03-47\env\routes.rou.xml"

# Write the best route as a trip
if best_route and len(best_route) > 1:
    trip_id = "best_trip"
    vehicle_type = "car"  # Matches the defined vehicle type in your .rou.xml
    write_trip_to_rou_file(rou_file_path, trip_id, vehicle_type, best_route)
else:
    print("No valid route found; cannot write trip to .rou.xml.")

# Close SUMO connection after simulation
traci.close()
