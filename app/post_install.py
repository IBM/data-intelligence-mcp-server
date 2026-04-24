# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool
# Post-installation script to copy skills folder to user-specified location.

import shutil
import sys
from pathlib import Path


# Constants
SKILLS_COPY_CANCELLED_MSG = "❌ Skills folder copy cancelled."


def get_skills_source_path():
    """Get the path to the skills folder in the installed package."""
    # Get the directory where this script is located
    current_dir = Path(__file__).parent.parent
    skills_path = current_dir / "skills"
    
    if not skills_path.exists():
        # Try alternative location using importlib.resources (Python 3.12+)
        try:
            import importlib.resources as resources
            traversable = resources.files("skills")
            # Convert Traversable to Path
            skills_path = Path(str(traversable))
        except Exception:
            pass
    
    return skills_path


def merge_directories(src, dst):
    """
    Recursively merge source directory into destination directory.
    - Adds new files from source
    - Overrides existing files with source versions
    - Preserves files in destination that don't exist in source
    """
    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)
    
    for item in src.iterdir():
        src_item = src / item.name
        dst_item = dst / item.name
        
        if src_item.is_dir():
            # Recursively merge subdirectories
            merge_directories(src_item, dst_item)
        else:
            # Copy file, overwriting if it exists
            shutil.copy2(src_item, dst_item)


def _process_yes_no_answer(answer):
    """
    Process a yes/no answer and handle cancellation if negative.
    
    Args:
        answer: User input string to process
        
    Returns:
        bool: True if answer is 'yes' or 'y' (case-insensitive), False otherwise
    """
    if answer.strip().lower() in ["yes", "y"]:
        return True
    print(SKILLS_COPY_CANCELLED_MSG)
    return False


def _ensure_destination_exists(destination_base):
    """Ensure the destination directory exists, creating it if needed."""
    if destination_base.exists():
        return True
    
    create = input(f"\n⚠️  Path '{destination_base}' does not exist. Create it? (yes/no): ")
    if not _process_yes_no_answer(create):
        return False
    
    try:
        destination_base.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {destination_base}")
        return True
    except Exception as e:
        print(f"❌ Failed to create directory: {e}")
        return False


def _confirm_merge_if_exists(skills_destination):
    """Confirm with user if they want to merge with existing skills folder."""
    if not skills_destination.exists():
        return True
    
    print(f"\n📁 Skills folder already exists at: {skills_destination}")
    print("\n⚠️  Merge behavior:")
    print("   • New files from the package will be added")
    print("   • Existing files will be overridden with package versions")
    print("   • Your other files in the folder will be preserved")
    
    response = input("\nDo you want to proceed with merging? (yes/no): ")
    if not _process_yes_no_answer(response):
        return False
    return True


def _perform_copy_or_merge(skills_source, skills_destination):
    """Perform the actual copy or merge operation."""
    if skills_destination.exists():
        print("🔄 Merging folders...")
        merge_directories(skills_source, skills_destination)
        print(f"\n✅ Skills folder successfully merged into: {skills_destination}")
    else:
        print("📋 Copying folder...")
        shutil.copytree(skills_source, skills_destination)
        print(f"\n✅ Skills folder successfully copied to: {skills_destination}")


def copy_skills_to_destination():
    """Copy skills folder to user-specified path with confirmation."""
    try:
        # Get source path
        skills_source = get_skills_source_path()
        
        # Check if source exists
        if not skills_source.exists():
            print(f"⚠️  Skills folder not found at: {skills_source}")
            return False
        
        # Display header
        print("\n📋 IBM watsonx Data Intelligence MCP Server - Skills Setup")
        print("━" * 60)
        print(f"Source: {skills_source}")
        print("━" * 60)
        
        # Ask user for destination path
        print("\nEnter the path where you want to copy the skills folder")
        print("(or press Enter to skip):")
        custom_path = input("Path: ").strip()
        
        if not custom_path:
            print("❌ Skills folder copy skipped.")
            print(f"💡 You can manually copy the skills folder from: {skills_source}")
            return False
        
        # Expand user path (handles ~)
        destination_base = Path(custom_path).expanduser().resolve()
        
        # Ensure destination directory exists
        if not _ensure_destination_exists(destination_base):
            return False
        
        skills_destination = destination_base / "skills"
        
        # Confirm merge if destination already exists
        if not _confirm_merge_if_exists(skills_destination):
            return False
        
        # Show final destination and ask for confirmation
        print(f"\n📍 Final destination: {skills_destination}")
        response = input("\nProceed with copying? (yes/no): ")
        
        if not _process_yes_no_answer(response):
            print(f"💡 You can manually copy the skills folder from: {skills_source}")
            return False
        
        _perform_copy_or_merge(skills_source, skills_destination)
        return True
            
    except Exception as e:
        print(f"❌ Error copying skills folder: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for post-installation."""
    print("\n" + "=" * 60)
    print("IBM watsonx Data Intelligence MCP Server - Post Installation")
    print("=" * 60)
    
    copy_skills_to_destination()
    
    print("\n" + "=" * 60)
    print("Installation complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
