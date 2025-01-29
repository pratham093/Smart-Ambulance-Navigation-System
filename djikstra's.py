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

# Dijkstra's Algorithm (Modified for Final Output Only)
def dijkstra(edges, lane_lengths, start_edge, destination_edge):
    distances = {edge: float('inf') for edge in edges}
    distances[start_edge] = 0
    previous_edges = {edge: None for edge in edges}
    priority_queue = [(0, start_edge)]

    while priority_queue:
        current_distance, current_edge = heapq.heappop(priority_queue)

        if current_edge == destination_edge:
            break

        for neighbor in get_neighbors(current_edge):
            length = lane_lengths.get(neighbor, 0)
            distance = current_distance + length
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous_edges[neighbor] = current_edge
                heapq.heappush(priority_queue, (distance, neighbor))

    path = []
    current_edge = destination_edge
    while current_edge is not None:
        path.append(current_edge)
        current_edge = previous_edges[current_edge]
    return path[::-1], distances[destination_edge]

# Write the best route to a .rou.xml file
def write_route_to_xml(route, output_file):
    try:
        root = ET.Element("routes")
        route_element = ET.SubElement(root, "route", id="best_route", edges=" ".join(route))
        tree = ET.ElementTree(root)
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        print(f"Route written to {output_file}")
    except Exception as e:
        print(f"Error writing route to XML: {e}")

# Run Dijkstra's algorithm
print("Running Dijkstra's algorithm...")
best_route, best_distance = dijkstra(list(lane_lengths.keys()), lane_lengths, starting_edge, destination_edge)
if best_route and best_distance != float('inf'):
    print(f"Best route: {best_route}")
    print(f"Best distance: {best_distance:.2f} meters")

    # Write the route to .rou.xml file
    output_file = r"E:\Program Files (x86)\Eclipse\Sumo\tools\2024-11-03-19-03-47\env\route.rou.xml"
    write_route_to_xml(best_route, output_file)
else:
    print("No valid path found.")

# Close SUMO
traci.close()