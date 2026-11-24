import os
import subprocess
import shutil

TARGET_REPOS = [
    "https://github.com/saidixitn/vps-automations.git",
    "https://github.com/saidixitn/Automation.git",
    "https://github.com/saidixitn/PythonProject.git",
    "https://github.com/saidixitn/Job-Posting-Alerts.git",
    "https://github.com/saidixitn/pm2-vps.git"
]

def get_git_credentials():
    p = subprocess.Popen(
        ["git", "credential", "fill"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, _ = p.communicate(input="protocol=https\nhost=github.com\n")
    creds = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()
    return creds.get("username"), creds.get("password")

username, token = get_git_credentials()
temp_dir = os.path.abspath(r"./temp_repos")
os.makedirs(temp_dir, exist_ok=True)

for repo_url in TARGET_REPOS:
    repo_name = repo_url.rstrip(".git").split("/")[-1]
    dest = os.path.join(temp_dir, repo_name)
    print(f"--- Processing {repo_name} ---")
    
    auth_url = repo_url.replace("https://", f"https://{username}:{token}@")
    
    if os.path.exists(dest):
        print(f"Directory {dest} exists. Fetching latest...")
        subprocess.run(["git", "-C", dest, "pull"], check=False)
    else:
        print(f"Cloning {repo_name} to {dest}...")
        res = subprocess.run(["git", "clone", auth_url, dest], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Successfully cloned {repo_name}")
        else:
            print(f"Failed to clone {repo_name}: {res.stderr}")

print("\nClone process finished.")
