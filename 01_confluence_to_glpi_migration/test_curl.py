import subprocess
import config

print("Testing GLPI Connection with CURL (via Python)...")
print("")

# Construct the curl command using config values
# curl -v -k -X GET "URL" -H "App-Token: ..." -H "Authorization: ..."

# Handle SSL verification for curl
# If VERIFY_SSL is False, use -k (insecure)
# If it's a path, use --cacert "path"
# If True, verify (default curl behavior)

curl_cmd = ["curl", "-v", "-X", "GET", f"{config.GLPI_URL}/initSession"]
curl_cmd.extend(["-H", f"App-Token: {config.APP_TOKEN}"])
curl_cmd.extend(["-H", f"Authorization: user_token {config.USER_TOKEN}"])

if config.VERIFY_SSL is False:
    curl_cmd.append("-k")
elif isinstance(config.VERIFY_SSL, str):
    curl_cmd.extend(["--cacert", config.VERIFY_SSL])

print(f"Running: {' '.join(curl_cmd)}")
print("")

try:
    subprocess.run(curl_cmd, check=True)
except subprocess.CalledProcessError as e:
    print(f"Curl command failed: {e}")
except FileNotFoundError:
    print("Error: 'curl' executable not found in PATH.")

print("")
input("Press Enter to exit...")
