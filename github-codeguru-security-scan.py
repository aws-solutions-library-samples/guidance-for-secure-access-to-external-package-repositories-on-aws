import os
import re
import csv
import json
import time
import boto3
import base64
import requests
import subprocess
from datetime import datetime
from dateutil import tz

# Environment Variables
sns_topic_arn = os.environ.get("SNSTopic")
github_repo = os.environ.get("PrivateGitHubRepo")
github_owner = os.environ.get("PrivateGitHubOwner")
github_username = os.environ.get("PrivateGitHubUsername")
github_email = os.environ.get("PrivateGitHubEmail")
github_token = os.environ.get("PrivateGitHubToken")
region_name = os.environ.get("AWS_REGION")

# Print environment variable values
print("SNSTopic: ", sns_topic_arn)
print("PrivateGitHubRepo: ", github_repo)
print("PrivateGitHubOwner: ", github_owner)
print("PrivateGitHubUsername: ", github_username)
print("PrivateGitHubEmail: ", github_email)
print("PrivateGitHubToken: ", github_token)
print("AWS_REGION: ", region_name)

# Instantiate boto3 clients
codeguru_security_client = boto3.client('codeguru-security')
codeartifact_client = boto3.client('codeartifact')
sns_client = boto3.client('sns')
codebuild_client = boto3.client('codebuild')
session = boto3.session.Session()
secrets_manager_client = session.client(service_name='secretsmanager', region_name=region_name)

# Method to push file to GitHub repo
def put_file_to_github(url, github_token, github_username, github_email, content_base64, commit_message, include_sha, existing_file_sha):
    try:
        response = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        data = {
            "message": commit_message,
            "committer": {
                "name": github_username,
                "email": github_email
            },
            "content": content_base64
        }

        if include_sha:
            data["sha"] = existing_file_sha

        response = requests.put(url, headers=headers, json=data)

        if response.status_code == 200 or response.status_code == 201:
            print(f"Private internal package pushed to GitHub successfully.")
        else:
            print(f"Failed to push file to GitHub. Status code: {response.status_code}")
            print("Response content: ", response.text)
    except Exception as error:
        print(f"Failed to push file to GitHub due to an exception: {error}")
    finally:
        return response

# Method to execute shell commands
def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return None

# Method to format findings for SNS email readability
def format_findings(findings):
    formatted_message = ""
    for index, finding in enumerate(findings, start=1):
        formatted_message += f"\n{index}. Vulnerability: {finding['title']}\n"
        formatted_message += f"   - Description: {finding['description']}\n"
        formatted_message += f"   - Severity: {finding['severity']}\n"
        formatted_message += f"   - Recommendation: {finding['remediation']['recommendation']['text']}\n"
        formatted_message += f"   - Path: {finding['vulnerability']['filePath']['path']}\n"
        
        reference_urls = finding.get('referenceUrls', [])
        if reference_urls:
            formatted_reference_urls = ', '.join(reference_urls)
        else:
            formatted_reference_urls = 'No reference URLs available'
            
        formatted_message += f"   - Reference URLs: {formatted_reference_urls}\n\n"
        
    return formatted_message

# Method to adjust package name
def sanitize_package_name(name):
    return re.sub(r'[^a-zA-Z0-9-_$:.]', '', name)

