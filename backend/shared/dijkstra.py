from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from models import TradePartnership, StockLevel
import heapq

def find_best_restock_route(db: Session, start_entity_id: str, start_entity_type: str, medicine_name: str, required_qty: int) -> Optional[List[str]]:
    """
    Finds the shortest path (in latency_days) from start_entity to an entity that has
    at least required_qty of medicine_name.
    Returns a list of entity_ids representing the path, or None if no path found.
    e.g. ['consumer_id', 'supplier_id', 'manufacturer_id']
    """
    # Dijkstra's algorithm
    # Graph: directed edges from receiver to supplier (we are looking backwards up the supply chain)
    # TradePartnership edges are from_entity (supplier) -> to_entity (receiver).
    # So we traverse edges where `to_entity_id == current_node`.
    
    # Priority queue: (total_latency, current_node, path)
    pq = [(0, start_entity_id, [start_entity_id])]
    
    visited = set()
    
    while pq:
        total_latency, current_node, path = heapq.heappop(pq)
        
        if current_node in visited:
            continue
        visited.add(current_node)
        
        # Check if current_node has the stock (don't check the start_entity itself)
        if current_node != start_entity_id:
            stock = db.query(StockLevel).filter(
                StockLevel.entity_id == current_node,
                StockLevel.medicine_name == medicine_name
            ).first()
            
            # Manufacturers are assumed to have infinite stock for emergency purposes if we reach them,
            # but let's check stock anyway. Actually, manufacturers might not maintain 'StockLevel' explicitly
            # in the same way, but let's assume they do, or if they are a manufacturer, we just return them.
            # Let's see if it's a manufacturer:
            node_type = None
            if len(path) > 1:
                # Get the edge that led here to know its type
                edge = db.query(TradePartnership).filter_by(from_entity_id=current_node, to_entity_id=path[-2]).first()
                if edge:
                    node_type = edge.from_entity_type
            
            if node_type == 'manufacturer':
                # Reached a manufacturer, they can produce it
                return path
            elif stock and stock.quantity >= required_qty:
                # Supplier has enough stock
                return path
        
        # Traverse neighbors (up the supply chain)
        edges = db.query(TradePartnership).filter_by(to_entity_id=current_node, status="active").all()
        for edge in edges:
            neighbor = edge.from_entity_id
            if neighbor not in visited:
                heapq.heappush(pq, (total_latency + edge.latency_days, neighbor, path + [neighbor]))
                
    return None
