import csv
import sys
import os

# Add the backend directory to sys.path so we can import from database and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import MedicineCatalog

csv_path = r'C:\Users\anish\Desktop\A_Z_medicines_dataset_of_India.csv'

def seed():
    db = SessionLocal()
    try:
        alkem_medicines = []
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('manufacturer_name', '').strip() == 'Alkem Laboratories Ltd':
                    sc1 = row.get('short_composition1', '').strip()
                    sc2 = row.get('short_composition2', '').strip()
                    
                    if sc2:
                        combined = f"{sc1} + {sc2}"
                    else:
                        combined = sc1
                        
                    pack_size = row.get('pack_size_label', '').strip()
                    alkem_medicines.append({
                        'medicine_name': combined,
                        'pack_size_label': pack_size
                    })
        
        print(f"Found {len(alkem_medicines)} Alkem medicines. Inserting into DB...")
        
        # Clear existing to avoid duplicates if re-run
        db.query(MedicineCatalog).delete()
        
        # Bulk insert
        objects = [
            MedicineCatalog(
                medicine_name=med['medicine_name'],
                pack_size_label=med['pack_size_label']
            )
            for med in alkem_medicines
        ]
        
        db.bulk_save_objects(objects)
        db.commit()
        print("Seeding completed successfully.")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    seed()
