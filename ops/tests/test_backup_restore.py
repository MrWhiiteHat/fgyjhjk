from pathlib import Path

import yaml

from ops.backups.backup_manager import BackupManager
from ops.backups.restore_manager import RestoreManager
from ops.backups.verify_backup import verify_backup_archive


def test_backup_and_restore_roundtrip(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "sample.txt"
    source_file.write_text("hello backup", encoding="utf-8")

    backup_root = tmp_path / "archives"
    policy = {
        "backup_root": str(backup_root.as_posix()),
        "sources": [str(source_dir.as_posix())],
        "include_files": [],
        "retention": {"keep_daily": 3, "keep_weekly": 2, "keep_monthly": 2},
        "compression": {"format": "zip", "level": 6},
        "integrity": {"generate_manifest": True, "verify_on_create": True},
    }
    policy_path = tmp_path / "backup_policy.yaml"
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    manager = BackupManager(policy_path=str(policy_path))
    backup_result = manager.create_backup(tier="daily")

    archive_path = Path(backup_result["archive_path"])
    assert archive_path.exists()

    verification = verify_backup_archive(archive_path)
    assert verification["valid"] is True

    restore_root = tmp_path / "restore"
    restore = RestoreManager(default_restore_root=str(restore_root))
    restored = restore.restore(archive_path=archive_path, restore_root=restore_root, overwrite=True)

    assert restored["restored_count"] > 0
    restored_files = [Path(item) for item in restored["restored_files"]]
    restored_file = next((item for item in restored_files if item.name == "sample.txt"), None)
    assert restored_file is not None
    assert restored_file.exists()
    assert restored_file.read_text(encoding="utf-8") == "hello backup"
