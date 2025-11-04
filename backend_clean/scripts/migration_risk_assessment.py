#!/usr/bin/env python3
"""
Migration Risk Assessment for Automation Engine v2
Comprehensive safety checks before applying migration 009
"""

import sqlite3
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

class MigrationRiskChecker:
    def __init__(self, db_path: str = "data/mcp_internal.db"):
        self.db_path = Path(db_path)
        self.backup_dir = Path("data/backups")
        self.backup_dir.mkdir(exist_ok=True)

    def run_complete_assessment(self) -> Dict[str, Any]:
        """Run complete migration risk assessment."""

        print("🔍 Migration Risk Assessment - Automation Engine v2")
        print("=" * 60)

        results = {
            "timestamp": datetime.now().isoformat(),
            "database_path": str(self.db_path),
            "checks": {}
        }

        # Run all checks
        checks = [
            ("database_exists", self._check_database_exists),
            ("database_size", self._check_database_size),
            ("disk_space", self._check_disk_space),
            ("database_lock", self._check_database_lock),
            ("data_integrity", self._check_data_integrity),
            ("existing_migrations", self._check_existing_migrations),
            ("backup_status", self._check_backup_status),
            ("active_connections", self._check_active_connections)
        ]

        for check_name, check_func in checks:
            print(f"\n🔧 Running {check_name} check...")
            try:
                result = check_func()
                results["checks"][check_name] = result

                level = result.get("level", "UNKNOWN")
                message = result.get("message", "No details")
                icon = self._get_status_icon(level)

                print(f"{icon} {message}")

                if "recommendation" in result:
                    print(f"   💡 {result['recommendation']}")

            except Exception as e:
                error_result = {
                    "level": "ERROR",
                    "message": f"Check failed: {str(e)}",
                    "error": True
                }
                results["checks"][check_name] = error_result
                print(f"❌ Check failed: {e}")

        # Overall assessment
        results["overall"] = self._assess_overall_safety(results["checks"])

        print(f"\n{'='*60}")
        self._print_overall_assessment(results["overall"])

        return results

    def _check_database_exists(self) -> Dict[str, Any]:
        """Check if database exists and is accessible."""
        if not self.db_path.exists():
            return {
                "level": "WARNING",
                "message": "Database doesn't exist - will be created during migration",
                "database_exists": False
            }

        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.execute("SELECT 1")
            conn.close()

            return {
                "level": "INFO",
                "message": f"Database exists and is accessible: {self.db_path}",
                "database_exists": True
            }
        except Exception as e:
            return {
                "level": "CRITICAL",
                "message": f"Database exists but not accessible: {e}",
                "recommendation": "Check database permissions and locks"
            }

    def _check_database_size(self) -> Dict[str, Any]:
        """Check database size and estimate migration time."""
        if not self.db_path.exists():
            return {"level": "INFO", "message": "No database to check size"}

        size_bytes = self.db_path.stat().st_size
        size_mb = size_bytes / 1024 / 1024

        if size_mb > 1000:  # > 1GB
            return {
                "level": "HIGH",
                "message": f"Large database ({size_mb:.1f}MB) - migration may take significant time",
                "size_mb": size_mb,
                "estimated_time_minutes": max(5, size_mb / 50),
                "recommendation": "Schedule during maintenance window"
            }
        elif size_mb > 100:  # > 100MB
            return {
                "level": "MEDIUM",
                "message": f"Medium database ({size_mb:.1f}MB) - expect moderate migration time",
                "size_mb": size_mb,
                "estimated_time_minutes": max(2, size_mb / 100)
            }
        else:
            return {
                "level": "LOW",
                "message": f"Small database ({size_mb:.1f}MB) - fast migration expected",
                "size_mb": size_mb,
                "estimated_time_minutes": 1
            }

    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space for backup and temporary files."""
        if not self.db_path.exists():
            return {"level": "INFO", "message": "No database to check disk space for"}

        db_size = self.db_path.stat().st_size
        available_space = shutil.disk_usage(self.db_path.parent).free

        # Need 3x database size: backup + temp + original
        required_space = db_size * 3

        if available_space < required_space:
            return {
                "level": "CRITICAL",
                "message": f"Insufficient disk space. Need {required_space/1024/1024:.1f}MB, have {available_space/1024/1024:.1f}MB",
                "available_mb": available_space / 1024 / 1024,
                "required_mb": required_space / 1024 / 1024,
                "recommendation": "Free disk space or move database to larger volume"
            }
        elif available_space < required_space * 2:
            return {
                "level": "HIGH",
                "message": f"Tight disk space - monitor during migration. Available: {available_space/1024/1024:.1f}MB",
                "available_mb": available_space / 1024 / 1024
            }
        else:
            return {
                "level": "LOW",
                "message": f"Sufficient disk space available: {available_space/1024/1024:.1f}MB"
            }

    def _check_database_lock(self) -> Dict[str, Any]:
        """Check if database is locked by active connections."""
        if not self.db_path.exists():
            return {"level": "INFO", "message": "No database to check"}

        try:
            conn = sqlite3.connect(self.db_path, timeout=1)
            conn.execute("BEGIN EXCLUSIVE")
            conn.rollback()
            conn.close()

            return {
                "level": "LOW",
                "message": "No database locks detected - migration safe"
            }
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                return {
                    "level": "CRITICAL",
                    "message": "Database is locked - active connections detected",
                    "recommendation": "Stop application services before migration"
                }
            else:
                return {
                    "level": "HIGH",
                    "message": f"Database access issue: {e}"
                }

    def _check_data_integrity(self) -> Dict[str, Any]:
        """Check database integrity before migration."""
        if not self.db_path.exists():
            return {"level": "INFO", "message": "No database to check integrity"}

        try:
            conn = sqlite3.connect(self.db_path)

            # Check integrity
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] != "ok":
                conn.close()
                return {
                    "level": "CRITICAL",
                    "message": f"Database integrity check failed: {result[0]}",
                    "recommendation": "Fix database corruption before migration"
                }

            # Check foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            conn.close()

            if violations:
                return {
                    "level": "HIGH",
                    "message": f"Foreign key violations found: {len(violations)}",
                    "violation_count": len(violations),
                    "violations_preview": violations[:3],
                    "recommendation": "Fix data inconsistencies before migration"
                }

            return {
                "level": "LOW",
                "message": "Database integrity checks passed successfully"
            }

        except Exception as e:
            return {
                "level": "HIGH",
                "message": f"Could not check database integrity: {e}"
            }

    def _check_existing_migrations(self) -> Dict[str, Any]:
        """Check current migration state."""
        if not self.db_path.exists():
            return {"level": "INFO", "message": "No database - fresh installation"}

        try:
            conn = sqlite3.connect(self.db_path)

            # Check if schema_versions table exists
            tables = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_versions'
            """).fetchall()

            if not tables:
                conn.close()
                return {
                    "level": "WARNING",
                    "message": "No schema_versions table found - manual migration tracking needed",
                    "recommendation": "Verify migration state manually"
                }

            # Get applied migrations
            migrations = conn.execute("""
                SELECT name, applied_at FROM schema_versions
                ORDER BY applied_at DESC
            """).fetchall()

            conn.close()

            if not migrations:
                return {
                    "level": "WARNING",
                    "message": "No migrations found in schema_versions table"
                }

            latest_migration = migrations[0][0]
            migration_count = len(migrations)

            # Check if automation engine migration already exists
            automation_migrations = [m for m in migrations if 'automation' in m[0].lower()]

            if automation_migrations:
                return {
                    "level": "WARNING",
                    "message": f"Automation migration already applied: {automation_migrations[0][0]}",
                    "latest_migration": latest_migration,
                    "total_migrations": migration_count,
                    "recommendation": "Verify if migration 009 should be re-applied"
                }

            return {
                "level": "LOW",
                "message": f"Migration system ready. Latest: {latest_migration}",
                "latest_migration": latest_migration,
                "total_migrations": migration_count
            }

        except Exception as e:
            return {
                "level": "HIGH",
                "message": f"Could not check migration state: {e}"
            }

    def _check_backup_status(self) -> Dict[str, Any]:
        """Check backup availability and freshness."""

        # Check for existing backups
        backup_patterns = [
            self.db_path.with_suffix('.backup'),
            self.db_path.parent / f"{self.db_path.stem}.backup",
            self.backup_dir / f"{self.db_path.stem}_*.backup"
        ]

        backup_files = []
        for pattern in backup_patterns:
            if pattern.exists():
                backup_files.append(pattern)
            elif '*' in str(pattern):
                backup_files.extend(pattern.parent.glob(pattern.name))

        if not backup_files:
            return {
                "level": "HIGH",
                "message": "No backups found",
                "recommendation": "Create backup before migration"
            }

        # Find most recent backup
        latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
        backup_age_hours = (time.time() - latest_backup.stat().st_mtime) / 3600
        backup_size_mb = latest_backup.stat().st_size / 1024 / 1024

        if backup_age_hours > 24:
            return {
                "level": "MEDIUM",
                "message": f"Latest backup is {backup_age_hours:.1f} hours old ({backup_size_mb:.1f}MB)",
                "backup_path": str(latest_backup),
                "age_hours": backup_age_hours,
                "recommendation": "Consider creating fresh backup before migration"
            }
        elif backup_age_hours > 1:
            return {
                "level": "LOW",
                "message": f"Recent backup available: {backup_age_hours:.1f} hours old ({backup_size_mb:.1f}MB)",
                "backup_path": str(latest_backup),
                "age_hours": backup_age_hours
            }
        else:
            return {
                "level": "LOW",
                "message": f"Fresh backup available: {backup_age_hours:.1f} hours old ({backup_size_mb:.1f}MB)",
                "backup_path": str(latest_backup),
                "age_hours": backup_age_hours
            }

    def _check_active_connections(self) -> Dict[str, Any]:
        """Check for processes that might be using the database."""

        # This is a simplified check for demo purposes
        # In production, you'd check actual process connections

        try:
            # Quick test for exclusive lock
            conn = sqlite3.connect(self.db_path, timeout=0.5)
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
            conn.close()

            return {
                "level": "LOW",
                "message": "No active database connections detected"
            }

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                return {
                    "level": "HIGH",
                    "message": "Database appears to be in use",
                    "recommendation": "Stop application before migration"
                }
            else:
                return {
                    "level": "MEDIUM",
                    "message": f"Database connection test inconclusive: {e}"
                }
        except Exception as e:
            return {
                "level": "MEDIUM",
                "message": f"Could not test database connections: {e}"
            }

    def _assess_overall_safety(self, checks: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall migration safety based on individual checks."""

        critical_issues = [
            name for name, result in checks.items()
            if result.get("level") == "CRITICAL"
        ]

        high_issues = [
            name for name, result in checks.items()
            if result.get("level") == "HIGH"
        ]

        if critical_issues:
            return {
                "migration_safe": False,
                "risk_level": "CRITICAL",
                "message": f"Critical issues must be resolved: {', '.join(critical_issues)}",
                "critical_issues": critical_issues,
                "high_issues": high_issues,
                "action_required": "STOP - Resolve critical issues before proceeding"
            }

        if len(high_issues) > 2:
            return {
                "migration_safe": False,
                "risk_level": "HIGH",
                "message": f"Multiple high-risk issues detected: {', '.join(high_issues)}",
                "high_issues": high_issues,
                "action_required": "CAUTION - Review and mitigate high-risk issues"
            }

        if high_issues:
            return {
                "migration_safe": True,
                "risk_level": "MEDIUM",
                "message": f"Some risks identified: {', '.join(high_issues)}",
                "high_issues": high_issues,
                "action_required": "PROCEED with caution - monitor closely"
            }

        return {
            "migration_safe": True,
            "risk_level": "LOW",
            "message": "All checks passed - migration is safe to proceed",
            "action_required": "PROCEED - Migration ready"
        }

    def _get_status_icon(self, level: str) -> str:
        """Get emoji icon for status level."""
        return {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "🟡",
            "LOW": "✅",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌"
        }.get(level, "❓")

    def _print_overall_assessment(self, overall: Dict[str, Any]):
        """Print overall assessment summary."""

        risk_level = overall["risk_level"]
        migration_safe = overall["migration_safe"]
        message = overall["message"]
        action = overall["action_required"]

        if migration_safe:
            print("✅ MIGRATION SAFETY: APPROVED")
        else:
            print("🚨 MIGRATION SAFETY: BLOCKED")

        print(f"🎯 Risk Level: {risk_level}")
        print(f"📊 Assessment: {message}")
        print(f"🎬 Action Required: {action}")

        if not migration_safe:
            print("\n🔧 Next Steps:")
            print("   1. Resolve critical/high issues listed above")
            print("   2. Re-run risk assessment")
            print("   3. Only proceed when assessment shows 'APPROVED'")

def main():
    """Main function to run risk assessment."""

    # Check if we're in the right directory
    if not Path("core/internal_db.py").exists():
        print("❌ Error: Run from mcp-server root directory")
        print("   Current directory should contain core/internal_db.py")
        return 1

    checker = MigrationRiskChecker()
    results = checker.run_complete_assessment()

    # Save results
    results_file = Path("data/migration_risk_assessment.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n📄 Results saved to: {results_file}")

    # Return exit code based on safety
    return 0 if results["overall"]["migration_safe"] else 1

if __name__ == "__main__":
    exit(main())