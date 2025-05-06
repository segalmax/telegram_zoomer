#!/usr/bin/env python3
"""
Create a GitHub repository and push the current code.

Usage:
    python create_github_repo.py [username] [repo_name] [token]
    
All arguments are optional and will be prompted for if not provided.
"""

import os
import sys
import subprocess
import requests
import getpass
import argparse

def run_command(command):
    """Run a shell command and return the output"""
    print(f"Running: {command}")
    process = subprocess.run(command, shell=True, capture_output=True, text=True)
    if process.returncode != 0:
        print(f"Error: {process.stderr}")
        return None
    return process.stdout.strip()

def create_github_repo(token, repo_name, description="Telegram bot that translates NYT posts into Russian zoomer slang"):
    """Create a GitHub repository using the GitHub API"""
    print(f"Creating GitHub repository: {repo_name}")
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "name": repo_name,
        "description": description,
        "private": False,  # Change to True if you want a private repository
        "auto_init": False
    }
    
    response = requests.post("https://api.github.com/user/repos", json=data, headers=headers)
    
    if response.status_code == 201:
        print(f"Repository created successfully: {repo_name}")
        return response.json()["html_url"]
    else:
        print(f"Failed to create repository: {response.status_code}")
        print(response.json())
        return None

def setup_and_push(repo_url, username):
    """Set up git remote and push code"""
    # Configure git if needed
    username_config = run_command("git config user.name")
    if not username_config:
        run_command(f"git config user.name '{username}'")
    
    email_config = run_command("git config user.email")
    if not email_config:
        run_command(f"git config user.email '{username}@users.noreply.github.com'")
    
    # Set up remote and push
    run_command(f"git remote remove origin || true")
    run_command(f"git remote add origin {repo_url}")
    result = run_command("git push -u origin main")
    
    if result:
        print(f"Successfully pushed code to {repo_url}")
        return True
    else:
        print("Failed to push code")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Create a GitHub repository and push the current code")
    parser.add_argument("username", nargs="?", help="GitHub username")
    parser.add_argument("repo_name", nargs="?", help="Repository name")
    parser.add_argument("token", nargs="?", help="GitHub personal access token")
    
    args = parser.parse_args()
    
    print("Creating GitHub Repository and Pushing Code")
    print("------------------------------------------")
    
    # Get GitHub username
    username = args.username
    if not username:
        username = input("Enter your GitHub username: ")
    
    # Get GitHub personal access token
    token = args.token
    if not token:
        print("\nA GitHub personal access token is required.")
        print("You can create one at: https://github.com/settings/tokens")
        print("Make sure it has 'repo' permissions.")
        token = getpass.getpass("Enter your GitHub personal access token: ")
    
    # Repository name (default to directory name)
    default_name = os.path.basename(os.getcwd())
    repo_name = args.repo_name or input(f"Enter repository name (default: {default_name}): ") or default_name
    
    # Create repository
    repo_url = create_github_repo(token, repo_name)
    if not repo_url:
        print("Failed to create repository. Exiting.")
        return
    
    # Push code
    if setup_and_push(repo_url, username):
        print("\nRepository setup completed!")
        print(f"Your code is now available at: {repo_url}")
    
if __name__ == "__main__":
    main() 