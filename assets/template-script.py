# Use this script to replace the repository name in the template files

import os

repo_url = input("Enter the GitHub repository URL: ")
dir_path = input("Enter the directory path: ")

# Extract repository name from URL
repo_name = repo_url.split("https://github.com/")[1]

for root, dirs, files in os.walk(dir_path):
    for file_name in files:
        # Check if file is a markdown file
        if file_name.endswith(".md"):
            file_path = os.path.join(root, file_name)
            # Open file and read its contents
            with open(file_path, "r", encoding="utf-8") as f:
                file_contents = f.read()
            # Replace text and write new contents back to file
            new_contents = file_contents.replace("SVijayB/Repo-Template", repo_name)
            with open(file_path, "w", encoding="utf8") as f:
                f.write(new_contents)

print("Done!")
