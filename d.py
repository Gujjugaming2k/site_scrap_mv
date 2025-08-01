# decrypt.py
from Crypto.Cipher import AES
import sys

key = b'VFlixPrimeSuperSecurePassword123' 

def decrypt_and_run(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()

    nonce = data[:16]
    tag = data[16:32]
    ciphertext = data[32:]

    cipher = AES.new(key, AES.MODE_EAX, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)

    exec(plaintext, globals())

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python decrypt.py abc.enc")
    else:
        decrypt_and_run(sys.argv[1])
