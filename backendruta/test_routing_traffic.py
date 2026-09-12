import pickle
from pathlib import Path
import osmnx as ox
import networkx as nx

BASE_DIR = Path(__file__).resolve().parent.parent
G = pickle.loads((BASE_DIR / "data" / "mty_graph.pkl").read_bytes())

o_node = ox.nearest_nodes(G, -100.2895, 25.6515) # Tec
d_node = ox.nearest_nodes(G, -100.3090, 25.6714) # Centro

# 1. Ruta normal
p_normal = nx.shortest_path(G, o_node, d_node, weight="travel_time")

# 2. Función de peso para MultiDiGraph que penaliza Garza Sada
def dynamic_weight(u, v, edges_dict):
    best_w = float("inf")
    for key, edge_data in edges_dict.items():
        base_tt = edge_data.get("travel_time", 1.0)
        name = str(edge_data.get("name", "")).lower()
        mult = 1000.0 if "garza sada" in name else 1.0
        w = base_tt * mult
        if w < best_w:
            best_w = w
    return best_w

p_avoid = nx.shortest_path(G, o_node, d_node, weight=dynamic_weight)

print(f"Normal path nodes: {len(p_normal)}")
print(f"Avoid path nodes:  {len(p_avoid)}")
print(f"Rutas distintas:   {p_normal != p_avoid}")

names_normal = [G.get_edge_data(u, v)[0].get("name") for u, v in zip(p_normal[:-1], p_normal[1:]) if G.get_edge_data(u, v)]
names_avoid = [G.get_edge_data(u, v)[0].get("name") for u, v in zip(p_avoid[:-1], p_avoid[1:]) if G.get_edge_data(u, v)]

garza_in_normal = any("Garza Sada" in str(n) for n in names_normal)
garza_in_avoid = any("Garza Sada" in str(n) for n in names_avoid)

print(f"Garza Sada en ruta normal: {garza_in_normal}")
print(f"Garza Sada en ruta evadida: {garza_in_avoid}")
