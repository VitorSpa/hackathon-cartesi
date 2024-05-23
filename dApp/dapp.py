from os import environ
import logging
import requests
from urllib.parse import urlparse
from urllib.parse import parse_qs
from cartesi_wallet.util import hex_to_str, str_to_hex
import json
import cartesi_wallet.wallet as Wallet


logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

rollup_server = environ["ROLLUP_HTTP_SERVER_URL"]
logger.info(f"HTTP rollup_server url is {rollup_server}")

wallet = Wallet
rollup_address = ""

app_relay_address = "0xF5DE34d6BbC0446E2a45719E718efEbaaE179daE" #open(f'./deployments/{network}/ERC20Portal.json')
ether_portal_address = "0xFfdbe43d4c855BF7e0f105c400A50857f53AB044" #open(f'./deployments/{network}/EtherPortal.json')
erc20_portal_address = "0x9C21AEb2093C32DDbC53eEF24B873BDCd1aDa1DB" #open(f'./deployments/{network}/ERC20Portal.json')
erc721_portal_address = "0x237F8DD094C0e47f4236f12b4Fa01d6Dae89fb87" #open(f'./deployments/{network}/ERC721Portal.json')


def encode(d):
    return "0x" + json.dumps(d).encode("utf-8").hex()

def decode_json(b):
    s = bytes.fromhex(b[2:]).decode("utf-8")
    d = json.loads(s)
    return d


def get_model_mocked_data():
    """ 
        We must predict the usage and generation for each house and sum it for all users in the marketplace, with that info one can sell, 
        keep or buy energy credits at a given moment and negotiate it. 
        
        The hardware collects data for each house(usage and gen) and we know it, so we can use it to predict the feature usage. To simulate the info,
        we will have a few samples as a test set. When a request to predict future usage/gen is made, we generate a random index and retrieve a sample 
        to use as input of the model.            
 
    """
    #TODO
    pass

def handle_advance(data):
    logger.info(f"Received advance request data {data}")
    msg_sender = data["metadata"]["msg_sender"]
    payload = data["payload"]

    # logger.info("PAYLOAD", hex_to_str( payload))

    try:
        notice = None
        if msg_sender.lower() == erc20_portal_address.lower(): # Deposit PowerToken      
            notice = wallet.erc20_deposit_process(payload)
            response = requests.post(rollup_server + "/notice", json={"payload": notice.payload})
        elif msg_sender.lower() == ether_portal_address.lower(): # Deposit Ether      
            notice = wallet.ether_deposit_process(payload)
            response = requests.post(rollup_server + "/notice", json={"payload": notice.payload})
        else:
            req_json = decode_json(payload)

            if req_json["method"] == "erc20_transfer":
                """
                    When a transfer of PowerTokens is made from user X to user Y, we made a transfer of ethers from user Y to user X, based on the agreed value.
                    The value of one PowerToken is mocked in this demo.
                """
                power_token_cost = 0.0001
                
                notice = wallet.erc20_transfer(req_json["from"].lower(), req_json["to"].lower(), req_json["erc20"].lower(), req_json["amount"])
                response = requests.post(rollup_server + "/notice", json={"payload": notice.payload})
                
                logger.info("Transfer of power tokens made.")

                notice = wallet.ether_transfer(req_json["to"].lower(), req_json["from"].lower(), req_json["amount"] * req_json['value_per_token'])
                response = requests.post(rollup_server + "/notice", json={"payload": notice.payload})

                logger.info("Payment completed")

            if req_json["method"] == "erc20_withdraw":
                voucher = wallet.erc20_withdraw(req_json["from"].lower(), req_json["erc20"].lower(), req_json["amount"])
                response = requests.post(rollup_server + "/voucher", json={"payload": voucher.payload, "destination": voucher.destination})
 
        if notice:
            logger.info(f"Received notice status {response.status_code} body {response.content}")
        return "accept"
    except Exception as error:
        error_msg = f"Failed to process command '{payload}'. {error}"
        response = requests.post(rollup_server + "/report", json={"payload": encode(error_msg)})
        logger.debug(error_msg, exc_info=True)
        return "reject"


def handle_inspect(data):
    logger.info(f"Received inspect request data {data}")
    try:
        url = urlparse(hex_to_str(data["payload"]))
        if url.path.startswith("balance/"):
            info = url.path.replace("balance/", "").split("/")
            token_type, account = info[0].lower(), info[1].lower()
            token_address, token_id, amount = "", 0, 0

            logger.info("ether request")
            if (token_type == "ether"):
                amount = wallet.balance_get(account).ether_get()
                print(amount)
                logger.info("ether request" )
            elif (token_type == "erc20"):
                token_address = info[2]
                amount = wallet.balance_get(account).erc20_get(token_address.lower())
            elif (token_type == "erc721"):
                token_address, token_id = info[2], info[3]
                amount = 1 if token_id in wallet.balance_get(account).erc721_get(token_address.lower()) else 0
            
            report = {"payload": encode({"token_id": token_id, "amount": amount, "token_type": token_type})}
            response = requests.post(rollup_server + "/report", json=report)
            logger.info(f"Received report status {response.status_code} body {response.content}")
        elif url.path.startswith("model_report/"):
            pass
            #TODO: generate model report and log it to the user
        return "accept"
    except Exception as error:
        error_msg = f"Failed to process inspect request. {error}"
        logger.debug(error_msg, exc_info=True)
        logger.info(error_msg)
        return "reject"

handlers = {
    "advance_state": handle_advance,
    "inspect_state": handle_inspect,
}

finish = {"status": "accept"}

while True:
    logger.info("Sending finish")
    response = requests.post(rollup_server + "/finish", json=finish)
    logger.info(f"Received finish status {response.status_code}")
    if response.status_code == 202:
        logger.info("No pending rollup request, trying again")
    else:
        rollup_request = response.json()
        data = rollup_request["data"]
        handler = handlers[rollup_request["request_type"]]
        finish["status"] = handler(rollup_request["data"])