with open('backend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if 'import logging' in line:
        new_lines.append('import sys\n')
        new_lines.append('_log_file = open("app.log", "a", buffering=1)\n')
        new_lines.append('sys.stdout = _log_file\n')
        new_lines.append('sys.stderr = _log_file\n')

new_lines.append('\n@app.get("/system/logs")\ndef get_system_logs():\n    import os\n    if os.path.exists("app.log"):\n        with open("app.log", "r") as f:\n            return f.read()\n    return "No logs"\n')

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
