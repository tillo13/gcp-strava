import subprocess
import json

# Function to get versions of a service
def get_versions(service_name):
    result = subprocess.run(["gcloud", "app", "versions", "list", "--service", service_name, "--format", "json"], stdout=subprocess.PIPE, check=True)
    versions = json.loads(result.stdout)
    versions.sort(key=lambda x: x["version"]["createTime"], reverse=True)
    return versions

# Function to start a version
def start_version(version_id):
    subprocess.run(["gcloud", "app", "versions", "start", version_id, "--quiet"], check=True)

# Function to rollback to previous version
def rollback_to_previous_version(service_name):
    versions = get_versions(service_name)

    if len(versions) >= 2:
        current_version = versions[0]
        previous_version = versions[1]

        print(f"Rolling back from version {current_version['id']} to version {previous_version['id']}...")
        start_version(previous_version['id'])  # Start the previous version
        subprocess.run(["gcloud", "app", "versions", "migrate", previous_version["id"], "--service", service_name, "--quiet"], check=True)

        print(f"Rollback successful. Rolled back from version {current_version['id']} to version {previous_version['id']}.")
    else:
        print("Cannot rollback. There is no previous version available.")

# Rollback to the previous version
rollback_to_previous_version("default")