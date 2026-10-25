"""Runner data tables.

Extracted from runner.py.
"""

_CLI_OVERRIDES = (
    # (argparse dest, config key)
    ("poll_interval", "poll_interval_sec"),
    ("timeout", "default_timeout_sec"),
    ("max_output_bytes", "max_output_bytes"),
    ("max_job_age", "max_job_age_sec"),
    ("retention_days", "output_retention_days"),
    ("task_timeout", "task_timeout"),
    ("max_query_budget", "max_query_budget"),
    ("max_queries_per_hour", "max_queries_per_hour"),
    ("max_result_view", "max_result_view"),
    ("judge", "judge"),
    ("dag_mode", "dag_mode"),
    ("oracle_mode", "oracle_mode"),
    ("oracle_opinion", "oracle_opinion_mode"),
    ("protocol_v2", "protocol_v2"),
    ("answer_only", "answer_only"),
    ("remediation_mode", "remediation_mode"),
    ("require_review", "require_review"),
    ("local_signals", "local_signals"),
    ("local_signal_port", "local_signal_port"),
    ("wake_cooldown", "local_wake_cooldown_sec"),
    ("log_max_bytes", "log_max_bytes"),
    ("log_backups", "log_backups"),
    ("transports", "transports"),
    ("oracle_log", "oracle_log"),
    ("oracle_log_max_bytes", "oracle_log_max_bytes"),
    ("oracle_log_backups", "oracle_log_backups"),
)

_YARA_RULES = (
    "rule hp_encoded_exec {\n"
    "  strings:\n"
    "    $a = \"eval(base64_decode\" nocase\n"
    "    $b = \"FromBase64String\" nocase\n"
    "    $c = \"Invoke-Expression\" nocase\n"
    "  condition:\n"
    "    any of them\n"
    "}\n"
    "rule hp_webshell {\n"
    "  strings:\n"
    "    $php = \"<?php\" nocase\n"
    "    $sys = \"system($_\" nocase\n"
    "    $sh = \"shell_exec(\" nocase\n"
    "  condition:\n"
    "    $php and ($sys or $sh)\n"
    "}\n"
    "rule hp_cred_dump {\n"
    "  strings:\n"
    "    $a = \"sekurlsa::logonpasswords\" nocase\n"
    "    $b = \"sekurlsa::wdigest\" nocase\n"
    "    $c = \"mimikatz\" nocase\n"
    "  condition:\n"
    "    any of them\n"
    "}\n"
    "rule hp_reverse_shell {\n"
    "  strings:\n"
    "    $a = \"/dev/tcp/\" nocase\n"
    "    $b = \"bash -i >&\" nocase\n"
    "    $c = \"nc -e \" nocase\n"
    "    $d = \"ncat -e \" nocase\n"
    "  condition:\n"
    "    any of them\n"
    "}\n"
)

