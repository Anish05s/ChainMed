from database import SessionLocal
from models import TradePartnership, Manufacturer, Supplier, Consumer

def seed():
    db = SessionLocal()
    try:
        manufacturers = db.query(Manufacturer).all()
        suppliers = db.query(Supplier).all()
        consumers = db.query(Consumer).all()

        count = 0
        
        # Connect all manufacturers to all suppliers
        for m in manufacturers:
            for s in suppliers:
                exists = db.query(TradePartnership).filter_by(from_entity_id=m.id, to_entity_id=s.id).first()
                if not exists:
                    tp = TradePartnership(
                        from_entity_id=m.id,
                        to_entity_id=s.id,
                        from_entity_type="manufacturer",
                        to_entity_type="supplier",
                        latency_days=1
                    )
                    db.add(tp)
                    count += 1
                    
        # Connect all suppliers to all consumers
        for s in suppliers:
            for c in consumers:
                exists = db.query(TradePartnership).filter_by(from_entity_id=s.id, to_entity_id=c.id).first()
                if not exists:
                    tp = TradePartnership(
                        from_entity_id=s.id,
                        to_entity_id=c.id,
                        from_entity_type="supplier",
                        to_entity_type="consumer",
                        latency_days=1
                    )
                    db.add(tp)
                    count += 1
                    
        db.commit()
        print(f"Seeded {count} TradePartnerships")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
