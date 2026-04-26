import json

from ops.logging.audit_logger import AuditLogger


def test_audit_logger_chain_valid(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(log_file=str(log_path))

    logger.log_event(actor="tester", action="register", target="model:v1", outcome="success", request_id="r1")
    logger.log_event(actor="tester", action="promote", target="model:v1", outcome="success", request_id="r2")

    result = logger.verify_chain()
    assert result["valid"] is True
    assert result["events"] == 2


def test_audit_logger_chain_detects_tamper(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(log_file=str(log_path))

    logger.log_event(actor="tester", action="register", target="model:v1", outcome="success", request_id="r1")
    logger.log_event(actor="tester", action="promote", target="model:v1", outcome="success", request_id="r2")

    lines = log_path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["outcome"] = "tampered"
    lines[1] = json.dumps(second, sort_keys=True)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = logger.verify_chain()
    assert result["valid"] is False
    assert result["errors"]
