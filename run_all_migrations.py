#!/usr/bin/env python3
"""
Master script to run all migrations in sequence.
"""
import os
import sys
import subprocess

# Migration folders in order
MIGRATIONS = [
    "01_confluence_to_glpi_migration",
    "02_project_jira_to_glpi_project_tasks_migration",
    "03_support_jira_to_glpi_assistance_tickets_migration",
]

def run_migration(folder, script="main.py"):
    """Run a migration script in the specified folder."""
    print(f"\n{'='*80}")
    print(f"Running migration: {folder}")
    print(f"{'='*80}\n")

    # Change to migration folder
    os.chdir(folder)

    try:
        # Run the migration script
        result = subprocess.run([sys.executable, script], check=True)
        print(f"\n✓ {folder} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {folder} failed with error: {e}")
        return False
    finally:
        # Return to root directory
        os.chdir('..')

def main():
    """Run all migrations in sequence."""
    print("=" * 80)
    print("IT-Agent: Running All Migrations")
    print("=" * 80)

    # Get root directory
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    # Track results
    results = {}

    # Run each migration
    for migration in MIGRATIONS:
        if not os.path.exists(migration):
            print(f"\n⚠ Warning: Migration folder not found: {migration}")
            results[migration] = "SKIPPED"
            continue

        success = run_migration(migration)
        results[migration] = "SUCCESS" if success else "FAILED"

        # Stop on failure (optional - remove if you want to continue)
        if not success:
            print(f"\n✗ Stopped at {migration} due to failure")
            break

    # Print summary
    print("\n" + "=" * 80)
    print("Migration Summary")
    print("=" * 80)
    for migration, status in results.items():
        status_symbol = "✓" if status == "SUCCESS" else "✗" if status == "FAILED" else "⚠"
        print(f"{status_symbol} {migration}: {status}")

    # Exit with appropriate code
    if all(status == "SUCCESS" for status in results.values()):
        print("\n✓ All migrations completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Some migrations failed or were skipped")
        sys.exit(1)

if __name__ == '__main__':
    main()