def main():
    approved_packages = []
    
    try:
        # Instantiate boto3 clients
        codeguru_security_client = boto3.client('codeguru-security')
        codeartifact_client = boto3.client('codeartifact')
        sns_client = boto3.client('sns')
        codebuild_client = boto3.client('codebuild')

        # Read CSV file to get external package information
        with open('external-package-request.csv', newline='') as csvfile:
            package_reader = csv.reader(csvfile)
            for row in package_reader:
                external_package_name, external_package_url = row
                external_package_name = sanitize_package_name(external_package_name)
                print(f"Processing package: {external_package_name} from {external_package_url}")

                # Download external package repository
                zip_file_name = f"{external_package_name}.zip"
                download_response = requests.get(external_package_url)
                if download_response.status_code == 200:
                    with open(zip_file_name, "wb") as zip_file:
                        zip_file.write(download_response.content)
                    
                    print("Package downloaded successfully")
                    # Perform CodeGuru Security Scans
                    try:
                        print("Initiating Security Scan for External Package Repository: " + external_package_name)
                        print("Creating CodeGuru Security Upload URL...")
                        create_url_input = {"scanName": external_package_name}
                        create_url_response = codeguru_security_client.create_upload_url(**create_url_input)
                        url = create_url_response["s3Url"]
                        artifact_id = create_url_response["codeArtifactId"]

                        print("Uploading External Package Repository File...")

                        upload_response = requests.put(
                            url,
                            headers=create_url_response["requestHeaders"],
                            data=open(zip_file_name, "rb"),
                        )

                        if upload_response.status_code == 200:
                            
                            print("Performing CodeGuru Security and Quality Scans...")
                            
                            scan_input = {
                                "resourceId": {
                                    "codeArtifactId": artifact_id,
                                },
                                "scanName": external_package_name,
                                "scanType": "Standard", # Express
                                "analysisType": "Security" # All
                            }
                            create_scan_response = codeguru_security_client.create_scan(**scan_input)
                            run_id = create_scan_response["runId"]

                            print("Retrieving Scan Results...")
                            
                            get_scan_input = {
                                "scanName": external_package_name,
                                "runId": run_id,
                            }

                            while True:
                                get_scan_response = codeguru_security_client.get_scan(**get_scan_input)
                                if get_scan_response["scanState"] == "InProgress":
                                    time.sleep(1)
                                else:
                                    break

                            if get_scan_response["scanState"] != "Successful":
                                raise Exception(f"CodeGuru Scan {external_package_name} failed")
                            else:

                                print("Analyzing Security and Quality Finding Severities...")

                                get_findings_input = {
                                    "scanName": external_package_name,
                                    "maxResults": 20,
                                    "status": "Open",
                                }

                                get_findings_response = codeguru_security_client.get_findings(**get_findings_input)
                                if "findings" in get_findings_response:
                                    # Check if any finding severity is medium or high
                                    has_medium_or_high_severity = any(finding["severity"] in ["Medium", "High"] for finding in get_findings_response["findings"])

                                    # If the package passes the security checks, add it to the approved_packages list
                                    if not has_medium_or_high_severity:
                                        print("No medium or high severities found. Pushing to GitHub repository...")
                                        approved_packages.append(external_package_name)

                                        for approved_package in approved_packages:
                                            try:
                                                if github_token:
                                                    print("GitHub token found. Attempting to push package to GitHub repository...")
                                                    zip_file_name = f"{approved_package}.zip"

                                                    # Load file content
                                                    with open(zip_file_name, "rb") as file:
                                                        content = file.read()

                                                    # Encode content to base64
                                                    content_base64 = base64.b64encode(content).decode('utf-8')

                                                    # GitHub repository details
                                                    commit_message = "Add private package - " +  zip_file_name # Commit message
                                                    branch = "main"  # Branch where you want to push the file
                                                    url = f"https://api.github.com/repos/{github_owner}/{github_repo}/contents/packages/{zip_file_name}"

                                                    # Query existing file SHA
                                                    get_existing_file_response = requests.get(
                                                        url,
                                                        headers={
                                                            "Accept": "application/vnd.github.v3+json",
                                                            "Authorization": f"Bearer {github_token}"
                                                        }
                                                    )

                                                    if get_existing_file_response.status_code == 200:
                                                        existing_file_info = get_existing_file_response.json()
                                                        existing_file_sha = existing_file_info.get('sha')

                                                        # Send the request to GitHub API
                                                        response = put_file_to_github(url, github_token, github_username, github_email, content_base64, commit_message, True, existing_file_sha)
                                                    elif get_existing_file_response.status_code == 404:
                                                        # If file not found, call put_file_to_github without SHA
                                                        response = put_file_to_github(url, github_token, github_username, github_email, content_base64, commit_message, False, None)
                                                    else:
                                                        print(f"Failed to get existing file from GitHub. Status code: {get_existing_file_response.status_code}")
                                                else:
                                                    print("GitHub personal access token not found in Secrets Manager.")
                                            except Exception as error:
                                                print(f"Action Failed for approved package {approved_package}, reason: {error}")

                                    else:
                                        print("Medium or high severities found. An email has been sent to the requestor with additional details.")
                                        subject = external_package_name + " Medium to High Severity Findings"
                                        formatted_message = format_findings(get_findings_response["findings"])

                                        sns_client.publish(
                                            TopicArn=sns_topic_arn,
                                            Subject=f"{external_package_name} Security Findings Report",
                                            Message=f"Security Findings Report for External Package Repository: {external_package_name}\n\n{formatted_message}"
                                        )
                        else:
                            raise Exception(f"Source failed to upload external package to CodeGuru Security with status {upload_response.status_code}")
                    except Exception as error:
                        print(f"Action Failed, reason: {error}")
                    
                    # End CodeGuru Security scan block

                else:
                    print(f"Failed to download package from {external_package_url}")

    except Exception as error:
        print(f"Action Failed, reason: {error}")

if __name__ == "__main__":
    main()
