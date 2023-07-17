import subprocess
import json

def delete_old_versions(service_name):
    result = subprocess.run(["gcloud", "app", "versions", "list", "--service", service_name, "--format", "json"], stdout=subprocess.PIPE, check=True)
    versions = json.loads(result.stdout)

    # Sort the version by their creation time
    versions.sort(key=lambda x: x["version"]["createTime"], reverse=True)

    # Displaying earliest and latest versions before deleting
    print(f"LATEST version: {versions[0]['id']}")
    print(f"EARLIEST version: {versions[-1]['id']}")

    # Only keep the versions we want to delete, in this case, the latest 10.
    versions_to_delete = versions[10:]
 
    for v in versions_to_delete:
        version_id = v["id"]
        print(f"Deleting version {version_id}")
        subprocess.run(["gcloud", "app", "versions", "delete", version_id, "--service", service_name, "--quiet"], check=True)

    result = subprocess.run(["gcloud", "app", "versions", "list", "--service", service_name, "--format", "json"], stdout=subprocess.PIPE, check=True)
    versions = json.loads(result.stdout)
    versions.sort(key=lambda x: x["version"]["createTime"], reverse=True)

    # Displaying earliest and latest versions after deleting
    print(f"\nAfter deletion:")
    print(f"LATEST version: {versions[0]['id']}")
    print(f"EARLIEST version: {versions[-1]['id']}")

delete_old_versions("default")