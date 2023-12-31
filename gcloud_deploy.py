import subprocess
import json
import time

# Set the maximum versions value here
VERSION_MAX = 15
print(f"You have chosen to keep {VERSION_MAX} versions of your app.")

# Function to get versions of a service
def get_versions(service_name):
    result = subprocess.run(["gcloud", "app", "versions", "list", "--service", service_name, "--format", "json"], stdout=subprocess.PIPE, check=True)
    versions = json.loads(result.stdout)
    versions.sort(key=lambda x: x["version"]["createTime"], reverse=True)
    return versions

# Function to delete versions
def delete_versions(service_name, versions_to_delete):
    for v in versions_to_delete:
        version_id = v["id"]
        print(f"Deleting version {version_id}")
        subprocess.run(["gcloud", "app", "versions", "delete", version_id, "--service", service_name, "--quiet"], check=True)

def deploy_app():
    start_time = time.time()
    
    # Check the current versions
    versions = get_versions("default")
    print(f"You currently have {len(versions)} versions.")
    print(f"The latest version is {versions[0]['id']}.")
    
    # Deploy new version
    if len(versions) > VERSION_MAX:
        print(f"More than {VERSION_MAX} versions exist. Deploying new version and then {len(versions)-(VERSION_MAX-1)} versions will be deleted.")
    else:
        print(f"Less than or equal to {VERSION_MAX} versions exist, no need to delete versions.")
    print("Deploying...")
    subprocess.run(["gcloud", "app", "deploy", "--quiet", "--project=gcp-strava"], check=True)
    print("Deployment done.")
    
    # Delete if needed
    if len(versions) > VERSION_MAX:
        versions = get_versions("default")
        versions_to_delete = versions[VERSION_MAX:]
        delete_versions("default", versions_to_delete)

    end_time = time.time()
    print(f"Script finished. Total execution time: {end_time - start_time} seconds.")

deploy_app()