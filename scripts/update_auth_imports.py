#!/usr/bin/env python3
"""
Update imports for auth module refactoring
"""
import re
import sys
from pathlib import Path

def update_imports(file_path: Path):
    """Update auth imports in a file"""

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Skip binary files
        return None

    original_content = content
    changes = []

    # Pattern 1: from core.auth.jwt import X
    pattern1 = r'from core\.auth_jwt import'
    replacement1 = 'from core.auth.jwt import'
    if re.search(pattern1, content):
        content = re.sub(pattern1, replacement1, content)
        changes.append(f"  ✓ core.auth_jwt → core.auth.jwt")

    # Pattern 2: from core.auth.unified import X
    pattern2 = r'from core\.unified_auth import'
    replacement2 = 'from core.auth.unified import'
    if re.search(pattern2, content):
        content = re.sub(pattern2, replacement2, content)
        changes.append(f"  ✓ core.unified_auth → core.auth.unified")

    # Pattern 3: from core.auth.system import X
    pattern3 = r'from core\.auth_system import'
    replacement3 = 'from core.auth.system import'
    if re.search(pattern3, content):
        content = re.sub(pattern3, replacement3, content)
        changes.append(f"  ✓ core.auth_system → core.auth.system")

    # Pattern 4: from core.auth.legacy import X (old auth.py)
    # This is trickier - need to check if it's using the old auth.py
    pattern4 = r'from core\.auth import(?!\s+(jwt|unified|system|legacy))'
    replacement4 = 'from core.auth.legacy import'
    if re.search(pattern4, content):
        content = re.sub(pattern4, replacement4, content)
        changes.append(f"  ✓ core.auth → core.auth.legacy")

    # Pattern 5: import core.auth.jwt as X
    pattern5 = r'import core\.auth_jwt'
    replacement5 = 'import core.auth.jwt'
    if re.search(pattern5, content):
        content = re.sub(pattern5, replacement5, content)
        changes.append(f"  ✓ import core.auth.jwt → import core.auth.jwt")

    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return changes

    return None

def main():
    project_root = Path(__file__).parent.parent

    # Find all Python files
    py_files = list(project_root.glob('**/*.py'))

    # Exclude certain directories
    exclude_dirs = {'.venv', 'venv', 'node_modules', '.git', '__pycache__',
                   'migrations', 'legacy_ui', 'backend_clean'}

    py_files = [
        f for f in py_files
        if not any(excl in f.parts for excl in exclude_dirs)
    ]

    print(f"🔍 Scanning {len(py_files)} Python files...\n")

    updated_count = 0

    for file_path in py_files:
        changes = update_imports(file_path)
        if changes:
            print(f"📝 {file_path.relative_to(project_root)}")
            for change in changes:
                print(change)
            print()
            updated_count += 1

    print(f"\n✅ Updated {updated_count} files")

if __name__ == "__main__":
    main()
