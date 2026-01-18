"""
Migration Runner
Applies .cypher migration files to Neo4j database.
"""
import os
import glob
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from services.neo4j_service import get_neo4j_service


def run_migrations(migrations_dir: str = "migrations"):
    """Run all .cypher migration files in order."""
    neo4j = get_neo4j_service()
    
    if not neo4j.verify_connection():
        print("Cannot connect to Neo4j. Check your connection settings.")
        return False
    
    print("Connected to Neo4j")
    
    # Find all migration files
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.cypher")))
    
    if not migration_files:
        print(f"No migration files found in {migrations_dir}/")
        return True
    
    print(f"Found {len(migration_files)} migration file(s)")
    
    for filepath in migration_files:
        filename = os.path.basename(filepath)
        print(f"Running: {filename}")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Split by semicolons to get individual statements
        # Filter out comments and empty lines
        statements = []
        for statement in content.split(';'):
            # Remove comments and clean up
            lines = []
            for line in statement.split('\n'):
                line = line.strip()
                if line and not line.startswith('//'):
                    lines.append(line)
            clean_statement = ' '.join(lines).strip()
            if clean_statement:
                statements.append(clean_statement)
        
        # Execute each statement
        with neo4j.driver.session() as session:
            for stmt in statements:
                try:
                    session.run(stmt)
                    print(f"Executed: {stmt[:60]}...")
                except Exception as e:
                    print(f"Warning: {e}")
                    # Continue - some constraints may already exist
    
    print("All migrations completed!")
    return True


if __name__ == "__main__":
    run_migrations()
