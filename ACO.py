import traci
import sys
import random
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
starting_x = 857.35
starting_y = 1334.73

# Get user input for the destination position in X and Y coordinates
print("Please enter the destination coordinates in X and Y (within the SUMO network):")
destination_x = float(input("Enter the destination X coordinate: "))
destination_y = float(input("Enter the destination Y coordinate: "))
print(f"Destination set to: {destination_x}, {destination_y}")

# Function to load edge lengths from the .net.xml file
def load_edge_lengths_from_lanes(net_file):
    edge_lengths = {}
    try:
        tree = ET.parse(net_file)
        root = tree.getroot()
        for edge in root.findall('.//edge'):
            edge_id = edge.get('id')
            lane = edge.find('lane')
            if lane is not None:
                length = float(lane.get('length', 0))
                edge_lengths[edge_id] = length
    except Exception as e:
        print(f"Error loading edge lengths: {e}")
    return edge_lengths

# Path to .net.xml file
net_file = r"E:\Program Files (x86)\Eclipse\Sumo\tools\2024-11-03-19-03-47\env\osm.net.xml\osm.net.xml"
print("Loading edge lengths...")
edge_lengths = load_edge_lengths_from_lanes(net_file)
if not edge_lengths:
    print("No edge lengths found. Using default values.")
    edge_lengths = {edge: 50.0 for edge in traci.edge.getIDList()}
print(f"Loaded {len(edge_lengths)} edges with lengths.")

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

# Ant Colony Optimization Functions
def initialize_pheromones(edges, initial_value=1.0):
    return {edge: initial_value for edge in edges}

def calculate_probability(current_edge, visited, pheromones, edge_lengths, alpha=1.0, beta=2.0):
    probabilities = {}
    for edge, length in edge_lengths.items():
        if edge not in visited:
            pheromone = pheromones.get(edge, 1e-6)
            heuristic = 1 / max(length, 1e-6)  # Avoid division by zero
            probabilities[edge] = (pheromone ** alpha) * (heuristic ** beta)
    total = sum(probabilities.values())
    if total == 0:
        return {edge: 1 / len(edge_lengths) for edge in edge_lengths}  # Uniform probability
    return {edge: prob / total for edge, prob in probabilities.items()}

def ant_colony_optimization(edges, edge_lengths, starting_edge, destination_edge, num_ants=10, generations=5, evaporation_rate=0.5):
    pheromones = initialize_pheromones(edges)
    best_route = None
    best_distance = float('inf')

    for generation in range(generations):
        print(f"Generation {generation + 1}/{generations}...")
        all_routes = []
        all_distances = []

        for ant in range(num_ants):
            current_edge = starting_edge
            route = [current_edge]
            visited = set(route)
            total_distance = 0

            while current_edge != destination_edge:
                probabilities = calculate_probability(current_edge, visited, pheromones, edge_lengths)
                current_edge = random.choices(list(probabilities.keys()), weights=probabilities.values())[0]
                if current_edge in visited:
                    break  # Prevent infinite loops
                route.append(current_edge)
                visited.add(current_edge)
                total_distance += edge_lengths.get(current_edge, 0)

            all_routes.append(route)
            all_distances.append(total_distance)

            if total_distance < best_distance:
                best_route = route
                best_distance = total_distance

        # Update pheromones
        for route, distance in zip(all_routes, all_distances):
            for edge in route:
                pheromones[edge] += 1 / max(distance, 1e-6)  # Add pheromone inversely proportional to distance

        # Evaporate pheromones
        for edge in pheromones:
            pheromones[edge] *= (1 - evaporation_rate)

    return best_route, best_distance

# Run Ant Colony Optimization
print("Starting Ant Colony Optimization...")
best_route, best_distance = ant_colony_optimization(list(edge_lengths.keys()), edge_lengths, starting_edge, destination_edge)
print(f"Best route: {best_route}")
print(f"Best distance: {best_distance:.2f} meters")

# Highlight the chosen route
# def highlight_route(route):
#     for edge in route:
#         traci.edge.setEdgeColor(edge, (255, 0, 255))  # Bright pink
#     print("Route highlighted on SUMO.")

# highlight_route(best_route)

# Simulate the optimal route and calculate total travel time
def calculate_travel_time(route):
    vehicle_id = "test_vehicle"
    traci.vehicle.add(vehicle_id, route[0])  # Add vehicle at the first edge of the route
    traci.vehicle.setRoute(vehicle_id, route)  # Set the full route
    travel_time = 0

    while traci.vehicle.getRoadID(vehicle_id) != route[-1]:
        traci.simulationStep()  # Step the simulation
        travel_time += 1

    traci.vehicle.remove(vehicle_id)  # Remove the vehicle after simulation
    return travel_time

print("Calculating travel time for the optimal route...")
travel_time = calculate_travel_time(best_route)
print(f"Total travel time: {travel_time} seconds")

def calculate_total_time(route, edge_lengths, speed_kmh=50):  # Speed set to 50 km/h
    speed_mps = speed_kmh / 3.6  # Convert speed to meters per second
    total_time = 0
    for edge in route:
        length = edge_lengths.get(edge, 0)
        time = length / speed_mps if speed_mps > 0 else float('inf')
        total_time += time
    return total_time

# Calculate total time for the best route with fixed speed
total_time = calculate_total_time(best_route, edge_lengths, speed_kmh=50)
print(f"Total travel time: {total_time:.2f} seconds")

# Close SUMO
traci.close()


#Ant Colony Optimization:
# 1. Stigmergy: action by an oeganusn stimukates subsequent actions
# 2. Phermone: mark and commumicate the path of the shortest path (higher phermone higher the probability to pick that path)