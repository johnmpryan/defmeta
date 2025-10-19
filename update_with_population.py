# update_populations_no_django.py
import csv
import psycopg2
from pathlib import Path

def update_populations_from_csv(csv_filename, db_config):
    """
    Update population data directly in PostgreSQL without Django.
    
    Args:
        csv_filename: Path to CSV file
        db_config: Dictionary with database connection details
    """
    csv_path = Path(csv_filename)
    
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            port=db_config.get('port', 5432)
        )
        cursor = conn.cursor()
        print(f"✓ Connected to database: {db_config['database']}")
        
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        return
    
    updated_count = 0
    not_found_count = 0
    error_count = 0
    
    print(f"\nReading populations from: {csv_filename}\n")
    
    # Read CSV and update database
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        # Strip whitespace from headers
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        
        for row in reader:
            state_name = row['subreddit'].strip().lower()
            population_str = row['population'].strip()
            
            try:
                # Convert population to integer
                population = int(population_str.replace(',', ''))
                
                # Update query (case-insensitive search)
                update_query = """
                    UPDATE subreddits 
                    SET population = %s 
                    WHERE LOWER(name) = LOWER(%s)
                """
                
                cursor.execute(update_query, (population, state_name))
                
                if cursor.rowcount > 0:
                    updated_count += 1
                    print(f"✓ Updated {state_name}: {population:,}")
                else:
                    not_found_count += 1
                    print(f"✗ Subreddit not found: {state_name}")
                    
            except ValueError:
                error_count += 1
                print(f"✗ Invalid population value for {state_name}: {population_str}")
            except Exception as e:
                error_count += 1
                print(f"✗ Error updating {state_name}: {e}")
        
        # Commit changes
        conn.commit()
    
    # Close connection
    cursor.close()
    conn.close()
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY:")
    print(f"  Updated: {updated_count}")
    print(f"  Not found: {not_found_count}")
    print(f"  Errors: {error_count}")
    print("="*50)

def main():
    """
    Main function - configure your database connection and CSV file
    """
    # LOCAL DATABASE CONFIG
    local_db_config = {
        'database': 'reddit_data',
        'user': 'django_user',
        'password': '#redditapp#',
        'host': 'localhost',
        'PORT': '5432'
    }
    
    # HEROKU DATABASE CONFIG (if needed)
    # Get connection details from: heroku pg:credentials:url -a reddit-stats-app
    heroku_db_config = {
        'host': 'YOUR_HEROKU_HOST',
        'database': 'YOUR_HEROKU_DB',
        'user': 'YOUR_HEROKU_USER',
        'password': 'YOUR_HEROKU_PASSWORD',
        'port': 5432
    }
    
    # CSV file location
    csv_filename = r"C:\Users\johnm\Documents\app development\reddit stats tracker\state_populations.csv"
    
    # Choose which database to update
    update_populations_from_csv(csv_filename, local_db_config)

if __name__ == "__main__":
    main()