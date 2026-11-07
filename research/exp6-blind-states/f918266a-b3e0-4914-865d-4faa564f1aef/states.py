import os
import shutil

DESKTOP_REL = os.path.join("home", "user", "Desktop")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, DESKTOP_REL)


def correct_python_monitor_and_log(snapshot_dir, out_dir):
    desktop = _prepare(snapshot_dir, out_dir)
    script_path = os.path.join(desktop, "monitor.py")
    log_path = os.path.join(desktop, "log.txt")
    script_code = (
        "import subprocess, sys\n"
        "proc = subprocess.Popen(\n"
        "    [sys.executable, '-u', 'calculator.py'],\n"
        "    stdout=subprocess.PIPE,\n"
        "    stderr=subprocess.STDOUT,\n"
        "    text=True,\n"
        "    bufsize=1,\n"
        ")\n"
        "with open('log.txt', 'a', encoding='utf-8') as log_f:\n"
        "    for line in proc.stdout:\n"
        "        sys.stdout.write(line)\n"
        "        sys.stdout.flush()\n"
        "        if 'ERROR' in line:\n"
        "            log_f.write(line)\n"
        "            log_f.flush()\n"
    )
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(script_code)
    with open(log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("ERROR: Division by zero is not allowed.\n")


def correct_bash_monitor_and_log(snapshot_dir, out_dir):
    desktop = _prepare(snapshot_dir, out_dir)
    script_path = os.path.join(desktop, "monitor.sh")
    log_path = os.path.join(desktop, "log.txt")
    script_code = (
        "#!/usr/bin/env bash\n"
        "python3 -u /home/user/Desktop/calculator.py | while IFS= read -r line; do\n"
        "  echo \"$line\"\n"
        "  if [[ \"$line\" == *\"ERROR\"* ]]; then\n"
        "    echo \"$line\" >> /home/user/Desktop/log.txt\n"
        "  fi\n"
        "done\n"
    )
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(script_code)
    with open(log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("ERROR: Division by zero is not allowed.\n")


def wrong_log_in_home_instead_of_desktop(snapshot_dir, out_dir):
    desktop = _prepare(snapshot_dir, out_dir)
    home_dir = os.path.dirname(desktop)
    with open(os.path.join(home_dir, "log.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("ERROR: Division by zero is not allowed.\n")


def wrong_logged_all_stdout_lines_not_just_error(snapshot_dir, out_dir):
    desktop = _prepare(snapshot_dir, out_dir)
    log_path = os.path.join(desktop, "log.txt")
    with open(log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(
            "Simple Calculator\n"
            "Available operations:\n"
            "1. Addition (+)\n"
            "2. Subtraction (-)\n"
            "3. Multiplication (*)\n"
            "4. Division (/)\n"
            "ERROR: Division by zero is not allowed.\n"
        )


def wrong_overwrote_calculator_py(snapshot_dir, out_dir):
    desktop = _prepare(snapshot_dir, out_dir)
    calc_path = os.path.join(desktop, "calculator.py")
    log_path = os.path.join(desktop, "log.txt")
    with open(calc_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Overwritten calculator with monitor\n")
    with open(log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("ERROR: Division by zero is not allowed.\n")


def wrong_stripped_error_keyword_from_log(snapshot_dir, out_dir):
    desktop = _prepare(snapshot_dir, out_dir)
    log_path = os.path.join(desktop, "log.txt")
    with open(log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("Division by zero is not allowed.\n")


def wrong_empty_log_txt_filtered_wrong_word(snapshot_dir, out_dir):
    desktop = _prepare(snapshot_dir, out_dir)
    script_path = os.path.join(desktop, "monitor.sh")
    log_path = os.path.join(desktop, "log.txt")
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("#!/usr/bin/env bash\npython3 calculator.py | grep 'FATAL' >> log.txt\n")
    with open(log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("")
