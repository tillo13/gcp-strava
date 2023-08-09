import subprocess

def get_modified_files():
    result = subprocess.run(['git', 'ls-files', '--modified'], stdout=subprocess.PIPE, text=True)
    return result.stdout.splitlines()

def revert_files_to_remote(files):
    if len(files) == 0:
        print("No modified files found.")
        return
    print('Modified files:')
    print(files)
    confirmation = ''
    while confirmation.lower() not in {"yes", "no"}:
        confirmation = input("The files listed above will be changed to match the latest commit state on the remote repository. Do you want to proceed? (yes/no) ")
    if confirmation.lower() == 'yes':
        for file_path in files:
            subprocess.run(['git', 'checkout', 'origin/main', '--', file_path])
        print("Reverted changes in the listed files to their last commit state.")
    else:
        print("Aborted.")

files = get_modified_files()
revert_files_to_remote(files)