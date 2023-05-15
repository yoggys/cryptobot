from os import getenv

from dotenv import load_dotenv

from utils.client import CryptoBot

load_dotenv(override=True)

if __name__ == "__main__":
    client: CryptoBot = CryptoBot()
    client.run(getenv("TOKEN"))
