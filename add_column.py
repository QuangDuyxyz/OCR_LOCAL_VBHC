import sqlite3
import os
import sys
from pathlib import Path

# Function to add do_mat column to document_versions table if it doesn't exist
def add_do_mat_column(db_path):
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if do_mat column exists in document_versions table
        cursor.execute("PRAGMA table_info(document_versions)")
        columns = [info[1] for info in cursor.fetchall()]
        
        # If do_mat column doesn't exist, add it
        if 'do_mat' not in columns:
            print(f"Adding do_mat column to document_versions table...")
            cursor.execute("ALTER TABLE document_versions ADD COLUMN do_mat TEXT")
            conn.commit()
            print(f"Successfully added do_mat column!")
        else:
            print(f"do_mat column already exists in document_versions table.")
        
        # Close connection
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding do_mat column: {str(e)}")
        return False

if __name__ == "__main__":
    # Path to database directory
    db_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "database"
    db_path = db_dir / "documents.db"
    
    # Check if database file exists
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        sys.exit(1)
    
    # Add do_mat column
    if add_do_mat_column(db_path):
        print("Column addition completed successfully.")
    else:
        print("Could not add column to database.")
