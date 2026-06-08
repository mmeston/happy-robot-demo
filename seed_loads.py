from api.database import init_db, seed_demo_loads


init_db()
count = seed_demo_loads()

print(f"Inserted {count} loads.")
