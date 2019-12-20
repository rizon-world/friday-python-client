import base64
import hashlib
import json
from typing import Any, Dict, List

import ecdsa

from hdacpy.typing import SyncMode
from hdacpy.wallet import privkey_to_address, privkey_to_pubkey
from hdacpy.exceptions import BadRequestException, EmptyMsgException

import requests


class Transaction:
    """A Cosmos transaction.

    After initialization, one or more atom transfers can be added by
    calling the `add_transfer()` method. Finally, call
    `get_pushable_tx()` to get a signed transaction that can be pushed
    to the `POST /txs` endpoint of the Cosmos REST API.
    """

    def __init__(
        self,
        *,
        host: str,
        privkey: str,
        account_num: int,
        sequence: int,
        gas_price: int,
        memo: str = "",
        chain_id: str = "friday-devnet",
        sync_mode: SyncMode = "sync",
    ) -> None:
        self._host = host
        self._privkey = privkey
        self._account_num = account_num
        self._sequence = sequence
        self._gas_price = gas_price
        self._memo = memo
        self._chain_id = chain_id
        self._sync_mode = sync_mode
        self._msgs: List[dict] = []

    def _get(self, url:str, params:dict) -> requests.Response:
        resp = requests.get(url, params=params)
        return resp

    def _post_json(self, url:str, json_param:dict) -> requests.Response:
        resp = requests.post(url, json=json_param)
        return resp

    def balance(self, address: str):
        url = "/".join([self._host, "executionlayer/balance"])
        resp = self._get(url, params={"address": address})
        return resp

    def transfer(self, sender_address: str, recipient_address:str, 
                 amount: int, gas_price: int, fee: int,
                 memo: str = "") -> None:
        url = "/".join([self._host, "executionlayer/transfer"])
        params = {
	        "chain_id": self._chain_id,
	        "memo": memo,
	        "gas_price": str(gas_price),
            "fee": str(fee),
	        "sender_address": sender_address,
            "recipient_address": recipient_address,
	        "amount": amount
        }
        resp = self._post_json(url, json_param=params)
        if resp.status_code != 200:
            raise BadRequestException
        
        value = resp.json().get("value")
        msgs = value.get("msg")
        if len(msgs) == 0:
            raise EmptyMsgException

        self._msgs.extend(msgs)

    def bond(self, address: str, amount: int, gas_price: int, fee:int, memo: str=""):
        url = "/".join([self._host, "executionlayer/bond"])
        params = {
	        "chain_id": self._chain_id,
	        "memo": memo,
	        "gas_price": str(gas_price),
            "fee": str(fee),
	        "address": address,
	        "amount": amount
        }
        resp = self._post_json(url, json_param=params)
        if resp.status_code != 200:
            raise BadRequestException
        
        value = resp.json().get("value")
        msgs = value.get("msg")
        if len(msgs) == 0:
            raise EmptyMsgException

        self._msgs.extend(msgs)

    def unbond(self, address: str, amount: int, gas_price: int, fee: int, memo: str=""):
        url = "/".join([self._host, "executionlayer/unbond"])
        params = {
	        "chain_id": self._chain_id,
	        "memo": memo,
	        "gas_price": str(gas_price),
            "fee": str(fee),
	        "address": address,
	        "amount": amount
        }
        resp = self._post_json(url, json_param=params)
        if resp.status_code != 200:
            raise BadRequestException
        
        value = resp.json().get("value")
        msgs = value.get("msg")
        if len(msgs) == 0:
            raise EmptyMsgException

        self._msgs.extend(msgs)

    def send_tx(self):
        tx = self._get_pushable_tx()
        url = "/".join([self._host, "txs"])
        resp = self._post_json(url, json_param=tx)
        return resp

    def _get_pushable_tx(self) -> str:
        pubkey = privkey_to_pubkey(self._privkey)
        base64_pubkey = base64.b64encode(bytes.fromhex(pubkey)).decode("utf-8")
        pushable_tx = {
            "tx": {
                "msg": self._msgs,
                "fee": {
                    "gas": str(self._gas_price),
                    "amount": [],
                },
                "memo": self._memo,
                "signatures": [
                    {
                        "signature": self._sign(),
                        "pub_key": {"type": "tendermint/PubKeySecp256k1", "value": base64_pubkey},
                        "account_number": str(self._account_num),
                        "sequence": str(self._sequence),
                    }
                ],
            },
            "mode": self._sync_mode,
        }
        return pushable_tx

    def _sign(self) -> str:
        message_str = json.dumps(self._get_sign_message(), separators=(",", ":"), sort_keys=True)
        message_bytes = message_str.encode("utf-8")

        privkey = ecdsa.SigningKey.from_string(bytes.fromhex(self._privkey), curve=ecdsa.SECP256k1)
        signature_compact = privkey.sign_deterministic(
            message_bytes, hashfunc=hashlib.sha256, sigencode=ecdsa.util.sigencode_string_canonize
        )

        signature_base64_str = base64.b64encode(signature_compact).decode("utf-8")
        return signature_base64_str

    def _get_sign_message(self) -> Dict[str, Any]:
        return {
            "chain_id": self._chain_id,
            "account_number": str(self._account_num),
            "fee": {
                "gas": str(self._gas_price),
                "amount": [],
            },
            "memo": self._memo,
            "sequence": str(self._sequence),
            "msgs": self._msgs,
        }